/**
 * ThemeImportExport — Phase 6 Theme Tab component.
 *
 * Addendum S9: JSON theme import and export workflow.
 *
 * Export: GET /api/v1/admin/themes/{theme_id}/export → JSON file download.
 * Import: POST /api/v1/admin/themes/import (preview) →
 *         then POST /api/v1/admin/themes (save).
 */

import React, { useRef, useState } from "react";
import axios from "axios";

interface ThemeImportPreview {
  theme_name: string;
  mode: string;
  based_on_name: string | null;
  tokens: Record<string, string>;
}

interface ThemeImportExportProps {
  carrierId: number;
  /** Called after a theme is successfully imported and saved. */
  onImported: () => void;
}

export function ThemeImportExport({
  carrierId,
  onImported,
}: ThemeImportExportProps): React.JSX.Element {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<ThemeImportPreview | null>(null);
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImporting(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await axios.post<ThemeImportPreview>(
        "/api/v1/admin/themes/import",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setPreview(data);
    } catch (err: unknown) {
      const msg =
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? "Import failed.")
          : "Import failed.";
      setError(String(msg));
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleSaveImport = async () => {
    if (!preview) return;
    setSaving(true);
    setError(null);

    try {
      await axios.post("/api/v1/admin/themes", {
        theme_name: preview.theme_name,
        mode: preview.mode,
        based_on_name: preview.based_on_name,
        ...preview.tokens,
      });
      setPreview(null);
      onImported();
    } catch (err: unknown) {
      const msg =
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? "Save failed.")
          : "Save failed.";
      setError(String(msg));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="theme-import-export">
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        style={{ display: "none" }}
        onChange={handleImportFile}
      />

      <button
        type="button"
        className="theme-tab__btn"
        onClick={() => fileInputRef.current?.click()}
        disabled={importing}
      >
        {importing ? "Reading…" : "Import JSON"}
      </button>

      {error && (
        <p style={{ color: "var(--color-red)", fontSize: "var(--text-sm)", margin: 0 }}>
          {error}
        </p>
      )}

      {/* Import preview modal-like inline panel */}
      {preview && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 300,
          }}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: "var(--space-5)",
              minWidth: 360,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
            }}
          >
            <h3 style={{ margin: 0, color: "var(--text-primary)" }}>Import Theme Preview</h3>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-primary)" }}>
              <p style={{ margin: "0 0 var(--space-1)" }}>
                <strong>Name:</strong> {preview.theme_name}
              </p>
              <p style={{ margin: "0 0 var(--space-1)" }}>
                <strong>Mode:</strong> {preview.mode}
              </p>
              {preview.based_on_name && (
                <p style={{ margin: "0 0 var(--space-1)" }}>
                  <strong>Based on:</strong> {preview.based_on_name}
                </p>
              )}
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-1)",
                  marginTop: "var(--space-2)",
                  flexWrap: "wrap",
                }}
              >
                {Object.entries(preview.tokens).map(([field, hex]) => (
                  <div
                    key={field}
                    title={`${field}: #${hex}`}
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 3,
                      backgroundColor: `#${hex}`,
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                ))}
              </div>
            </div>
            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="theme-tab__btn"
                onClick={() => setPreview(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="theme-tab__btn theme-tab__btn--primary"
                onClick={handleSaveImport}
                disabled={saving}
              >
                {saving ? "Saving…" : "Save Theme"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
