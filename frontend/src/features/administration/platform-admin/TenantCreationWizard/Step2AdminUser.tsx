/**
 * Step2AdminUser — Admin user details for the new tenant.
 * V9 S12.2 — first/last name, email, invitation toggle.
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";

export interface Step2Data {
  firstName: string;
  lastName: string;
  email: string;
  sendInvite: boolean;
}

interface Props {
  initial: Step2Data | null;
  onNext: (data: Step2Data) => void;
  onBack: () => void;
}

export function Step2AdminUser({ initial, onNext, onBack }: Props): React.JSX.Element {
  const labels = useLabels();
  const [firstName, setFirstName] = useState(initial?.firstName ?? "");
  const [lastName, setLastName] = useState(initial?.lastName ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [sendInvite, setSendInvite] = useState(initial?.sendInvite ?? true);

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const canProceed =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    EMAIL_REGEX.test(email.trim());

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canProceed) return;
    onNext({
      firstName: firstName.trim(),
      lastName: lastName.trim(),
      email: email.trim(),
      sendInvite,
    });
  };

  return (
    <form className="wizard-step" onSubmit={handleSubmit}>
      <h2 className="wizard-step__title">{labels.platform_wizard_step2}</h2>

      <div className="form-field">
        <label className="form-field__label" htmlFor="admin-first">
          {labels.platform_field_admin_first}
        </label>
        <input
          id="admin-first"
          className="form-field__input"
          type="text"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          required
        />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="admin-last">
          {labels.platform_field_admin_last}
        </label>
        <input
          id="admin-last"
          className="form-field__input"
          type="text"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          required
        />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="admin-email">
          {labels.platform_field_admin_email}
        </label>
        <input
          id="admin-email"
          className="form-field__input"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>

      <div className="form-field form-field--checkbox">
        <label className="form-field__label form-field__label--inline">
          <input
            type="checkbox"
            checked={sendInvite}
            onChange={(e) => setSendInvite(e.target.checked)}
            className="form-field__checkbox"
          />
          {labels.platform_field_invite_toggle}
        </label>
      </div>

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.platform_btn_back}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {labels.platform_btn_next}
        </button>
      </div>
    </form>
  );
}
