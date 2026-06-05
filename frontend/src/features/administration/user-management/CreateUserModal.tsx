/**
 * CreateUserModal — POST /api/v1/tenant/users
 * Role selector limited to AUDITOR and REVIEWER (V9 S13.2, S25).
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

type AssignableRole = "AUDITOR" | "REVIEWER";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export function CreateUserModal({ onClose, onCreated }: Props): React.JSX.Element {
  const labels = useLabels();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<AssignableRole>("AUDITOR");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const canSubmit =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    EMAIL_REGEX.test(email.trim());

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      await axios.post("/api/v1/tenant/users", {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        role,
      });
      onCreated();
    } catch (err: unknown) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? labels.error_generic
          : labels.error_generic
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal__header">
          <h2 className="modal__title">{labels.users_create_title}</h2>
          <button type="button" className="modal__close" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </div>

        <form className="modal__body" onSubmit={(e) => void handleSubmit(e)}>
          {error && <div className="alert alert--error" role="alert">{error}</div>}

          <div className="form-field">
            <label className="form-field__label" htmlFor="cu-first">
              {labels.users_field_first_name}
            </label>
            <input id="cu-first" className="form-field__input" type="text"
              value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="cu-last">
              {labels.users_field_last_name}
            </label>
            <input id="cu-last" className="form-field__input" type="text"
              value={lastName} onChange={(e) => setLastName(e.target.value)} required />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="cu-email">
              {labels.users_field_email}
            </label>
            <input id="cu-email" className="form-field__input" type="email"
              value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="cu-role">
              {labels.users_field_role}
            </label>
            {/* Role selector intentionally limited to AUDITOR and REVIEWER (V9 S25) */}
            <select id="cu-role" className="form-field__select"
              value={role} onChange={(e) => setRole(e.target.value as AssignableRole)}>
              <option value="AUDITOR">{labels.users_role_auditor}</option>
              <option value="REVIEWER">{labels.users_role_reviewer}</option>
            </select>
          </div>

          <div className="modal__footer">
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              {labels.users_btn_cancel}
            </button>
            <button type="submit" className="btn btn--primary" disabled={!canSubmit || submitting}>
              {submitting ? labels.loading : labels.users_create_title}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
