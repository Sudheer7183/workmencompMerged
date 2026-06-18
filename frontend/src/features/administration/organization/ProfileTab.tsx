/**
 * ProfileTab — GET/PUT /api/v1/tenant/profile
 *
 * Phase 7BCD redesign: wrapped in org-settings__section card with
 * header / body / footer regions. Form fields and API logic unchanged.
 *
 * Fix retained: API null fields normalised to "" at load time so
 * controlled inputs are never set to null.
 */

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TenantProfile {
  display_name:  string;
  legal_name:    string;
  address_line1: string | null;
  address_line2: string | null;
  city:          string | null;
  state_code:    string | null;
  zip_code:      string | null;
}

interface ProfileFormState {
  display_name:  string;
  legal_name:    string;
  address_line1: string;
  address_line2: string;
  city:          string;
  state_code:    string;
  zip_code:      string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const EMPTY_FORM: ProfileFormState = {
  display_name:  "",
  legal_name:    "",
  address_line1: "",
  address_line2: "",
  city:          "",
  state_code:    "",
  zip_code:      "",
};

function normalise(profile: TenantProfile): ProfileFormState {
  return {
    display_name:  profile.display_name  ?? "",
    legal_name:    profile.legal_name    ?? "",
    address_line1: profile.address_line1 ?? "",
    address_line2: profile.address_line2 ?? "",
    city:          profile.city          ?? "",
    state_code:    profile.state_code    ?? "",
    zip_code:      profile.zip_code      ?? "",
  };
}

async function fetchProfile(): Promise<TenantProfile> {
  const { data } = await axios.get<TenantProfile>("/api/v1/tenant/profile");
  return data;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ProfileTab(): React.JSX.Element {
  const label       = useLabels("org_settings");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<TenantProfile>({
    queryKey: ["tenant-profile"],
    queryFn:  fetchProfile,
  });

  const [form, setForm] = useState<ProfileFormState>(EMPTY_FORM);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm(normalise(data));
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: ProfileFormState) => axios.put("/api/v1/tenant/profile", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const set =
    (key: keyof ProfileFormState) =>
    (e: React.ChangeEvent<HTMLInputElement>): void =>
      setForm((prev) => ({ ...prev, [key]: e.target.value }));

  if (isLoading) return <p>{labelShared("loading", "Loading…")}</p>;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate(form);
      }}
    >
      {/* Organisation Identity */}
      <div className="org-settings__section">
        <div className="org-settings__section-header">
          <h2 className="org-settings__section-title">
            {label("section.identity", "Organisation Identity")}
          </h2>
          <p className="org-settings__section-subtitle">
            {label(
              "section.identity_subtitle",
              "The display name appears throughout the platform. The legal name is used on reports and documents."
            )}
          </p>
        </div>

        <div className="org-settings__section-body">
          {saved && (
            <div className="alert alert--success" role="status">
              {label("msg.save_success", "Changes saved successfully.")}
            </div>
          )}

          <div className="form-field">
            <label className="form-field__label" htmlFor="prof-display-name">
              {label("field.display_name", "Display Name")}
            </label>
            <input
              id="prof-display-name"
              className="form-field__input"
              type="text"
              value={form.display_name}
              onChange={set("display_name")}
              maxLength={100}
              required
            />
            <p className="org-settings__char-counter" aria-live="polite">
              {form.display_name.length}/100
            </p>
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="prof-legal-name">
              {label("field.legal_name", "Legal Name")}
            </label>
            <input
              id="prof-legal-name"
              className="form-field__input"
              type="text"
              value={form.legal_name}
              onChange={set("legal_name")}
              required
            />
          </div>
        </div>
      </div>

      {/* Mailing Address */}
      <div className="org-settings__section" style={{ marginTop: "var(--space-5)" }}>
        <div className="org-settings__section-header">
          <h2 className="org-settings__section-title">
            {label("section.address", "Mailing Address")}
          </h2>
        </div>

        <div className="org-settings__section-body">
          <div className="form-field">
            <label className="form-field__label" htmlFor="prof-addr1">
              {label("field.address_line1", "Address Line 1")}
            </label>
            <input
              id="prof-addr1"
              className="form-field__input"
              type="text"
              value={form.address_line1}
              onChange={set("address_line1")}
            />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="prof-addr2">
              {label("field.address_line2", "Address Line 2")}
            </label>
            <input
              id="prof-addr2"
              className="form-field__input"
              type="text"
              value={form.address_line2}
              onChange={set("address_line2")}
            />
          </div>

          <div className="org-settings__address-row">
            <div className="form-field">
              <label className="form-field__label" htmlFor="prof-city">
                {label("field.city", "City")}
              </label>
              <input
                id="prof-city"
                className="form-field__input"
                type="text"
                value={form.city}
                onChange={set("city")}
              />
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="prof-state">
                {label("field.state", "State")}
              </label>
              <input
                id="prof-state"
                className="form-field__input"
                type="text"
                maxLength={2}
                value={form.state_code}
                onChange={set("state_code")}
              />
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="prof-zip">
                {label("field.zip", "ZIP")}
              </label>
              <input
                id="prof-zip"
                className="form-field__input"
                type="text"
                value={form.zip_code}
                onChange={set("zip_code")}
              />
            </div>
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
