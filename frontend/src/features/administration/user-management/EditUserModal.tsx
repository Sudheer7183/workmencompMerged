/**
 * EditUserModal — PATCH /api/v1/tenant/users/{id}
 * Allows role change (AUDITOR ↔ REVIEWER) and deactivation.
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

type AssignableRole = "AUDITOR" | "REVIEWER";

interface UserItem {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

interface Props {
  user: UserItem;
  onClose: () => void;
  onUpdated: () => void;
}

export function EditUserModal({ user, onClose, onUpdated }: Props): React.JSX.Element {
  const labels = useLabels();
  const [role, setRole] = useState<AssignableRole>(
    user.role === "REVIEWER" ? "REVIEWER" : "AUDITOR"
  );
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await axios.patch(`/api/v1/tenant/users/${user.user_id}`, { role });
      onUpdated();
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

  const handleDeactivate = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await axios.delete(`/api/v1/tenant/users/${user.user_id}`);
      onUpdated();
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
          <h2 className="modal__title">{labels.users_edit_title}</h2>
          <button type="button" className="modal__close" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </div>

        <form className="modal__body" onSubmit={(e) => void handleSave(e)}>
          {error && <div className="alert alert--error" role="alert">{error}</div>}

          <p className="modal__subtitle">{user.first_name} {user.last_name}</p>
          <p className="modal__email">{user.email}</p>

          <div className="form-field">
            <label className="form-field__label" htmlFor="eu-role">
              {labels.users_field_role}
            </label>
            <select id="eu-role" className="form-field__select"
              value={role} onChange={(e) => setRole(e.target.value as AssignableRole)}>
              <option value="AUDITOR">{labels.users_role_auditor}</option>
              <option value="REVIEWER">{labels.users_role_reviewer}</option>
            </select>
          </div>

          <div className="modal__footer">
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              {labels.users_btn_cancel}
            </button>
            <button type="submit" className="btn btn--primary" disabled={submitting}>
              {submitting ? labels.loading : labels.org_btn_save}
            </button>
          </div>
        </form>

        {/* Deactivation — separate danger zone at bottom of modal */}
        <div className="modal__danger-zone">
          {!confirmDeactivate ? (
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={() => setConfirmDeactivate(true)}
            >
              {labels.users_btn_deactivate}
            </button>
          ) : (
            <div className="modal__confirm-deactivate">
              <p className="modal__confirm-text">{labels.users_deactivate_confirm}</p>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={() => void handleDeactivate()}
                disabled={submitting}
              >
                {labels.users_btn_deactivate}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={() => setConfirmDeactivate(false)}
              >
                {labels.users_btn_cancel}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
