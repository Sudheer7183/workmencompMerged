/**
 * CreateUserModal — Phase 7B redesign.
 * Two grouped sections: Personal Details + Role & Permissions.
 * Role options render with description text.
 * Field-level inline error messages.
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

type AssignableRole = "AUDITOR" | "REVIEWER";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function CreateUserModal({ onClose, onCreated }: Props): React.JSX.Element {
  const label = useLabels("create_user");
  const labelUsers = useLabels("users");
  const labelShared = useLabels("shared");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<AssignableRole>("AUDITOR");
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Field-level validation
  const errors: Record<string, string> = {};
  if (touched.firstName && !firstName.trim()) {
    errors.firstName = label("validation_first_name_required", "First name is required.");
  }
  if (touched.lastName && !lastName.trim()) {
    errors.lastName = label("validation_last_name_required", "Last name is required.");
  }
  if (touched.email && !email.trim()) {
    errors.email = label("validation_email_required", "Email address is required.");
  } else if (touched.email && !EMAIL_REGEX.test(email.trim())) {
    errors.email = label("validation_email_invalid", "Please enter a valid email address.");
  }

  const canSubmit =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    EMAIL_REGEX.test(email.trim()) &&
    Object.keys(errors).length === 0;

  const handleBlur = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Mark all touched
    setTouched({ firstName: true, lastName: true, email: true });
    if (!canSubmit) return;
    setServerError(null);
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
      setServerError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ??
              labelShared("error_generic", "Something went wrong. Please try again.")
          : labelShared("error_generic", "Something went wrong. Please try again.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const ROLE_OPTIONS: { value: AssignableRole; labelKey: string; defaultLabel: string; descKey: string; defaultDesc: string }[] = [
    {
      value: "AUDITOR",
      labelKey: "role.auditor",
      defaultLabel: "Auditor",
      descKey: "role_auditor_description",
      defaultDesc: "Can upload files and trigger calculations.",
    },
    {
      value: "REVIEWER",
      labelKey: "role.reviewer",
      defaultLabel: "Reviewer",
      descKey: "role_reviewer_description",
      defaultDesc: "Read-only. Can view policies and reports.",
    },
  ];

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="create-user-title">
      <div className="modal">
        <div className="modal__header">
          <h2 className="modal__title" id="create-user-title">
            {labelUsers("modal.create_title", "Create User")}
          </h2>
          <button type="button" className="modal__close" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </div>

        <form className="modal__body" onSubmit={(e) => void handleSubmit(e)} noValidate>
          {serverError && (
            <div className="alert alert--error" role="alert">
              {serverError}
            </div>
          )}

          {/* Personal Details section */}
          <div className="modal__section">
            <h3 className="modal__section-title">
              {label("section_personal", "Personal Details")}
            </h3>

            <div className="modal__name-row">
              <div className="form-field">
                <label className="form-field__label" htmlFor="cu-first">
                  {label("label_first_name", "First Name")}
                </label>
                <input
                  id="cu-first"
                  className={`form-field__input${errors.firstName ? " form-field__input--error" : ""}`}
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  onBlur={() => handleBlur("firstName")}
                  autoComplete="given-name"
                  data-testid="input-first-name"
                />
                {errors.firstName && (
                  <p className="form-field__error" role="alert">{errors.firstName}</p>
                )}
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="cu-last">
                  {label("label_last_name", "Last Name")}
                </label>
                <input
                  id="cu-last"
                  className={`form-field__input${errors.lastName ? " form-field__input--error" : ""}`}
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  onBlur={() => handleBlur("lastName")}
                  autoComplete="family-name"
                  data-testid="input-last-name"
                />
                {errors.lastName && (
                  <p className="form-field__error" role="alert">{errors.lastName}</p>
                )}
              </div>
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="cu-email">
                {label("label_email", "Email Address")}
              </label>
              <input
                id="cu-email"
                className={`form-field__input${errors.email ? " form-field__input--error" : ""}`}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onBlur={() => handleBlur("email")}
                autoComplete="email"
                data-testid="input-email"
              />
              {errors.email && (
                <p className="form-field__error" role="alert">{errors.email}</p>
              )}
            </div>
          </div>

          {/* Role & Permissions section */}
          <div className="modal__section">
            <h3 className="modal__section-title">
              {label("section_role", "Role & Permissions")}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {ROLE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`modal__role-option${role === opt.value ? " modal__role-option--selected" : ""}`}
                  data-testid={`role-option-${opt.value.toLowerCase()}`}
                >
                  <div className="modal__role-option-header">
                    <input
                      type="radio"
                      name="role"
                      value={opt.value}
                      checked={role === opt.value}
                      onChange={() => setRole(opt.value)}
                    />
                    <span className="modal__role-option-label">
                      {labelUsers(opt.labelKey, opt.defaultLabel)}
                    </span>
                  </div>
                  <p className="modal__role-option-description">
                    {label(opt.descKey, opt.defaultDesc)}
                  </p>
                </label>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="modal__footer">
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              {label("btn_cancel", "Cancel")}
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={submitting}
              data-testid="btn-send-invitation"
            >
              {submitting
                ? labelShared("loading", "Loading…")
                : label("btn_send_invitation", "Send Invitation →")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
