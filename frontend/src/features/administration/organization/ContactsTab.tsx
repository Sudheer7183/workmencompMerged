/**
 * ContactsTab — GET/PUT /api/v1/tenant/contacts
 * Manages PRIMARY and SECONDARY contacts.
 */

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface TenantContact {
  contact_type: "PRIMARY" | "SECONDARY";
  contact_name: string;
  contact_email: string;
  contact_phone: string | null;
}

async function fetchContacts(): Promise<TenantContact[]> {
  const { data } = await axios.get<TenantContact[]>("/api/v1/tenant/contacts");
  return data;
}

const EMPTY_CONTACT = (type: "PRIMARY" | "SECONDARY"): TenantContact => ({
  contact_type: type,
  contact_name: "",
  contact_email: "",
  contact_phone: "",
});

function ContactForm({
  label,
  contact,
  onChange,
}: {
  label: string;
  contact: TenantContact;
  onChange: (updated: TenantContact) => void;
}) {
  const labels = useLabels();
  const set =
    (key: keyof TenantContact) =>
    (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange({ ...contact, [key]: e.target.value });

  return (
    <fieldset className="contact-form">
      <legend className="contact-form__legend">{label}</legend>
      <div className="form-field">
        <label className="form-field__label">{labels.org_field_contact_name}</label>
        <input className="form-field__input" type="text"
          value={contact.contact_name} onChange={set("contact_name")} required />
      </div>
      <div className="form-field">
        <label className="form-field__label">{labels.org_field_contact_email}</label>
        <input className="form-field__input" type="email"
          value={contact.contact_email} onChange={set("contact_email")} required />
      </div>
      <div className="form-field">
        <label className="form-field__label">{labels.org_field_contact_phone}</label>
        <input className="form-field__input" type="tel"
          value={contact.contact_phone ?? ""} onChange={set("contact_phone")} />
      </div>
    </fieldset>
  );
}

export function ContactsTab(): React.JSX.Element {
  const labels = useLabels();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TenantContact[]>({
    queryKey: ["tenant-contacts"],
    queryFn: fetchContacts,
  });

  const [primary, setPrimary] = useState<TenantContact>(EMPTY_CONTACT("PRIMARY"));
  const [secondary, setSecondary] = useState<TenantContact>(EMPTY_CONTACT("SECONDARY"));
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    const pri = data.find((c) => c.contact_type === "PRIMARY");
    const sec = data.find((c) => c.contact_type === "SECONDARY");
    if (pri) setPrimary(pri);
    if (sec) setSecondary(sec);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (contacts: TenantContact[]) =>
      axios.put("/api/v1/tenant/contacts", contacts),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-contacts"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  if (isLoading) return <p>{labels.loading}</p>;

  return (
    <form
      className="contacts-tab"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate([primary, secondary]);
      }}
    >
      {saved && (
        <div className="alert alert--success" role="status">
          {labels.org_save_success}
        </div>
      )}
      <ContactForm
        label={labels.org_contact_primary}
        contact={primary}
        onChange={setPrimary}
      />
      <ContactForm
        label={labels.org_contact_secondary}
        contact={secondary}
        onChange={setSecondary}
      />
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? labels.loading : labels.org_btn_save}
        </button>
      </div>
    </form>
  );
}
