/**
 * AddCarrierModal — POST /platform/carriers.
 *
 * Phase 7BCD redesign: replaced modal with carrier-create-panel (slide-in drawer).
 * Supports create mode and edit mode (pre-populated, slug read-only).
 * Used from CarriersList.
 */

import React, { useState, useEffect } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

export interface CarrierFormData {
  carrier_id?: number;
  name: string;
  slug: string;
  ai_narrative_enabled: boolean;
}

interface Props {
  /** When provided, panel opens in edit mode pre-populated with these values. */
  editCarrier?: CarrierFormData;
  onClose: () => void;
  onCreated: () => void;
}

export function AddCarrierModal({ editCarrier, onClose, onCreated }: Props): React.JSX.Element {
  const label = useLabels("platform_admin");
  const labelShared = useLabels("shared");
  const labelUsers = useLabels("users");

  const isEditMode = editCarrier != null;

  const [carrierName, setCarrierName] = useState(editCarrier?.name ?? "");
  const [carrierSlug, setCarrierSlug] = useState(editCarrier?.slug ?? "");
  const [aiEnabled, setAiEnabled] = useState(editCarrier?.ai_narrative_enabled ?? false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Auto-generate slug from name in create mode only
  useEffect(() => {
    if (!isEditMode && carrierName) {
      setCarrierSlug(
        carrierName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
      );
    }
  }, [carrierName, isEditMode]);

  const canSubmit = carrierName.trim().length > 0 && carrierSlug.trim().length > 0;

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      if (isEditMode && editCarrier?.carrier_id) {
        await axios.patch(`/platform/carriers/${editCarrier.carrier_id}`, {
          carrier_name: carrierName.trim(),
          ai_narrative_enabled: aiEnabled,
        });
      } else {
        await axios.post("/platform/carriers", {
          carrier_name: carrierName.trim(),
          slug: carrierSlug.trim().toLowerCase().replace(/[^a-z0-9]/g, "-"),
          ai_narrative_enabled: aiEnabled,
        });
      }
      onCreated();
    } catch (err: unknown) {
      const extractDetail = (): string => {
        if (!axios.isAxiosError(err))
          return labelShared("error_generic", "Something went wrong. Please try again.");
        const detail = (err.response?.data as { detail?: unknown })?.detail;
        if (!detail)
          return labelShared("error_generic", "Something went wrong. Please try again.");
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail) && detail.length > 0) {
          const first = detail[0] as { msg?: string; loc?: string[] };
          const loc = first.loc?.slice(1).join(" → ") ?? "";
          return loc
            ? `${loc}: ${first.msg ?? "Invalid value"}`
            : (first.msg ?? labelShared("error_generic", "Something went wrong. Please try again."));
        }
        return labelShared("error_generic", "Something went wrong. Please try again.");
      };
      setError(extractDetail());
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="carrier-create-panel" role="dialog" aria-modal="true">
      <div
        className="carrier-create-panel__backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="carrier-create-panel__drawer">
        {/* Header */}
        <div className="carrier-create-panel__header">
          <h2 className="carrier-create-panel__title">
            {isEditMode
              ? label("carrier.edit_title", "Edit Carrier")
              : label("btn.new_carrier", "Add Carrier")}
          </h2>
          <button
            type="button"
            className="carrier-create-panel__close"
            aria-label={labelShared("btn.close", "Close")}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <form
          className="carrier-create-panel__body"
          onSubmit={(e) => void handleSubmit(e)}
          id="carrier-form"
        >
          {error && (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          )}

          <div className="form-field">
            <label className="form-field__label" htmlFor="cp-carrier-name">
              {label("col.name", "Carrier Name")}
            </label>
            <input
              id="cp-carrier-name"
              className="form-field__input"
              type="text"
              value={carrierName}
              onChange={(e) => setCarrierName(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="cp-slug">
              {label("carrier.slug_label", "Slug / Identifier")}
            </label>
            <input
              id="cp-slug"
              className="form-field__input"
              type="text"
              value={carrierSlug}
              onChange={(e) =>
                !isEditMode &&
                setCarrierSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))
              }
              readOnly={isEditMode}
              maxLength={63}
              placeholder="e.g. demo-carrier"
              required
            />
            {isEditMode && (
              <p className="carrier-create-panel__readonly-hint">
                {label("carrier.slug_immutable", "Slug cannot be changed after creation.")}
              </p>
            )}
          </div>

          <div className="form-field">
            <label className="form-field__label">
              {label("carrier.ai_narrative_label", "AI Narrative")}
            </label>
            <label className="toggle-label">
              <input
                type="checkbox"
                className="toggle-input"
                checked={aiEnabled}
                onChange={(e) => setAiEnabled(e.target.checked)}
              />
              <span className="toggle-track" />
              <span className="toggle-text">
                {aiEnabled
                  ? label("carrier.ai_enabled", "Enabled")
                  : label("carrier.ai_disabled", "Disabled")}
              </span>
            </label>
          </div>
        </form>

        {/* Footer */}
        <div className="carrier-create-panel__footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            {labelUsers("btn.cancel", "Cancel")}
          </button>
          <button
            type="submit"
            form="carrier-form"
            className="btn btn--primary"
            disabled={!canSubmit || submitting}
          >
            {submitting
              ? labelShared("loading", "Loading…")
              : isEditMode
              ? label("carrier.btn_save", "Save Changes")
              : label("btn.new_carrier", "Add Carrier")}
          </button>
        </div>
      </div>
    </div>
  );
}
