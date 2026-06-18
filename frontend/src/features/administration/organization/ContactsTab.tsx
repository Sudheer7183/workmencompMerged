/**
 * ContactsTab — GET/PUT /api/v1/tenant/contacts
 *
 * Phase 7BCD redesign: PRIMARY and SECONDARY contacts rendered side-by-side
 * inside an org-settings__section card using a contact-grid layout.
 * API logic and form fields unchanged.
 */

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TenantContact {
  contact_type:  "PRIMARY" | "SECONDARY";
  contact_name:  string;
  contact_email: string;
  contact_phone: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const EMPTY_CONTACT = (type: "PRIMARY" | "SECONDARY"): TenantContact => ({
  contact_type:  type,
  contact_name:  "",
  contact_email: "",
  contact_phone: "",
});

async function fetchContacts(): Promise<TenantContact[]> {
  const { data } = await axios.get<TenantContact[]>("/api/v1/tenant/contacts");
  return data;
}

// ── Sub-component: single contact fieldset ────────────────────────────────────

function ContactFields({
  title,
  contact,
  onChange,
  showEmailHelper = false,
}: {
  title: string;
  contact: TenantContact;
  onChange: (updated: TenantContact) => void;
  showEmailHelper?: boolean;
}): React.JSX.Element {
  const label = useLabels("org_settings");

  const set =
    (key: keyof TenantContact) =>
    (e: React.ChangeEvent<HTMLInputElement>): void =>
      onChange({ ...contact, [key]: e.target.value });

  return (
    <fieldset className="org-settings__field-group">
      <legend className="org-settings__field-group-label">{title}</legend>
      <div className="form-field">
        <label className="form-field__label">{label("field.contact_name", "Contact Name")}</label>
        <input
          className="form-field__input"
          type="text"
          value={contact.contact_name}
          onChange={set("contact_name")}
          required
        />
      </div>
      <div className="form-field">
        <label className="form-field__label">{label("field.contact_email", "Contact Email")}</label>
        <input
          className="form-field__input"
          type="email"
          value={contact.contact_email}
          onChange={set("contact_email")}
          required
        />
        {showEmailHelper && (
          <p className="org-settings__field-helper">
            {label(
              "field.contact_email_helper",
              "Used for system notifications and audit result delivery."
            )}
          </p>
        )}
      </div>
      <div className="form-field">
        <label className="form-field__label">{label("field.contact_phone", "Contact Phone")}</label>
        <input
          className="form-field__input"
          type="tel"
          value={contact.contact_phone ?? ""}
          onChange={set("contact_phone")}
        />
      </div>
    </fieldset>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ContactsTab(): React.JSX.Element {
  const label       = useLabels("org_settings");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<TenantContact[]>({
    queryKey: ["tenant-contacts"],
    queryFn:  fetchContacts,
  });

  const [primary,   setPrimary]   = useState<TenantContact>(EMPTY_CONTACT("PRIMARY"));
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

  if (isLoading) return <p>{labelShared("loading", "Loading…")}</p>;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate([primary, secondary]);
      }}
    >
      <div className="org-settings__section">
        <div className="org-settings__section-header">
          <h2 className="org-settings__section-title">
            {label("section.contacts", "Contact Details")}
          </h2>
          <p className="org-settings__section-subtitle">
            {label(
              "section.contacts_subtitle",
              "Primary and secondary contacts are used for billing and audit communications."
            )}
          </p>
        </div>

        <div className="org-settings__section-body">
          {saved && (
            <div className="alert alert--success" role="status">
              {label("msg.save_success", "Changes saved successfully.")}
            </div>
          )}

          <div className="org-settings__contact-grid">
            <ContactFields
              title={label("contact.primary", "Primary Contact")}
              contact={primary}
              onChange={setPrimary}
              showEmailHelper={true}
            />
            <ContactFields
              title={label("contact.secondary", "Secondary Contact")}
              contact={secondary}
              onChange={setSecondary}
            />
          </div>
        </div>

        <div className="org-settings__section-footer">
          <button
            type="submit"
            className="btn btn--primary"
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? labelShared("loading", "Loading…")
              : label("btn.save", "Save Changes")}
          </button>
        </div>
      </div>
    </form>
  );
}
