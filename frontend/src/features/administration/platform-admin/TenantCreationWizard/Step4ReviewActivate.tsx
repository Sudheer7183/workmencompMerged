/**
 * Step4ReviewActivate — Summary review + activation.
 *
 * V9 S12.2:
 * - Shows all values from Steps 1–3.
 * - "Activate" triggers POST /platform/tenants.
 * - Shows provisioning progress overlay while waiting.
 * - On success navigates to TenantDetail via onComplete callback.
 *
 * Field name alignment with backend TenantCreateRequest:
 *   name             (was: tenant_name)
 *   slug             ✓
 *   tenant_type      ✓ — values: AUDIT_COMPANY | CARRIER | BROKER
 *   carrier_ids      ✓
 *   admin_email      ✓
 *   admin_first_name ✓
 *   admin_last_name  ✓
 *   send_invitation  (was: send_invite)
 *   temporary_password (optional, omitted)
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import type { WizardData } from "./WizardShell";

interface Props {
  data: WizardData;
  onBack: () => void;
  onComplete: (slug: string) => void;
}

type ProvisionStep = "schema" | "migrations" | "seeding" | "keycloak" | "done";

const PROVISION_SEQUENCE: ProvisionStep[] = [
  "schema",
  "migrations",
  "seeding",
  "keycloak",
  "done",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extracts a human-readable error string from any Axios error.
 * Handles the FastAPI Pydantic validation shape:
 *   { detail: [{ msg, loc, type, input }, ...] }
 * and the simple:
 *   { detail: "some string" }
 */
function extractErrorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback;
  const detail = (err.response?.data as { detail?: unknown })?.detail;
  if (!detail) return fallback;
  // Simple string detail
  if (typeof detail === "string") return detail;
  // Pydantic validation array: pick the first error's msg + loc
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: string[] };
    const loc = first.loc?.join(" → ") ?? "";
    const msg = first.msg ?? fallback;
    return loc ? `${loc}: ${msg}` : msg;
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// Provisioning overlay
// ---------------------------------------------------------------------------

function ProvisioningOverlay({
  currentStep,
  labels,
}: {
  currentStep: ProvisionStep;
  labels: ReturnType<typeof useLabels>;
}) {
  const steps: { key: ProvisionStep; label: string }[] = [
    { key: "schema",     label: labels.platform_provisioning_schema },
    { key: "migrations", label: labels.platform_provisioning_migrations },
    { key: "seeding",    label: labels.platform_provisioning_seeding },
    { key: "keycloak",   label: labels.platform_provisioning_keycloak },
  ];

  const currentIdx = PROVISION_SEQUENCE.indexOf(currentStep);

  return (
    <div className="provisioning-overlay" role="status" aria-live="polite">
      <div className="provisioning-overlay__panel">
        <h3 className="provisioning-overlay__title">Provisioning tenant…</h3>
        <ul className="provisioning-overlay__steps">
          {steps.map((s, idx) => {
            const done   = idx < currentIdx;
            const active = idx === currentIdx;
            const cls = [
              "provisioning-overlay__step",
              done   ? "provisioning-overlay__step--done"   : "",
              active ? "provisioning-overlay__step--active" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <li key={s.key} className={cls}>
                <span className="provisioning-overlay__step-icon">
                  {done ? "✓" : active ? "⟳" : "○"}
                </span>
                {s.label}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tenant type display label mapping
// ---------------------------------------------------------------------------
const TENANT_TYPE_LABELS: Record<string, string> = {
  AUDIT_COMPANY: "Audit Company",
  CARRIER:       "Carrier",
  BROKER:        "Broker",
};

// ---------------------------------------------------------------------------
// Step4ReviewActivate
// ---------------------------------------------------------------------------

export function Step4ReviewActivate({ data, onBack, onComplete }: Props): React.JSX.Element {
  const labels = useLabels();
  const [provisionStep, setProvisionStep] = useState<ProvisionStep | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activate = async (asDraft: boolean) => {
    if (!data.step1 || !data.step2) return;
    setError(null);
    setProvisionStep("schema");

    const stepTimer = (step: ProvisionStep, delayMs: number) =>
      new Promise<void>((res) =>
        setTimeout(() => {
          setProvisionStep(step);
          res();
        }, delayMs)
      );

    try {
      const [apiResult] = await Promise.all([
        // POST body aligned exactly to backend TenantCreateRequest schema
        axios.post<{ slug: string }>("/platform/tenants", {
          name:             data.step1.tenantName,      // backend field: "name"
          slug:             data.step1.slug,
          tenant_type:      data.step1.tenantType,      // AUDIT_COMPANY | CARRIER | BROKER
          admin_email:      data.step2.email,
          admin_first_name: data.step2.firstName,
          admin_last_name:  data.step2.lastName,
          send_invitation:  data.step2.sendInvite,      // backend field: "send_invitation"
          carrier_ids:      data.step3?.selectedCarrierIds ?? [],
          // temporary_password omitted — Keycloak will send an invitation email
        }),
        (async () => {
          await stepTimer("migrations", 800);
          await stepTimer("seeding",    1600);
          await stepTimer("keycloak",   2400);
          await stepTimer("done",       3000);
        })(),
      ]);

      onComplete(apiResult.data.slug);
    } catch (err: unknown) {
      setProvisionStep(null);
      setError(extractErrorMessage(err, labels.error_generic));
    }
  };

  if (provisionStep && provisionStep !== "done") {
    return <ProvisioningOverlay currentStep={provisionStep} labels={labels} />;
  }

  const { step1, step2, step3 } = data;

  return (
    <div className="wizard-step">
      <h2 className="wizard-step__title">{labels.platform_wizard_step4}</h2>

      {error && (
        <div className="alert alert--error" role="alert">
          {error}
        </div>
      )}

      <section className="review-section">
        <h3 className="review-section__title">{labels.platform_wizard_step1}</h3>
        <dl className="review-section__dl">
          <dt>{labels.platform_field_tenant_name}</dt>
          <dd>{step1?.tenantName}</dd>
          <dt>{labels.platform_field_subdomain}</dt>
          <dd>
            <code>{step1?.slug}</code>
          </dd>
          <dt>{labels.platform_field_tenant_type}</dt>
          <dd>{TENANT_TYPE_LABELS[step1?.tenantType ?? ""] ?? step1?.tenantType}</dd>
        </dl>
      </section>

      <section className="review-section">
        <h3 className="review-section__title">{labels.platform_wizard_step2}</h3>
        <dl className="review-section__dl">
          <dt>{labels.platform_field_admin_first}</dt>
          <dd>
            {step2?.firstName} {step2?.lastName}
          </dd>
          <dt>{labels.platform_field_admin_email}</dt>
          <dd>{step2?.email}</dd>
        </dl>
      </section>

      <section className="review-section">
        <h3 className="review-section__title">{labels.platform_wizard_step3}</h3>
        <dd>{step3?.selectedCarrierIds.length ?? 0} carrier(s) selected</dd>
      </section>

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.platform_btn_back}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => void activate(true)}
        >
          {labels.platform_btn_save_draft}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void activate(false)}
        >
          {labels.platform_btn_activate}
        </button>
      </div>
    </div>
  );
}
