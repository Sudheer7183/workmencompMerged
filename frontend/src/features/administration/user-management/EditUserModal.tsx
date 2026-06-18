/**
 * EditUserPanel — Phase 7BCD redesign.
 *
 * Replaced the modal with a right-side slide-in user-edit-panel BEM block.
 * Sections: Identity (read-only), Role & Permissions, Danger Zone.
 * All strings via useLabels(). No style={{}} props.
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

// Keep old export name for backwards compatibility with any imports using EditUserModal
export { EditUserPanel as EditUserModal };

export function EditUserPanel({ user, onClose, onUpdated }: Props): React.JSX.Element {
  const labelOrgSettings = useLabels("org_settings");
  const labelShared = useLabels("shared");
  const labelUsers = useLabels("users");

  const [role, setRole] = useState<AssignableRole>(
    user.role === "REVIEWER" ? "REVIEWER" : "AUDITOR"
  );
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSave = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await axios.patch(`/api/v1/tenant/users/${user.user_id}`, { role });
      onUpdated();
    } catch (err: unknown) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ??
              labelShared("error_generic", "Something went wrong. Please try again.")
          : labelShared("error_generic", "Something went wrong. Please try again.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (): Promise<void> => {
    setError(null);
    setSubmitting(true);
    try {
      await axios.delete(`/api/v1/tenant/users/${user.user_id}`);
      onUpdated();
    } catch (err: unknown) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ??
              labelShared("error_generic", "Something went wrong. Please try again.")
          : labelShared("error_generic", "Something went wrong. Please try again.")
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="user-edit-panel" role="dialog" aria-modal="true">
      <div
        className="user-edit-panel__backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="user-edit-panel__drawer">
        {/* Header */}
        <div className="user-edit-panel__header">
          <h2 className="user-edit-panel__title">
            {labelUsers("modal.edit_title", "Edit User")}
          </h2>
          <button
            type="button"
            className="user-edit-panel__close"
            aria-label={labelShared("btn.close", "Close")}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="user-edit-panel__body">
          {error && (
            <div className="alert alert--error" role="alert" style={{ margin: "var(--space-4) var(--space-6) 0" }}>
              {error}
            </div>
          )}

          {/* Identity section — read-only */}
          <div className="user-edit-panel__section">
            <p className="user-edit-panel__section-title">
              {labelUsers("section.identity", "Identity")}
            </p>
            <p className="user-edit-panel__identity-name">
              {user.first_name} {user.last_name}
            </p>
            <p className="user-edit-panel__identity-email">{user.email}</p>
          </div>

          {/* Role & Permissions section */}
          <form
            id="user-edit-form"
            className="user-edit-panel__section"
            onSubmit={(e) => void handleSave(e)}
          >
            <p className="user-edit-panel__section-title">
              {labelUsers("section.role", "Role & Permissions")}
            </p>

            <div className="form-field">
              <label className="form-field__label" htmlFor="uep-role">
                {labelUsers("field.role", "Role")}
              </label>
              <select
                id="uep-role"
                className="form-field__select"
                value={role}
                onChange={(e) => setRole(e.target.value as AssignableRole)}
              >
                <option value="AUDITOR">
                  {labelUsers("role.auditor", "Auditor")}
                </option>
                <option value="REVIEWER">
                  {labelUsers("role.reviewer", "Reviewer")}
                </option>
              </select>
            </div>
          </form>

          {/* Danger zone */}
          <div className="user-edit-panel__danger-zone">
            <p className="user-edit-panel__danger-title">
              {labelUsers("section.danger_zone", "Danger Zone")}
            </p>
            {!confirmDeactivate ? (
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={() => setConfirmDeactivate(true)}
              >
                {labelUsers("btn.deactivate", "Deactivate User")}
              </button>
            ) : (
              <div className="user-edit-panel__danger-confirm">
                <p className="user-edit-panel__danger-text">
                  {labelUsers(
                    "modal.deactivate_confirm",
                    "Are you sure you want to deactivate this user? They will lose access immediately."
                  )}
                </p>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <button
                    type="button"
                    className="btn btn--danger btn--sm"
                    onClick={() => void handleDeactivate()}
                    disabled={submitting}
                  >
                    {labelUsers("btn.deactivate", "Confirm Deactivate")}
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => setConfirmDeactivate(false)}
                  >
                    {labelUsers("btn.cancel", "Cancel")}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="user-edit-panel__footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            {labelUsers("btn.cancel", "Cancel")}
          </button>
          <button
            type="submit"
            form="user-edit-form"
            className="btn btn--primary"
            disabled={submitting}
          >
            {submitting
              ? labelShared("loading", "Loading…")
              : labelOrgSettings("btn.save", "Save Changes")}
          </button>
        </div>
      </div>
    </div>
  );
}
