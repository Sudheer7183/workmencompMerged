/**
 * Step2AdminUser — Admin user details for the new tenant.
 * V9 S12.2 — first/last name, email, invitation toggle.
 *
 * Fix: replaced label_shared("platform_wizard_step", "platform_wizard_step")2
 * with label_platform_admin("step2.title", "Admin User") per V9 S23.3.
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
  const label_platform_admin = useLabels("platform_admin");
  // const label_shared = useLabels("shared");
  const [firstName, setFirstName] = useState(initial?.firstName ?? "");
  const [lastName, setLastName] = useState(initial?.lastName ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [sendInvite, setSendInvite] = useState(initial?.sendInvite ?? true);

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const canProceed =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    EMAIL_REGEX.test(email.trim());

  const handleSubmit = (e: React.FormEvent): void => {
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
      {/* FIX: was label_shared("platform_wizard_step", "platform_wizard_step")2 */}
      <h2 className="wizard-step__title">
        {label_platform_admin("step2.title", "Admin User")}
      </h2>

      <div className="form-field">
        <label className="form-field__label" htmlFor="admin-first">
          {label_platform_admin("field.admin_first", "First Name")}
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
          {label_platform_admin("field.admin_last", "Last Name")}
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
          {label_platform_admin("field.admin_email", "Admin Email")}
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
          {label_platform_admin("field.invite_toggle", "Send invitation email")}
        </label>
      </div>

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_platform_admin("btn.back", "Back")}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {label_platform_admin("btn.next", "Next")}
        </button>
      </div>
    </form>
  );
}