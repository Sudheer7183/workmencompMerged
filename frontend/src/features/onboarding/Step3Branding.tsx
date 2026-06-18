/**
 * Onboarding Step 3 — Logo drag-drop + brand_color hex input.
 *
 * - Logo: drag-drop zone (PNG/JPG/SVG, 5 MB), preview after successful upload.
 * - brand_color: 6-char hex text input — stored WITHOUT leading "#".
 * - Full ThemeEditor is Phase 6.
 *
 * Fixes applied:
 *  1. label_shared("onboarding_s", "onboarding_s")3_title  → label_onboarding("step3.title", …)
 *  2. handleFile useCallback deps had [label] — `label` was never defined; corrected to
 *     [label_shared] which is the hook actually used inside the callback.
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
  const label_onboarding = useLabels("onboarding");
  const label_org_settings = useLabels("org_settings");
  const label_shared = useLabels("shared");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(initial?.logoUrl ?? null);
  const [brandColor, setBrandColor] = useState(initial?.brandColor ?? "");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [colorError, setColorError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // FIX: deps was [label] — `label` was never in scope; corrected to [label_shared]
  const handleFile = useCallback(async (file: File | null | undefined): Promise<void> => {
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
          ? (err.response?.data as { detail?: string })?.detail
            ?? label_shared("error_generic", "Something went wrong. Please try again.")
          : label_shared("error_generic", "Something went wrong. Please try again.")
      );
    } finally {
      setUploading(false);
    }
  }, [label_shared]);

  const onDrop = (e: React.DragEvent): void => {
    e.preventDefault();
    setDragOver(false);
    void handleFile(e.dataTransfer.files[0]);
  };

  const handleNext = (): void => {
    if (brandColor && !HEX_6_REGEX.test(brandColor)) {
      setColorError("Enter a 6-character hex value, e.g. 4ade80");
      return;
    }
    setColorError(null);
    onNext({ logoUrl, brandColor });
  };

  return (
    <div className="onboarding-step">
      {/* FIX: was label_shared("onboarding_s", "onboarding_s")3_title */}
      <h2 className="onboarding-step__title">
        {label_onboarding("step3.title", "Organization Branding")}
      </h2>

      {/* Logo upload */}
      <section className="onboarding-step__section">
        <h3 className="onboarding-step__section-title">
          {label_org_settings("branding.logo", "Organisation Logo")}
        </h3>
        <p className="onboarding-step__hint">
          {label_org_settings("branding.logo_hint", "PNG, JPG, or SVG · Max 5 MB")}
        </p>

        {uploadError && (
          <div className="alert alert--error" role="alert">{uploadError}</div>
        )}

        {logoUrl && (
          <div className="branding-tab__preview">
            <img src={logoUrl} alt="Logo preview" className="branding-tab__logo-img" />
          </div>
        )}

        <div
          className={`drop-zone ${dragOver ? "drop-zone--over" : ""}`}
          role="button"
          tabIndex={0}
          aria-label={label_org_settings("branding.drag_drop", "Drag and drop a file, or click to browse")}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === "Enter") fileInputRef.current?.click(); }}
        >
          <p className="drop-zone__label">
            {uploading
              ? label_shared("loading", "Loading…")
              : label_org_settings("branding.drag_drop", "Drag and drop a file, or click to browse")}
          </p>
          <button type="button" className="btn btn--secondary btn--sm">
            {label_org_settings("branding.upload_btn", "Upload Logo")}
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
        <h3 className="onboarding-step__section-title">
          {label_org_settings("branding.brand_color", "Brand Colour")}
        </h3>
        <p className="onboarding-step__hint">
          {label_org_settings("branding.brand_color_hint", "6-character hex value (e.g. 4ade80)")}
        </p>
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
              aria-label={label_org_settings("branding.brand_color", "Brand Colour")}
            />
            {brandColor && HEX_6_REGEX.test(brandColor) && (
              <span
                className="branding-tab__color-swatch"
                style={{ backgroundColor: `#${brandColor}` }}
                aria-hidden="true"
              />
            )}
          </div>
          {colorError && (
            <p className="form-field__error" role="alert">{colorError}</p>
          )}
        </div>
      </section>

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_onboarding("btn.prev", "Previous")}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleNext}
          disabled={uploading}
        >
          {label_onboarding("btn.continue", "Continue")}
        </button>
      </div>
    </div>
  );
}