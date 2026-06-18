/**
 * Onboarding Step 2 — PRIMARY and SECONDARY contact forms.
 *
 * Fix: replaced label_shared("onboarding_s", "onboarding_s")2_title
 * with label_onboarding("step2.title", "Contact Persons") per V9 S23.3.
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";

export interface ContactData {
  contact_type: "PRIMARY" | "SECONDARY";
  contact_name: string;
  contact_email: string;
  contact_phone: string;
}

interface Props {
  initial: { primary: ContactData; secondary: ContactData } | null;
  onNext: (data: { primary: ContactData; secondary: ContactData }) => void;
  onBack: () => void;
}

function emptyContact(type: "PRIMARY" | "SECONDARY"): ContactData {
  return { contact_type: type, contact_name: "", contact_email: "", contact_phone: "" };
}

function ContactFieldset({
  legend,
  contact,
  idPrefix,
  onChange,
}: {
  legend: string;
  contact: ContactData;
  idPrefix: string;
  onChange: (c: ContactData) => void;
}): React.JSX.Element {
  const label_org_settings = useLabels("org_settings");
  const set = (key: keyof ContactData) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...contact, [key]: e.target.value });

  return (
    <fieldset className="contact-form">
      <legend className="contact-form__legend">{legend}</legend>
      <div className="form-field">
        <label className="form-field__label" htmlFor={`${idPrefix}-name`}>
          {label_org_settings("field.contact_name", "Contact Name")}
        </label>
        <input
          id={`${idPrefix}-name`}
          className="form-field__input"
          type="text"
          value={contact.contact_name}
          onChange={set("contact_name")}
          required={contact.contact_type === "PRIMARY"}
        />
      </div>
      <div className="form-field">
        <label className="form-field__label" htmlFor={`${idPrefix}-email`}>
          {label_org_settings("field.contact_email", "Contact Email")}
        </label>
        <input
          id={`${idPrefix}-email`}
          className="form-field__input"
          type="email"
          value={contact.contact_email}
          onChange={set("contact_email")}
          required={contact.contact_type === "PRIMARY"}
        />
      </div>
      <div className="form-field">
        <label className="form-field__label" htmlFor={`${idPrefix}-phone`}>
          {label_org_settings("field.contact_phone", "Contact Phone")}
        </label>
        <input
          id={`${idPrefix}-phone`}
          className="form-field__input"
          type="tel"
          value={contact.contact_phone}
          onChange={set("contact_phone")}
        />
      </div>
    </fieldset>
  );
}

export function Step2Contacts({ initial, onNext, onBack }: Props): React.JSX.Element {
  const label_onboarding = useLabels("onboarding");
  const label_org_settings = useLabels("org_settings");
  const [primary, setPrimary] = useState<ContactData>(
    initial?.primary ?? emptyContact("PRIMARY")
  );
  const [secondary, setSecondary] = useState<ContactData>(
    initial?.secondary ?? emptyContact("SECONDARY")
  );

  const canProceed =
    primary.contact_name.trim().length > 0 && primary.contact_email.trim().length > 0;

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (canProceed) onNext({ primary, secondary });
  };

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      {/* FIX: was label_shared("onboarding_s", "onboarding_s")2_title */}
      <h2 className="onboarding-step__title">
        {label_onboarding("step2.title", "Contact Persons")}
      </h2>

      <ContactFieldset
        legend={label_org_settings("contact.primary", "Primary Contact")}
        contact={primary}
        idPrefix="primary-contact"
        onChange={setPrimary}
      />
      <ContactFieldset
        legend={label_org_settings("contact.secondary", "Secondary Contact")}
        contact={secondary}
        idPrefix="secondary-contact"
        onChange={setSecondary}
      />

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_onboarding("btn.prev", "Previous")}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {label_onboarding("btn.continue", "Continue")}
        </button>
      </div>
    </form>
  );
}