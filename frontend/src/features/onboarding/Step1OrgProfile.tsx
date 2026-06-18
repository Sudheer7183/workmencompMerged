/**
 * Onboarding Step 1 — Organisation Profile.
 * display_name, legal_name, address fields.
 *
 * Fixes applied:
 *  1. label_shared("onboarding_s", "onboarding_s")1_title  → label_onboarding("step1.title", …)
 *  2. label_shared("org_field_address_line", "org_field_address_line")1  → label_org_settings("field.address_line1", …)
 *  3. label_shared("org_field_address_line", "org_field_address_line")2  → label_org_settings("field.address_line2", …)
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";

export interface OrgProfileData {
  display_name: string;
  legal_name: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state_code: string;
  zip_code: string;
}

interface Props {
  initial: OrgProfileData | null;
  onNext: (data: OrgProfileData) => void;
}

export function Step1OrgProfile({ initial, onNext }: Props): React.JSX.Element {
  const label_onboarding = useLabels("onboarding");
  const label_org_settings = useLabels("org_settings");
  const [form, setForm] = useState<OrgProfileData>(
    initial ?? {
      display_name: "", legal_name: "", address_line1: "",
      address_line2: "", city: "", state_code: "", zip_code: "",
    }
  );

  const set = (key: keyof OrgProfileData) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((p) => ({ ...p, [key]: e.target.value }));

  const canProceed = form.display_name.trim().length > 0 && form.legal_name.trim().length > 0;

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (canProceed) onNext(form);
  };

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      {/* FIX: was label_shared("onboarding_s", "onboarding_s")1_title */}
      <h2 className="onboarding-step__title">
        {label_onboarding("step1.title", "Organization Profile")}
      </h2>

      <div className="form-field">
        <label className="form-field__label" htmlFor="ob-display">
          {label_org_settings("field.display_name", "Display Name")}
        </label>
        <input
          id="ob-display"
          className="form-field__input"
          type="text"
          value={form.display_name}
          onChange={set("display_name")}
          required
        />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="ob-legal">
          {label_org_settings("field.legal_name", "Legal Name")}
        </label>
        <input
          id="ob-legal"
          className="form-field__input"
          type="text"
          value={form.legal_name}
          onChange={set("legal_name")}
          required
        />
      </div>

      {/* FIX: was label_shared("org_field_address_line", "org_field_address_line")1 */}
      <div className="form-field">
        <label className="form-field__label" htmlFor="ob-addr1">
          {label_org_settings("field.address_line1", "Address Line 1")}
        </label>
        <input
          id="ob-addr1"
          className="form-field__input"
          type="text"
          value={form.address_line1}
          onChange={set("address_line1")}
        />
      </div>

      {/* FIX: was label_shared("org_field_address_line", "org_field_address_line")2 */}
      <div className="form-field">
        <label className="form-field__label" htmlFor="ob-addr2">
          {label_org_settings("field.address_line2", "Address Line 2")}
        </label>
        <input
          id="ob-addr2"
          className="form-field__input"
          type="text"
          value={form.address_line2}
          onChange={set("address_line2")}
        />
      </div>

      <div className="form-row">
        <div className="form-field">
          <label className="form-field__label" htmlFor="ob-city">
            {label_org_settings("field.city", "City")}
          </label>
          <input
            id="ob-city"
            className="form-field__input"
            type="text"
            value={form.city}
            onChange={set("city")}
          />
        </div>
        <div className="form-field form-field--sm">
          <label className="form-field__label" htmlFor="ob-state">
            {label_org_settings("field.state", "State")}
          </label>
          <input
            id="ob-state"
            className="form-field__input"
            type="text"
            maxLength={2}
            value={form.state_code}
            onChange={set("state_code")}
          />
        </div>
        <div className="form-field form-field--sm">
          <label className="form-field__label" htmlFor="ob-zip">
            {label_org_settings("field.zip", "ZIP Code")}
          </label>
          <input
            id="ob-zip"
            className="form-field__input"
            type="text"
            value={form.zip_code}
            onChange={set("zip_code")}
          />
        </div>
      </div>

      <div className="wizard-step__actions">
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {label_onboarding("btn.continue", "Continue")}
        </button>
      </div>
    </form>
  );
}