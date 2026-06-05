/**
 * ProfileTab — GET/PUT /api/v1/tenant/profile
 * Fields: display_name, legal_name, address.
 */

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface TenantProfile {
  display_name: string;
  legal_name: string;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state_code: string | null;
  zip_code: string | null;
}

async function fetchProfile(): Promise<TenantProfile> {
  const { data } = await axios.get<TenantProfile>("/api/v1/tenant/profile");
  return data;
}

export function ProfileTab(): React.JSX.Element {
  const labels = useLabels();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TenantProfile>({
    queryKey: ["tenant-profile"],
    queryFn: fetchProfile,
  });

  const [form, setForm] = useState<TenantProfile>({
    display_name: "",
    legal_name: "",
    address_line1: "",
    address_line2: "",
    city: "",
    state_code: "",
    zip_code: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: TenantProfile) => axios.put("/api/v1/tenant/profile", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const set = (key: keyof TenantProfile) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  if (isLoading) return <p>{labels.loading}</p>;

  return (
    <form
      className="profile-tab"
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(form); }}
    >
      {saved && (
        <div className="alert alert--success" role="status">
          {labels.org_save_success}
        </div>
      )}

      <div className="form-field">
        <label className="form-field__label" htmlFor="display-name">
          {labels.org_field_display_name}
        </label>
        <input id="display-name" className="form-field__input" type="text"
          value={form.display_name} onChange={set("display_name")} required />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="legal-name">
          {labels.org_field_legal_name}
        </label>
        <input id="legal-name" className="form-field__input" type="text"
          value={form.legal_name} onChange={set("legal_name")} required />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="addr1">
          {labels.org_field_address_line1}
        </label>
        <input id="addr1" className="form-field__input" type="text"
          value={form.address_line1 ?? ""} onChange={set("address_line1")} />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="addr2">
          {labels.org_field_address_line2}
        </label>
        <input id="addr2" className="form-field__input" type="text"
          value={form.address_line2 ?? ""} onChange={set("address_line2")} />
      </div>

      <div className="form-row">
        <div className="form-field">
          <label className="form-field__label" htmlFor="city">{labels.org_field_city}</label>
          <input id="city" className="form-field__input" type="text"
            value={form.city ?? ""} onChange={set("city")} />
        </div>
        <div className="form-field form-field--sm">
          <label className="form-field__label" htmlFor="state">{labels.org_field_state}</label>
          <input id="state" className="form-field__input" type="text"
            maxLength={2} value={form.state_code ?? ""} onChange={set("state_code")} />
        </div>
        <div className="form-field form-field--sm">
          <label className="form-field__label" htmlFor="zip">{labels.org_field_zip}</label>
          <input id="zip" className="form-field__input" type="text"
            value={form.zip_code ?? ""} onChange={set("zip_code")} />
        </div>
      </div>

      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? labels.loading : labels.org_btn_save}
        </button>
      </div>
    </form>
  );
}
