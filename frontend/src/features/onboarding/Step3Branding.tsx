/**
 * Onboarding Step 3 — Logo drag-drop + brand_color hex input.
 *
 * - Logo: drag-drop zone (PNG/JPG/SVG, 5 MB), preview after successful upload.
 * - brand_color: 6-char hex text input — stored WITHOUT leading "#".
 * - Full ThemeEditor is Phase 6.
 */

import React, { useState, useRef, useCallback } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

export interface BrandingData {
  logoUrl: string | null;
  brandColor: string;
}

interface Props {
  initial: BrandingData | null;
  onNext: (data: BrandingData) => void;
  onBack: () => void;
}

const ALLOWED_MIME = ["image/png", "image/jpeg", "image/svg+xml"];
const MAX_BYTES = 5 * 1024 * 1024;
const HEX_6_REGEX = /^[0-9a-fA-F]{6}$/;

export function Step3Branding({ initial, onNext, onBack }: Props): React.JSX.Element {
  const labels = useLabels();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(initial?.logoUrl ?? null);
  const [brandColor, setBrandColor] = useState(initial?.brandColor ?? "");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [colorError, setColorError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (file: File | null | undefined) => {
    if (!file) return;
    if (!ALLOWED_MIME.includes(file.type)) {
      setUploadError("Only PNG, JPG, and SVG files are accepted.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setUploadError("File exceeds the 5 MB size limit.");
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await axios.post<{ logo_url: string }>(
        "/api/v1/tenant/branding/logo",
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setLogoUrl(data.logo_url);
    } catch (err: unknown) {
      setUploadError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? labels.error_generic
          : labels.error_generic
      );
    } finally {
      setUploading(false);
    }
  }, [labels]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    void handleFile(e.dataTransfer.files[0]);
  };

  const handleNext = () => {
    if (brandColor && !HEX_6_REGEX.test(brandColor)) {
      setColorError("Enter a 6-character hex value, e.g. 4ade80");
      return;
    }
    setColorError(null);
    onNext({ logoUrl, brandColor });
  };

  return (
    <div className="onboarding-step">
      <h2 className="onboarding-step__title">{labels.onboarding_s3_title}</h2>

      {/* Logo upload */}
      <section className="onboarding-step__section">
        <h3 className="onboarding-step__section-title">{labels.org_branding_logo}</h3>
        <p className="onboarding-step__hint">{labels.org_branding_logo_hint}</p>

        {uploadError && <div className="alert alert--error" role="alert">{uploadError}</div>}

        {logoUrl && (
          <div className="branding-tab__preview">
            <img src={logoUrl} alt="Logo preview" className="branding-tab__logo-img" />
          </div>
        )}

        <div
          className={`drop-zone ${dragOver ? "drop-zone--over" : ""}`}
          role="button"
          tabIndex={0}
          aria-label={labels.org_branding_drag_drop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === "Enter") fileInputRef.current?.click(); }}
        >
          <p className="drop-zone__label">
            {uploading ? labels.loading : labels.org_branding_drag_drop}
          </p>
          <button type="button" className="btn btn--secondary btn--sm">
            {labels.org_branding_upload_btn}
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.svg"
          className="drop-zone__input"
          data-testid="file-upload-input"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
      </section>

      {/* Brand colour */}
      <section className="onboarding-step__section">
        <h3 className="onboarding-step__section-title">{labels.org_branding_brand_color}</h3>
        <p className="onboarding-step__hint">{labels.org_branding_brand_color_hint}</p>
        <div className="form-field">
          <div className="branding-tab__color-input-row">
            <span className="branding-tab__color-hash">#</span>
            <input
              className={`form-field__input form-field__input--mono ${colorError ? "form-field__input--error" : ""}`}
              type="text"
              value={brandColor}
              onChange={(e) => { setBrandColor(e.target.value); setColorError(null); }}
              maxLength={6}
              placeholder="4ade80"
              aria-label={labels.org_branding_brand_color}
            />
            {brandColor && HEX_6_REGEX.test(brandColor) && (
              <span
                className="branding-tab__color-swatch"
                style={{ backgroundColor: `#${brandColor}` }}
                data-testid="file-upload-input"
              />
            )}
          </div>
          {colorError && <p className="form-field__error" role="alert">{colorError}</p>}
        </div>
      </section>

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.onboarding_btn_prev}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleNext}
          disabled={uploading}
        >
          {labels.onboarding_btn_continue}
        </button>
      </div>
    </div>
  );
}
