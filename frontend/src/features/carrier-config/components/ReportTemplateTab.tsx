/**
 * ReportTemplateTab.tsx — Phase 5
 *
 * Tab 5 of CarrierConfigHub (replaces ComingSoonTab phase={5}).
 * Manages carrier_report_templates: logo upload, colour pickers, contact block.
 *
 * Per V9 S15.2 Tab 5.
 *
 * Fields:
 *   - Report Logo: drag-drop / file picker → POST /tenant/branding/report-logo/{carrierId}
 *   - Primary Colour: 6-char hex input + live swatch
 *   - Secondary Colour: 6-char hex input + live swatch
 *   - Contact Block (HTML): textarea, max 1000 chars, rendered in PDF footer
 *   - PDF Preview: generates a book_summary PDF and opens in new tab
 *   - Save Template: PUT /admin/report-template/{carrierId}
 */

import React, { useEffect, useRef, useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import {
  getReportTemplate,
  generateReport,
  putReportTemplate,
  uploadReportLogo,
  type ReportTemplate,
} from "../../reports/services/reportsApi";
import { getReportStatus } from "../../reports/services/reportsApi";

interface ReportTemplateTabProps {
  carrierId: number;
}

const HEX_REGEX = /^[0-9a-fA-F]{6}$/;

export function ReportTemplateTab({
  carrierId,
}: ReportTemplateTabProps): React.JSX.Element {
  const label_reports = useLabels("reports");
  const label_shared = useLabels("shared");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [uploadingLogo, setUploadingLogo] = useState<boolean>(false);
  const [previewing, setPreviewing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [primaryColour, setPrimaryColour] = useState<string>("1A3C5E");
  const [secondaryColour, setSecondaryColour] = useState<string>("2E86C1");
  const [contactBlock, setContactBlock] = useState<string>("");

  const [primaryColourError, setPrimaryColourError] = useState<string | null>(
    null
  );
  const [secondaryColourError, setSecondaryColourError] = useState<
    string | null
  >(null);

  // Load existing template on mount
  useEffect(() => {
    async function load(): Promise<void> {
      setLoading(true);
      try {
        const tmpl: ReportTemplate = await getReportTemplate(carrierId);
        setLogoUrl(tmpl.logo_url ?? null);
        setPrimaryColour(tmpl.primary_colour ?? "1A3C5E");
        setSecondaryColour(tmpl.secondary_colour ?? "2E86C1");
        setContactBlock(tmpl.contact_block ?? "");
      } catch {
        setError(label_reports("template.load_error", "report_template_load_error") ?? "Failed to load template.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [carrierId, label_reports("template.load_error", "report_template_load_error")]);

  // ── Logo upload ────────────────────────────────────────────────────────────
  async function handleLogoChange(
    e: React.ChangeEvent<HTMLInputElement>
  ): Promise<void> {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const result = await uploadReportLogo(carrierId, file);
      setLogoUrl(result.logo_url);
    } catch {
      setError(label_reports("template.logo_upload_error", "report_logo_upload_error") ?? "Failed to upload logo.");
    } finally {
      setUploadingLogo(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // ── Colour validation ──────────────────────────────────────────────────────
  function handlePrimaryColourChange(value: string): void {
    // Strip # if user pastes with it
    const stripped = value.replace(/^#/, "");
    setPrimaryColour(stripped);
    setPrimaryColourError(
      HEX_REGEX.test(stripped)
        ? null
        : (label_reports("template.colour_invalid", "report_colour_invalid") ?? "Must be a 6-character hex code (e.g. 1A3C5E)")
    );
  }

  function handleSecondaryColourChange(value: string): void {
    const stripped = value.replace(/^#/, "");
    setSecondaryColour(stripped);
    setSecondaryColourError(
      HEX_REGEX.test(stripped)
        ? null
        : (label_reports("template.colour_invalid", "report_colour_invalid") ?? "Must be a 6-character hex code (e.g. 2E86C1)")
    );
  }

  // ── Save template ──────────────────────────────────────────────────────────
  async function handleSave(): Promise<void> {
    if (primaryColourError || secondaryColourError) return;
    setSaving(true);
    setSaveSuccess(false);
    setError(null);
    try {
      await putReportTemplate(carrierId, {
        logo_url: logoUrl || null,
        primary_colour: primaryColour || null,
        secondary_colour: secondaryColour || null,
        contact_block: contactBlock || null,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } catch {
      setError(label_reports("template.save_error", "report_template_save_error") ?? "Failed to save template.");
    } finally {
      setSaving(false);
    }
  }

  // ── PDF Preview ────────────────────────────────────────────────────────────
  async function handlePdfPreview(): Promise<void> {
    setPreviewing(true);
    setError(null);
    try {
      const { job_id } = await generateReport({
        carrier_id: carrierId,
        report_type: "book_summary",
        output_format: "pdf",
      });
      // Poll until complete, then open
      let attempts = 0;
      const maxAttempts = 40; // 40 × 3s = 2 minutes
      const interval = setInterval(async () => {
        attempts++;
        try {
          const statusData = await getReportStatus(job_id);
          if (statusData.status === "COMPLETE" && statusData.file_url) {
            clearInterval(interval);
            setPreviewing(false);
            window.open(statusData.file_url, "_blank", "noopener,noreferrer");
          } else if (statusData.status === "FAILED" || attempts >= maxAttempts) {
            clearInterval(interval);
            setPreviewing(false);
            setError(
              statusData.error_detail ??
                (label_reports("template.preview_failed", "report_preview_failed") ?? "PDF preview failed.")
            );
          }
        } catch {
          clearInterval(interval);
          setPreviewing(false);
        }
      }, 3000);
    } catch {
      setPreviewing(false);
      setError(label_reports("template.preview_failed", "report_preview_failed") ?? "Failed to start PDF preview.");
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="report-template-tab">
        <p className="text-muted">{label_shared("loading", "Loading…") ?? "Loading…"}</p>
      </div>
    );
  }

  return (
    <div
      className="report-template-tab"
      data-testid="report-template-tab"
    >
      {error && (
        <div className="alert alert--error" role="alert">
          {error}
        </div>
      )}

      {/* ── Logo ──────────────────────────────────────────────────────────── */}
      <section className="report-template-tab__section">
        <h3 className="report-template-tab__section-title">
          {label_reports("template.logo_section", "report_template_logo_section") ?? "Report Logo"}
        </h3>
        <div className="report-template-tab__logo-zone">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={label_reports("template.logo_preview_alt", "report_logo_preview_alt") ?? "Logo preview"}
              className="report-template-tab__logo-preview"
            />
          ) : (
            <div className="report-template-tab__logo-placeholder">
              {label_reports("template.logo_using_tenant", "report_logo_using_tenant") ??
                "Using tenant branding logo (not set)"}
            </div>
          )}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={(e) => void handleLogoChange(e)}
            />
            <button
              type="button"
              className="btn btn--secondary"
              disabled={uploadingLogo}
              onClick={() => fileInputRef.current?.click()}
              data-testid="logo-upload-btn"
            >
              {uploadingLogo
                ? (label_shared("uploading", "uploading") ?? "Uploading…")
                : (label_reports("template.logo_upload", "report_logo_upload") ?? "Upload Logo")}
            </button>
            {logoUrl && (
              <button
                type="button"
                className="btn btn--ghost"
                style={{ marginLeft: "8px" }}
                onClick={() => setLogoUrl(null)}
              >
                {label_shared("remove", "remove") ?? "Remove"}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* ── Colours ───────────────────────────────────────────────────────── */}
      <section className="report-template-tab__section">
        <h3 className="report-template-tab__section-title">
          {label_reports("template.colours_section", "report_template_colours_section") ?? "Brand Colours"}
        </h3>
        <div className="report-template-tab__colour-row">
          {/* Primary colour */}
          <div className="report-template-tab__colour-field">
            <label className="form-label" htmlFor="primaryColour">
              {label_reports("template.primary_colour", "report_primary_colour") ?? "Primary Colour"}
            </label>
            <div className="report-template-tab__colour-input-row">
              <span
                className="report-template-tab__colour-swatch"
                style={{
                  backgroundColor: HEX_REGEX.test(primaryColour)
                    ? `#${primaryColour}`
                    : "transparent",
                }}
                aria-hidden="true"
              />
              <input
                id="primaryColour"
                type="text"
                className="input"
                value={primaryColour}
                maxLength={6}
                placeholder="1A3C5E"
                onChange={(e) => handlePrimaryColourChange(e.target.value)}
                data-testid="primary-colour-input"
              />
            </div>
            {primaryColourError && (
              <p className="form-error">{primaryColourError}</p>
            )}
          </div>

          {/* Secondary colour */}
          <div className="report-template-tab__colour-field">
            <label className="form-label" htmlFor="secondaryColour">
              {label_reports("template.secondary_colour", "report_secondary_colour") ?? "Secondary Colour"}
            </label>
            <div className="report-template-tab__colour-input-row">
              <span
                className="report-template-tab__colour-swatch"
                style={{
                  backgroundColor: HEX_REGEX.test(secondaryColour)
                    ? `#${secondaryColour}`
                    : "transparent",
                }}
                aria-hidden="true"
              />
              <input
                id="secondaryColour"
                type="text"
                className="input"
                value={secondaryColour}
                maxLength={6}
                placeholder="2E86C1"
                onChange={(e) => handleSecondaryColourChange(e.target.value)}
                data-testid="secondary-colour-input"
              />
            </div>
            {secondaryColourError && (
              <p className="form-error">{secondaryColourError}</p>
            )}
          </div>
        </div>
      </section>

      {/* ── Contact block ─────────────────────────────────────────────────── */}
      <section className="report-template-tab__section">
        <h3 className="report-template-tab__section-title">
          {label_reports("template.contact_block_section", "report_contact_block_section") ?? "Footer Contact Block (HTML)"}
        </h3>
        <textarea
          className="report-template-tab__contact-area"
          value={contactBlock}
          maxLength={1000}
          rows={4}
          placeholder="e.g. <p>123 Main St · audit@company.com</p>"
          onChange={(e) => setContactBlock(e.target.value)}
          data-testid="contact-block-input"
          aria-label={label_reports("template.contact_block_section", "report_contact_block_section") ?? "Contact block HTML"}
        />
        <p className="form-hint">
          {contactBlock.length}
          {label_reports("template.contact_block_char_limit", "report_contact_block_char_limit") ?? " / 1000 characters. Rendered in the PDF report footer."}
        </p>
      </section>

      {/* ── Actions ───────────────────────────────────────────────────────── */}
      <div className="report-template-tab__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={
            saving ||
            !!primaryColourError ||
            !!secondaryColourError
          }
          onClick={() => void handleSave()}
          data-testid="save-template-btn"
        >
          {saving
            ? (label_shared("saving", "saving") ?? "Saving…")
            : (label_reports("template.save", "report_save_template") ?? "Save Template")}
        </button>

        <button
          type="button"
          className="btn btn--secondary"
          disabled={previewing}
          onClick={() => void handlePdfPreview()}
          data-testid="pdf-preview-btn"
        >
          {previewing
            ? (label_reports("template.previewing", "report_previewing") ?? "Generating preview…")
            : (label_reports("template.pdf_preview", "report_pdf_preview") ?? "PDF Preview")}
        </button>

        {saveSuccess && (
          <span
            className="report-template-tab__save-success"
            data-testid="save-success-toast"
            role="status"
          >
            {label_shared("saved", "saved") ?? "✓ Saved"}
          </span>
        )}
      </div>
    </div>
  );
}
