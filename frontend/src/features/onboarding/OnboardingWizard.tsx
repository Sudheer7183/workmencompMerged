/**
 * OnboardingWizard — 5-step first-login wizard for TENANT_ADMIN.
 *
 * V9 S13.1 — blocking redirect triggered by ProtectedRoute when
 * role === TENANT_ADMIN && !onboarding_completed.
 *
 * Step completion saves data incrementally — steps 1–3 PUT to the API
 * before advancing; steps 4–5 are read-only / completion.
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { Step1OrgProfile, type OrgProfileData } from "./Step1OrgProfile";
import { Step2Contacts, type ContactData } from "./Step2Contacts";
import { Step3Branding, type BrandingData } from "./Step3Branding";
import { Step4CarrierOverview } from "./Step4CarrierOverview";
import { Step5Complete } from "./Step5Complete";


interface WizardState {
  step1: OrgProfileData | null;
  step2: { primary: ContactData; secondary: ContactData } | null;
  step3: BrandingData | null;
}

async function saveProfile(data: OrgProfileData): Promise<void> {
  await axios.put("/api/v1/tenant/profile", {
    display_name: data.display_name,
    legal_name: data.legal_name,
    address_line1: data.address_line1 || null,
    address_line2: data.address_line2 || null,
    city: data.city || null,
    state_code: data.state_code || null,
    zip_code: data.zip_code || null,
  });
}

async function saveContacts(primary: ContactData, secondary: ContactData): Promise<void> {
  await axios.put("/api/v1/tenant/contacts", [primary, secondary]);
}

async function saveBranding(data: BrandingData): Promise<void> {
  await axios.put("/api/v1/tenant/branding", {
    brand_color: data.brandColor || null,
  });
}

export function OnboardingWizard(): React.JSX.Element {
  const labels = useLabels();
  const [step, setStep] = useState(1);
  const [state, setState] = useState<WizardState>({ step1: null, step2: null, step3: null });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const stepLabels = [
    labels.onboarding_step1,
    labels.onboarding_step2,
    labels.onboarding_step3,
    labels.onboarding_step4,
    labels.onboarding_step5,
  ];

  const goBack = () => setStep((s) => Math.max(s - 1, 1));

  const handleStep1 = async (data: OrgProfileData) => {
    setSaving(true);
    setSaveError(null);
    try {
      await saveProfile(data);
      setState((prev) => ({ ...prev, step1: data }));
      setStep(2);
    } catch {
      setSaveError(labels.error_generic);
    } finally {
      setSaving(false);
    }
  };

  const handleStep2 = async (data: { primary: ContactData; secondary: ContactData }) => {
    setSaving(true);
    setSaveError(null);
    try {
      await saveContacts(data.primary, data.secondary);
      setState((prev) => ({ ...prev, step2: data }));
      setStep(3);
    } catch {
      setSaveError(labels.error_generic);
    } finally {
      setSaving(false);
    }
  };

  const handleStep3 = async (data: BrandingData) => {
    setSaving(true);
    setSaveError(null);
    try {
      await saveBranding(data);
      setState((prev) => ({ ...prev, step3: data }));
      setStep(4);
    } catch {
      setSaveError(labels.error_generic);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="onboarding-wizard">
      <header className="onboarding-wizard__header">
        <h1 className="onboarding-wizard__title">{labels.onboarding_title}</h1>
      </header>

      {/* Progress bar */}
      <nav className="onboarding-wizard__progress" aria-label="Onboarding progress">
        {stepLabels.map((label, idx) => {
          const s = idx + 1;
          const cls = [
            "onboarding-wizard__step",
            s === step ? "onboarding-wizard__step--active" : "",
            s < step ? "onboarding-wizard__step--done" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div key={s} className={cls}>
              <span className="onboarding-wizard__step-num">{s}</span>
              <span className="onboarding-wizard__step-label">{label}</span>
            </div>
          );
        })}
      </nav>

      {saveError && (
        <div className="alert alert--error" role="alert">{saveError}</div>
      )}

      {saving && <p className="onboarding-wizard__saving">{labels.loading}</p>}

      <div className="onboarding-wizard__content">
        {step === 1 && (
          <Step1OrgProfile initial={state.step1} onNext={(d) => void handleStep1(d)} />
        )}
        {step === 2 && (
          <Step2Contacts
            initial={state.step2}
            onNext={(d) => void handleStep2(d)}
            onBack={goBack}
          />
        )}
        {step === 3 && (
          <Step3Branding
            initial={state.step3}
            onNext={(d) => void handleStep3(d)}
            onBack={goBack}
          />
        )}
        {step === 4 && (
          <Step4CarrierOverview onNext={() => setStep(5)} onBack={goBack} />
        )}
        {step === 5 && <Step5Complete onBack={goBack} />}
      </div>
    </div>
  );
}
