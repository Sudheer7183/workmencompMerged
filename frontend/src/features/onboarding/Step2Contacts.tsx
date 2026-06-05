/**
 * Onboarding Step 2 — PRIMARY and SECONDARY contact forms.
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
}) {
  const labels = useLabels();
  const set = (key: keyof ContactData) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...contact, [key]: e.target.value });

  return (
    <fieldset className="contact-form">
      <legend className="contact-form__legend">{legend}</legend>
      <div className="form-field">
        <label className="form-field__label" htmlFor={`${idPrefix}-name`}>
          {labels.org_field_contact_name}
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
          {labels.org_field_contact_email}
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
          {labels.org_field_contact_phone}
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
  const labels = useLabels();
  const [primary, setPrimary] = useState<ContactData>(
    initial?.primary ?? emptyContact("PRIMARY")
  );
  const [secondary, setSecondary] = useState<ContactData>(
    initial?.secondary ?? emptyContact("SECONDARY")
  );

  const canProceed =
    primary.contact_name.trim().length > 0 && primary.contact_email.trim().length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canProceed) onNext({ primary, secondary });
  };

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      <h2 className="onboarding-step__title">{labels.onboarding_s2_title}</h2>
      <ContactFieldset
        legend={labels.org_contact_primary}
        contact={primary}
        idPrefix="primary-contact"
        onChange={setPrimary}
      />
      <ContactFieldset
        legend={labels.org_contact_secondary}
        contact={secondary}
        idPrefix="secondary-contact"
        onChange={setSecondary}
      />
      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.onboarding_btn_prev}
        </button>
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {labels.onboarding_btn_continue}
        </button>
      </div>
    </form>
  );
}
