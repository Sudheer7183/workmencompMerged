/**
 * WizardShell — 4-step Tenant Creation Wizard container.
 *
 * Owns:
 *  - Step navigation state and accumulated WizardData
 *  - Carrier name lookup for Step4 display
 *  - POST /platform/tenants provisioning call + isActivating / activationError state
 *
 * Layout: wizard-page → wizard-steps nav (progress bar) → wizard-panel (body per step)
 * Each step renders inside wizard-panel__body so it gets the correct padding/gap.
 *
 * Step 3 (Carrier Assignment) is optional per Phase 7A.
 */

import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";
import { Step1TenantDetails, type Step1Data } from "./Step1TenantDetails";
import { Step2AdminUser, type Step2Data } from "./Step2AdminUser";
import { Step3CarrierAssign, type Step3Data } from "./Step3CarrierAssign";
import { Step4ReviewActivate } from "./Step4ReviewActivate";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface WizardData {
  step1: Step1Data | null;
  step2: Step2Data | null;
  step3: Step3Data | null;
}

interface CarrierOption {
  carrier_id: number;
  carrier_name: string;
  slug: string;
}

interface StepDefinition {
  labelKey: string;
  defaultLabel: string;
  isOptional?: boolean;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STEP_COUNT = 4;

const STEP_DEFINITIONS: StepDefinition[] = [
  { labelKey: "wizard.step1", defaultLabel: "Tenant Details" },
  { labelKey: "wizard.step2", defaultLabel: "Admin User" },
  { labelKey: "wizard.step3", defaultLabel: "Carrier Assignment", isOptional: true },
  { labelKey: "wizard.step4", defaultLabel: "Review & Activate" },
];

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchCarriers(): Promise<CarrierOption[]> {
  try {
    const { data } = await axios.get<CarrierOption[]>("/platform/carriers");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export function WizardShell(): React.JSX.Element {
  const label = useLabels("platform_admin");
  const navigate = useNavigate();

  const [currentStep, setCurrentStep] = useState(1);
  const [data, setData] = useState<WizardData>({ step1: null, step2: null, step3: null });
  const [isActivating, setIsActivating] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);

  const { data: carriers = [] } = useQuery<CarrierOption[]>({
    queryKey: ["platform-carriers-wizard"],
    queryFn: fetchCarriers,
    staleTime: 60 * 1000,
  });

  const carrierNames: Record<number, string> = Object.fromEntries(
    carriers.map((c) => [c.carrier_id, c.carrier_name])
  );

  const goNext = (): void => setCurrentStep((s) => Math.min(s + 1, STEP_COUNT));
  const goBack = (): void => setCurrentStep((s) => Math.max(s - 1, 1));

  // ── Activation ────────────────────────────────────────────────────────────

  async function handleActivate(): Promise<void> {
    if (!data.step1 || !data.step2) return;
    setIsActivating(true);
    setActivationError(null);

    try {
      const payload = {
        name:             data.step1.tenantName,
        slug:             data.step1.slug,
        tenant_type:      data.step1.tenantType,
        admin_email:      data.step2.email,
        admin_first_name: data.step2.firstName,
        admin_last_name:  data.step2.lastName,
        send_invitation:  data.step2.sendInvite ?? true,
        carrier_ids:      data.step3?.selectedCarrierIds ?? [],
      };

      const response = await axios.post<{ slug: string }>("/platform/tenants", payload);
      navigate(`/platform/tenants/${response.data.slug}`);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActivationError(
        typeof detail === "string"
          ? detail
          : label("wizard.error_generic", "Provisioning failed. Please try again.")
      );
      setIsActivating(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="wizard-page">
      {/* Page heading */}
      <div className="wizard-page__header">
        <h1 className="wizard-page__title">
          {label("btn.new_tenant", "New Tenant")}
        </h1>
        <p className="wizard-page__subtitle">
          {label(
            "wizard.page_subtitle",
            "Complete all steps to provision and activate a new tenant."
          )}
        </p>
      </div>

      {/* Step progress bar */}
      <nav
        className="wizard-steps"
        aria-label={label("aria.progress", "Wizard progress")}
      >
        {STEP_DEFINITIONS.map((def, idx) => {
          const step = idx + 1;
          const isActive   = step === currentStep;
          const isComplete = step < currentStep;

          const cls = [
            "wizard-steps__item",
            isActive   ? "wizard-steps__item--active"   : "",
            isComplete ? "wizard-steps__item--complete"  : "",
            def.isOptional && !isActive && !isComplete
              ? "wizard-steps__item--optional"
              : "",
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <div key={step} className={cls}>
              <span className="wizard-steps__num">
                {isComplete ? "✓" : step}
              </span>
              <span className="wizard-steps__label">
                {label(def.labelKey, def.defaultLabel)}
              </span>
              {def.isOptional && (
                <span className="wizard-steps__optional-hint">
                  {label("wizard.optional_hint", "Optional")}
                </span>
              )}
            </div>
          );
        })}
      </nav>

      {/* Step content panel */}
      <div className="wizard-panel">
        <div className="wizard-panel__body">
          {currentStep === 1 && (
            <Step1TenantDetails
              initial={data.step1}
              onNext={(d) => {
                setData((prev) => ({ ...prev, step1: d }));
                goNext();
              }}
            />
          )}

          {currentStep === 2 && (
            <Step2AdminUser
              initial={data.step2}
              onNext={(d) => {
                setData((prev) => ({ ...prev, step2: d }));
                goNext();
              }}
              onBack={goBack}
            />
          )}

          {currentStep === 3 && (
            <Step3CarrierAssign
              initial={data.step3}
              onNext={(d) => {
                setData((prev) => ({ ...prev, step3: d }));
                goNext();
              }}
              onBack={goBack}
            />
          )}

          {currentStep === 4 && data.step1 && data.step2 && (
            <Step4ReviewActivate
              step1={data.step1}
              step2={data.step2}
              step3={data.step3 ?? { selectedCarrierIds: [] }}
              carrierNames={carrierNames}
              onActivate={() => void handleActivate()}
              onBack={goBack}
              isActivating={isActivating}
            />
          )}
        </div>

        {/* Activation error — shown below step content inside the panel */}
        {activationError && (
          <p className="wizard-panel__error" role="alert">
            {activationError}
          </p>
        )}
      </div>
    </div>
  );
}
