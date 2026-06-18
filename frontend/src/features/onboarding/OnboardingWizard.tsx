/**
 * OnboardingWizard — 5-step first-login wizard for TENANT_ADMIN.
 *
 * Phase 7BCD redesign (Item 2.1):
 *   - Progress indicator replaced with wizard-steps BEM block (same as WizardShell).
 *   - Step content region uses wizard-panel BEM block.
 *   - No API or step-logic changes.
 *
 * Each step component has its own data types:
 *   Step1: initial: OrgProfileData | null, onNext(data)
 *   Step2: initial: { primary, secondary } | null, onNext(data), onBack
 *   Step3: initial: BrandingData | null, onNext(data), onBack
 *   Step4: onNext(), onBack
 *   Step5: onBack
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import type { OrgProfileData } from "./Step1OrgProfile";import type { ContactData } from "./Step2Contacts";
import type { BrandingData } from "./Step3Branding";

import { Step1OrgProfile } from "./Step1OrgProfile";
import { Step2Contacts } from "./Step2Contacts";
import { Step3Branding } from "./Step3Branding";
import { Step4CarrierOverview } from "./Step4CarrierOverview";
import { Step5Complete } from "./Step5Complete";

// ── Wizard data accumulator ───────────────────────────────────────────────────

interface WizardState {
  step1: OrgProfileData | null;
  step2: { primary: ContactData; secondary: ContactData } | null;
  step3: BrandingData | null;
}

const TOTAL_STEPS = 5;

interface StepDef {
  labelKey: string;
  defaultLabel: string;
}

const STEP_DEFS: StepDef[] = [
  { labelKey: "step.1", defaultLabel: "Organisation Profile" },
  { labelKey: "step.2", defaultLabel: "Contacts" },
  { labelKey: "step.3", defaultLabel: "Branding" },
  { labelKey: "step.4", defaultLabel: "Carrier Overview" },
  { labelKey: "step.5", defaultLabel: "Complete" },
];

export function OnboardingWizard(): React.JSX.Element {
  const labelOnboarding = useLabels("onboarding");

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [wizardState, setWizardState] = useState<WizardState>({
    step1: null,
    step2: null,
    step3: null,
  });

  function handleNext(): void {
    setCurrentStep((prev) => Math.min(prev + 1, TOTAL_STEPS));
  }

  function handleBack(): void {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  }

  function renderStep(): React.JSX.Element {
    switch (currentStep) {
      case 1:
        return (
          <Step1OrgProfile
            initial={wizardState.step1}
            onNext={(data) => {
              setWizardState((prev) => ({ ...prev, step1: data }));
              handleNext();
            }}
          />
        );
      case 2:
        return (
          <Step2Contacts
            initial={wizardState.step2}
            onNext={(data) => {
              setWizardState((prev) => ({ ...prev, step2: data }));
              handleNext();
            }}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <Step3Branding
            initial={wizardState.step3}
            onNext={(data) => {
              setWizardState((prev) => ({ ...prev, step3: data }));
              handleNext();
            }}
            onBack={handleBack}
          />
        );
      case 4:
        return <Step4CarrierOverview onNext={handleNext} onBack={handleBack} />;
      case 5:
        return <Step5Complete onBack={handleBack} />;
      default:
        return (
          <Step1OrgProfile
            initial={wizardState.step1}
            onNext={(data) => {
              setWizardState((prev) => ({ ...prev, step1: data }));
              handleNext();
            }}
          />
        );
    }
  }

  return (
    <div className="onboarding-wizard">
      <header className="onboarding-wizard__header">
        <h1 className="onboarding-wizard__title">
          {labelOnboarding("wizard.title", "Welcome — Let's get you set up")}
        </h1>
        <p className="onboarding-wizard__subtitle">
          {labelOnboarding(
            "wizard.subtitle",
            "Complete these steps to configure your organisation. You can update these settings later from the Administration panel."
          )}
        </p>
      </header>

      {/* ── wizard-steps progress bar ── */}
      <nav
        className="wizard-steps"
        aria-label={labelOnboarding("aria.progress", "Setup progress")}
      >
        {STEP_DEFS.map((def, idx) => {
          const step = idx + 1;
          const isActive   = step === currentStep;
          const isComplete = step < currentStep;
          const cls = [
            "wizard-steps__item",
            isActive   ? "wizard-steps__item--active"  : "",
            isComplete ? "wizard-steps__item--complete" : "",
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <div key={step} className={cls} aria-current={isActive ? "step" : undefined}>
              <span className="wizard-steps__num">{isComplete ? "✓" : step}</span>
              <span className="wizard-steps__label">
                {labelOnboarding(def.labelKey, def.defaultLabel)}
              </span>
            </div>
          );
        })}
      </nav>

      {/* ── Step content in wizard-panel ── */}
      <div className="wizard-panel">
        <div className="wizard-panel__body">
          {renderStep()}
        </div>
        <div className="onboarding-wizard__step-counter wizard-panel__footer">
          <span>
            {labelOnboarding("step.counter_prefix", "Step")} {currentStep}{" "}
            {labelOnboarding("step.counter_of", "of")} {TOTAL_STEPS}
          </span>
        </div>
      </div>
    </div>
  );
}
