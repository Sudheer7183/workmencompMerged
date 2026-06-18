/**
 * BrandingTab — Logo upload + brand_color hex input.
 *
 * Phase 7BCD redesign: wrapped in org-settings__section cards with
 * separate Logo and Brand Colour sections.
 *
 * API calls and file handling logic unchanged from Phase 2.
 * V9 S14 / Phase 2 scope — full ThemeEditor is Phase 6.
 */

import React, { useState, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BrandingResponse {
  logo_url:      string | null;
  logo_dark_url: string | null;
  brand_color:   string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/svg+xml"];
const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5 MB
const HEX_6_REGEX = /^[0-9a-fA-F]{6}$/;

async function fetchBranding(): Promise<BrandingResponse> {
  const { data } = await axios.get<BrandingResponse>("/api/v1/tenant/branding");
  return data;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function BrandingTab(): React.JSX.Element {
  const label       = useLabels("org_settings");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: branding } = useQuery<BrandingResponse>({
    queryKey: ["tenant-branding"],
    queryFn:  fetchBranding,
  });

  const [brandColor, setBrandColor] = useState(branding?.brand_color ?? "");
  const [colorError, setColorError] = useState<string | null>(null);
  const [dragOver,   setDragOver]   = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(branding?.logo_url ?? null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [savedColor,  setSavedColor]  = useState(false);

  React.useEffect(() => {
    if (branding?.brand_color != null) setBrandColor(branding.brand_color);
    if (branding?.logo_url    != null) setPreviewUrl(branding.logo_url);
  }, [branding]);

  // ── Logo upload ─────────────────────────────────────────────────────────

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await axios.post<{ logo_url: string }>(
        "/api/v1/tenant/branding/logo",
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data.logo_url;
    },
    onSuccess: (url) => {
      setPreviewUrl(url);
      setUploadError(null);
      void qc.invalidateQueries({ queryKey: ["tenant-branding"] });
    },
    onError: (err: unknown) => {
      setUploadError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ??
              labelShared("error_generic", "Something went wrong. Please try again.")
          : labelShared("error_generic", "Something went wrong. Please try again.")
      );
    },
  });

  const handleFile = useCallback(
    (file: File | null | undefined): void => {
      if (!file) return;
      if (!ALLOWED_TYPES.includes(file.type)) {
        setUploadError(label("branding.file_type_error", "Only PNG, JPG, and SVG files are accepted."));
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setUploadError(label("branding.file_size_error", "File exceeds the 5 MB size limit."));
        return;
      }
      setUploadError(null);
      uploadMutation.mutate(file);
    },
    [uploadMutation, label]
  );

  const onDrop = (e: React.DragEvent): void => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // ── Brand colour ────────────────────────────────────────────────────────

  const colorMutation = useMutation({
    mutationFn: (color: string) =>
      axios.put("/api/v1/tenant/branding", { brand_color: color || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-branding"] });
      setSavedColor(true);
      setTimeout(() => setSavedColor(false), 3000);
    },
  });

  const handleColorSave = (e: React.FormEvent): void => {
    e.preventDefault();
    if (brandColor && !HEX_6_REGEX.test(brandColor)) {
      setColorError(label("branding.color_format_error", "Enter a 6-character hex value, e.g. 4ade80"));
      return;
    }
    setColorError(null);
    colorMutation.mutate(brandColor);
  };

  return (
    <div className="org-settings__tab-panel">
      {/* ── Logo section ─────────────────────────────────────────────────── */}
      <div className="org-settings__section">
        <div className="org-settings__section-header">
          <h2 className="org-settings__section-title">
            {label("branding.logo", "Organisation Logo")}
          </h2>
          <p className="org-settings__section-subtitle">
            {label(
              "branding.logo_hint_detailed",
              "Accepted formats: PNG, JPG, SVG. Max size: 2MB. Displayed in reports and the navigation header."
            )}
          </p>
        </div>

        <div className="org-settings__section-body">
          {uploadError && (
            <div className="alert alert--error" role="alert">{uploadError}</div>
          )}

          {previewUrl && (
            <div className="branding-tab__preview">
              <img
                src={previewUrl}
                alt={label("branding.logo_preview_alt", "Logo preview")}
                className="branding-tab__logo-img"
              />
            </div>
          )}

          <div
            className={`drop-zone ${dragOver ? "drop-zone--over" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={label("branding.drag_drop", "Drag and drop a file, or click to browse")}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => { if (e.key === "Enter") fileInputRef.current?.click(); }}
          >
            <p className="drop-zone__label">
              {uploadMutation.isPending
                ? labelShared("loading", "Loading…")
                : label("branding.drag_drop", "Drag and drop a file, or click to browse")}
            </p>
            <button type="button" className="btn btn--secondary btn--sm">
              {label("branding.upload_btn", "Upload Logo")}
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,.svg"
            className="drop-zone__input"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>
      </div>

      {/* ── Brand colour section ──────────────────────────────────────────── */}
      <div className="org-settings__section">
        <div className="org-settings__section-header">
          <h2 className="org-settings__section-title">
            {label("branding.brand_color", "Brand Colour")}
          </h2>
          <p className="org-settings__section-subtitle">
            {label("branding.brand_color_hint", "6-character hex value (e.g. 4ade80)")}
          </p>
        </div>

        <form onSubmit={handleColorSave}>
          <div className="org-settings__section-body">
            {savedColor && (
              <div className="alert alert--success" role="status">
                {label("msg.save_success", "Changes saved successfully.")}
              </div>
            )}

            <div className="form-field">
              <label className="form-field__label" htmlFor="brand-color-hex">
                {label("branding.brand_color", "Brand Colour")}
              </label>
              <div className="branding-tab__color-input-row">
                <span className="branding-tab__color-hash">#</span>
                <input
                  id="brand-color-hex"
                  className={`form-field__input form-field__input--mono ${
                    colorError ? "form-field__input--error" : ""
                  }`}
                  type="text"
                  value={brandColor}
                  onChange={(e) => { setBrandColor(e.target.value); setColorError(null); }}
                  maxLength={6}
                  placeholder="4ade80"
                  aria-label={label("branding.brand_color", "Brand Colour")}
                />
                {brandColor && HEX_6_REGEX.test(brandColor) && (
                  <span
                    className="org-settings__color-swatch"
                    style={{ ["--org-swatch-color" as string]: `#${brandColor}` } as React.CSSProperties}
                    aria-label={label("branding.color_swatch_label", "Brand colour preview")}
                  />
                )}
              </div>
              {colorError && (
                <p className="form-field__error" role="alert">{colorError}</p>
              )}
            </div>
          </div>

          <div className="org-settings__section-footer">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={colorMutation.isPending}
            >
              {colorMutation.isPending
                ? labelShared("loading", "Loading…")
                : label("btn.save", "Save Changes")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
