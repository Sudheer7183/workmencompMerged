/**
 * BrandingTab — Logo upload + brand_color hex input.
 *
 * V9 S14 / Phase 2 scope:
 * - Logo: drag-drop zone (PNG/JPG/SVG, 5 MB max), preview after upload.
 *   Uploads via POST /api/v1/tenant/branding/logo (multipart/form-data).
 * - brand_color: 6-char hex text input. PUT /api/v1/tenant/branding.
 * - Full ThemeEditor (all tokens) is Phase 6 — NOT included here.
 */

import React, { useState, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface BrandingResponse {
  logo_url: string | null;
  logo_dark_url: string | null;
  brand_color: string | null;
}

async function fetchBranding(): Promise<BrandingResponse> {
  const { data } = await axios.get<BrandingResponse>("/api/v1/tenant/branding");
  return data;
}

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/svg+xml"];
const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5 MB
const HEX_6_REGEX = /^[0-9a-fA-F]{6}$/;

export function BrandingTab(): React.JSX.Element {
  const labels = useLabels();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: branding } = useQuery<BrandingResponse>({
    queryKey: ["tenant-branding"],
    queryFn: fetchBranding,
  });

  const [brandColor, setBrandColor] = useState(branding?.brand_color ?? "");
  const [colorError, setColorError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(branding?.logo_url ?? null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [savedColor, setSavedColor] = useState(false);

  // Sync initial brand_color from query
  React.useEffect(() => {
    if (branding?.brand_color != null) setBrandColor(branding.brand_color);
    if (branding?.logo_url != null) setPreviewUrl(branding.logo_url);
  }, [branding]);

  // ── Logo upload ───────────────────────────────────────────────────────────
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
          ? (err.response?.data as { detail?: string })?.detail ?? labels.error_generic
          : labels.error_generic
      );
    },
  });

  const handleFile = useCallback(
    (file: File | null | undefined) => {
      if (!file) return;
      if (!ALLOWED_TYPES.includes(file.type)) {
        setUploadError("Only PNG, JPG, and SVG files are accepted.");
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setUploadError("File exceeds the 5 MB size limit.");
        return;
      }
      setUploadError(null);
      uploadMutation.mutate(file);
    },
    [uploadMutation]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // ── Brand color ───────────────────────────────────────────────────────────
  const colorMutation = useMutation({
    mutationFn: (color: string) =>
      axios.put("/api/v1/tenant/branding", { brand_color: color || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-branding"] });
      setSavedColor(true);
      setTimeout(() => setSavedColor(false), 3000);
    },
  });

  const handleColorSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (brandColor && !HEX_6_REGEX.test(brandColor)) {
      setColorError("Enter a 6-character hex value, e.g. 4ade80");
      return;
    }
    setColorError(null);
    colorMutation.mutate(brandColor);
  };

  return (
    <div className="branding-tab">
      {/* Logo section */}
      <section className="branding-tab__section">
        <h3 className="branding-tab__section-title">{labels.org_branding_logo}</h3>
        <p className="branding-tab__hint">{labels.org_branding_logo_hint}</p>

        {uploadError && (
          <div className="alert alert--error" role="alert">{uploadError}</div>
        )}

        {previewUrl && (
          <div className="branding-tab__preview">
            <img
              src={previewUrl}
              alt="Logo preview"
              className="branding-tab__logo-img"
            />
          </div>
        )}

        {/* Drag-drop zone */}
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
            {uploadMutation.isPending ? labels.loading : labels.org_branding_drag_drop}
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
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </section>

      {/* Brand colour section */}
      <section className="branding-tab__section">
        <h3 className="branding-tab__section-title">{labels.org_branding_brand_color}</h3>
        <p className="branding-tab__hint">{labels.org_branding_brand_color_hint}</p>

        <form className="branding-tab__color-form" onSubmit={handleColorSave}>
          {savedColor && (
            <div className="alert alert--success" role="status">
              {labels.org_save_success}
            </div>
          )}
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
            {colorError && (
              <p className="form-field__error" role="alert">{colorError}</p>
            )}
          </div>
          <div className="form-actions">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={colorMutation.isPending}
            >
              {colorMutation.isPending ? labels.loading : labels.org_btn_save}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
