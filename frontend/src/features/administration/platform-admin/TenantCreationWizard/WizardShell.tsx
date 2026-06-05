/**
 * WizardShell — 4-step Tenant Creation Wizard container.
 * V9 S12.2 — manages step state and renders progress indicator.
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { Step1TenantDetails, type Step1Data } from "./Step1TenantDetails";
import { Step2AdminUser, type Step2Data } from "./Step2AdminUser";
import { Step3CarrierAssign, type Step3Data } from "./Step3CarrierAssign";
import { Step4ReviewActivate } from "./Step4ReviewActivate";

export interface WizardData {
  step1: Step1Data | null;
  step2: Step2Data | null;
  step3: Step3Data | null;
}

const STEP_COUNT = 4;

export function WizardShell(): React.JSX.Element {
  const labels = useLabels();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [data, setData] = useState<WizardData>({ step1: null, step2: null, step3: null });

  const stepLabels = [
    labels.platform_wizard_step1,
    labels.platform_wizard_step2,
    labels.platform_wizard_step3,
    labels.platform_wizard_step4,
  ];

  const goNext = () => setCurrentStep((s) => Math.min(s + 1, STEP_COUNT));
  const goBack = () => setCurrentStep((s) => Math.max(s - 1, 1));

  const onComplete = (newSlug: string) => {
    navigate(`/platform/tenants/${newSlug}`);
  };

  return (
    <div className="wizard-shell">
      {/* Progress indicator */}
      <nav className="wizard-shell__progress" aria-label="Wizard progress">
        {stepLabels.map((label, idx) => {
          const step = idx + 1;
          const cls = [
            "wizard-shell__step",
            step === currentStep ? "wizard-shell__step--active" : "",
            step < currentStep ? "wizard-shell__step--done" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div key={step} className={cls}>
              <span className="wizard-shell__step-num">{step}</span>
              <span className="wizard-shell__step-label">{label}</span>
            </div>
          );
        })}
      </nav>

      {/* Step content */}
      <div className="wizard-shell__content">
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
        {currentStep === 4 && (
          <Step4ReviewActivate
            data={data}
            onBack={goBack}
            onComplete={onComplete}
          />
        )}
      </div>
    </div>
  );
}
