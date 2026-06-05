/**
 * AddCarrierModal — POST /platform/carriers.
 * Used both from CarriersList and Step3CarrierAssign.
 */

import React, { useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export function AddCarrierModal({ onClose, onCreated }: Props): React.JSX.Element {
  const labels = useLabels();
  const [carrierName, setCarrierName] = useState("");
  const [carrierCode, setCarrierCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = carrierName.trim().length > 0 && carrierCode.trim().length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
        await axios.post("/platform/carriers", {
                name: carrierName.trim(),
                slug: carrierCode.trim().toLowerCase().replace(/[^a-z0-9]/g, "-"),
                ai_narrative_enabled: false,
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
          <h2 className="modal__title">{labels.platform_btn_new_carrier}</h2>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <form className="modal__body" onSubmit={(e) => void handleSubmit(e)}>
          {error && (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          )}

          <div className="form-field">
            <label className="form-field__label" htmlFor="carrier-name">
              {labels.platform_col_name}
            </label>
            <input
              id="carrier-name"
              className="form-field__input"
              type="text"
              value={carrierName}
              onChange={(e) => setCarrierName(e.target.value)}
              required
            />
          </div>

          <div className="form-field">
            <label className="form-field__label" htmlFor="carrier-code">
              Slug <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(lowercase, hyphens only)</span>
            </label>
            <input
              id="carrier-code"
              className="form-field__input"
              type="text"
              value={carrierCode}
              onChange={(e) => setCarrierCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
              maxLength={63}
              placeholder="e.g. demo-carrier"
              required
            />
          </div>

          <div className="modal__footer">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={onClose}
            >
              {labels.users_btn_cancel}
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={!canSubmit || submitting}
            >
              {submitting ? labels.loading : labels.platform_btn_new_carrier}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
