/**
 * AuditRunnerPage — Phase 3 (updated).
 *
 * Ingestion mode toggle:
 *   • "calc_engine"  (Application 2) — raw files, calculations run
 *   • "display_only" (Application 1) — pre-calculated display files
 *
 * When calc_engine is active, two upload types are available:
 *   Type 1 — XML + Payroll XLSX + Audit Report XLSX (3 files)
 *   Type 2 — Payroll XLSX + Audit Report XLSX only  (2 files, no XML)
 *
 * Each file is uploaded individually. The last upload's session_id
 * drives the FieldMappingReview screen.
 */

import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { uploadFile, type IngestionMode } from "./services/ingestionApi";

// ── Types ─────────────────────────────────────────────────────────────────────

type UploadType = "type1" | "type2";

interface FileSlot {
  id: string;
  label: string;
  accept: string;
  hint: string;
  required: boolean;
  file: File | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildSlots(uploadType: UploadType): FileSlot[] {
  if (uploadType === "type1") {
    return [
      {
        id: "xml",
        label: "XML Audit Report",
        accept: ".xml,text/xml,application/xml",
        hint: "Policy config — class codes, exposure, dates",
        required: true,
        file: null,
      },
      {
        id: "payroll",
        label: "Payroll Detail XLSX",
        accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        hint: "Per-employee payroll rows",
        required: true,
        file: null,
      },
      {
        id: "audit",
        label: "Audit Summary Report XLSX",
        accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        hint: "Audit report with classification detail",
        required: true,
        file: null,
      },
    ];
  }
  // Type 2 — no XML
  return [
    {
      id: "payroll",
      label: "Payroll Detail XLSX",
      accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      hint: "Per-employee payroll rows",
      required: true,
      file: null,
    },
    {
      id: "audit",
      label: "Audit Summary Report XLSX",
      accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      hint: "Audit report with classification detail",
      required: true,
      file: null,
    },
  ];
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AuditRunnerPage(): React.JSX.Element {
  const labels = useLabels();
  const navigate = useNavigate();
  const { carrierId } = useTenantCarrier();

  const [ingestionMode, setIngestionMode] = useState<IngestionMode>("calc_engine");
  const [uploadType, setUploadType] = useState<UploadType>("type2");
  const [slots, setSlots] = useState<FileSlot[]>(() => buildSlots("type2"));
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // One hidden file input per slot
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ── Mode / type switching ───────────────────────────────────────────────────

  function handleModeChange(mode: IngestionMode): void {
    setIngestionMode(mode);
    setErrorMessage(null);
    // display_only uses a single file slot like the original behaviour
    if (mode === "display_only") {
      setSlots([
        {
          id: "display",
          label: "Pre-calculated Report XLSX",
          accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          hint: "Pre-calculated display file",
          required: true,
          file: null,
        },
      ]);
    } else {
      const newType = uploadType;
      setSlots(buildSlots(newType));
    }
  }

  function handleUploadTypeChange(type: UploadType): void {
    setUploadType(type);
    setSlots(buildSlots(type));
    setErrorMessage(null);
  }

  // ── File selection ──────────────────────────────────────────────────────────

  function handleFileSelect(slotId: string, file: File | null): void {
    setSlots((prev) =>
      prev.map((s) => (s.id === slotId ? { ...s, file } : s))
    );
    setErrorMessage(null);
  }

  function handleInputChange(
    slotId: string,
    e: React.ChangeEvent<HTMLInputElement>
  ): void {
    handleFileSelect(slotId, e.target.files?.[0] ?? null);
  }

  function handleDrop(
    slotId: string,
    e: React.DragEvent<HTMLDivElement>
  ): void {
    e.preventDefault();
    const file = e.dataTransfer.files[0] ?? null;
    if (file) handleFileSelect(slotId, file);
  }

  function handleRemoveFile(slotId: string): void {
    handleFileSelect(slotId, null);
    // Reset the underlying input so the same file can be re-selected
    const input = inputRefs.current[slotId];
    if (input) input.value = "";
  }

  // ── Submit ──────────────────────────────────────────────────────────────────

  async function handleSubmit(): Promise<void> {
    const requiredSlots = slots.filter((s) => s.required);
    const missing = requiredSlots.filter((s) => !s.file);
    if (missing.length > 0) {
      setErrorMessage(
        `Please select: ${missing.map((s) => s.label).join(", ")}`
      );
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    let lastRunId = 0;
    let lastSessionId = 0;

    try {
      for (let i = 0; i < slots.length; i++) {
        const slot = slots[i];
        if (!slot.file) continue;

        setUploadProgress(
          `Uploading ${i + 1} of ${slots.length}: ${slot.label}…`
        );

        const response = await uploadFile(
          carrierId,
          1,
          slot.file,
          ingestionMode
        );
        lastRunId = response.run_id;
        lastSessionId = response.session_id;
      }

      navigate(`/audit-runner/${lastRunId}/mapping`, {
        state: { sessionId: lastSessionId, runId: lastRunId },
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : labels.upload_error ?? "Upload failed. Please try again.";
      setErrorMessage(message);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  const allRequiredFilled = slots
    .filter((s) => s.required)
    .every((s) => s.file !== null);

  return (
    <div className="audit-runner">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="audit-runner__header">
        <h1 className="audit-runner__title">
          {labels.audit_runner_title ?? "Audit Runner"}
        </h1>
        <p className="audit-runner__subtitle">
          {labels.audit_runner_subtitle ??
            "Upload carrier data files to begin the audit ingestion pipeline."}
        </p>
      </div>

      <div className="audit-runner__card">

        {/* ── Ingestion Mode Toggle ────────────────────────────────────── */}
        <div className="ingest-toggle">
          <span className="ingest-toggle__label">Pipeline Mode</span>
          <div className="ingest-toggle__pills" role="group" aria-label="Ingestion mode">
            <button
              type="button"
              className={[
                "ingest-toggle__pill",
                ingestionMode === "calc_engine"
                  ? "ingest-toggle__pill--active"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => handleModeChange("calc_engine")}
              aria-pressed={ingestionMode === "calc_engine"}
            >
              <span className="ingest-toggle__pill-dot" />
              Calculation Engine
            </button>
            <button
              type="button"
              className={[
                "ingest-toggle__pill",
                ingestionMode === "display_only"
                  ? "ingest-toggle__pill--active ingest-toggle__pill--display"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => handleModeChange("display_only")}
              aria-pressed={ingestionMode === "display_only"}
            >
              <span className="ingest-toggle__pill-dot" />
              Display Only
            </button>
          </div>
          <p className="ingest-toggle__hint">
            {ingestionMode === "calc_engine"
              ? "Raw files — premium and variance calculated by the engine"
              : "Pre-calculated files — values displayed as-is"}
          </p>
        </div>

        {/* ── Upload Type selector (calc_engine only) ──────────────────── */}
        {ingestionMode === "calc_engine" && (
          <div className="upload-type">
            <span className="upload-type__label">Upload Type</span>
            <div className="upload-type__options">
              <label className="upload-type__option">
                <input
                  type="radio"
                  name="upload_type"
                  value="type2"
                  checked={uploadType === "type2"}
                  onChange={() => handleUploadTypeChange("type2")}
                  className="upload-type__radio"
                />
                <span className="upload-type__option-body">
                  <span className="upload-type__option-name">
                    Type 2 — 2 Files
                  </span>
                  <span className="upload-type__option-desc">
                    Payroll XLSX + Audit Report XLSX
                  </span>
                </span>
              </label>
              <label className="upload-type__option">
                <input
                  type="radio"
                  name="upload_type"
                  value="type1"
                  checked={uploadType === "type1"}
                  onChange={() => handleUploadTypeChange("type1")}
                  className="upload-type__radio"
                />
                <span className="upload-type__option-body">
                  <span className="upload-type__option-name">
                    Type 1 — 3 Files
                  </span>
                  <span className="upload-type__option-desc">
                    XML + Payroll XLSX + Audit Report XLSX
                  </span>
                </span>
              </label>
            </div>
          </div>
        )}

        {/* ── File Slots ───────────────────────────────────────────────── */}
        <div className="file-slots">
          {slots.map((slot) => (
            <div
              key={slot.id}
              className={[
                "file-slot",
                slot.file ? "file-slot--filled" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <div className="file-slot__header">
                <span className="file-slot__label">{slot.label}</span>
                <span className="file-slot__hint">{slot.hint}</span>
              </div>

              {slot.file ? (
                <div className="file-slot__selected">
                  <span className="file-slot__file-icon">📄</span>
                  <span className="file-slot__file-name">{slot.file.name}</span>
                  <span className="file-slot__file-size">
                    ({(slot.file.size / 1024).toFixed(1)} KB)
                  </span>
                  <button
                    type="button"
                    className="file-slot__remove"
                    onClick={() => handleRemoveFile(slot.id)}
                    aria-label={`Remove ${slot.label}`}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div
                  className="file-slot__dropzone"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => handleDrop(slot.id, e)}
                  onClick={() => inputRefs.current[slot.id]?.click()}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select ${slot.label}`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      inputRefs.current[slot.id]?.click();
                  }}
                >
                  <span className="file-slot__dropzone-icon">⊕</span>
                  <span className="file-slot__dropzone-text">
                    Click or drag to select
                  </span>
                </div>
              )}

              <input
                ref={(el) => {
                  inputRefs.current[slot.id] = el;
                }}
                type="file"
                accept={slot.accept}
                onChange={(e) => handleInputChange(slot.id, e)}
                className="audit-runner__file-input"
                aria-hidden="true"
              />
            </div>
          ))}
        </div>

        {/* ── Progress / Error ─────────────────────────────────────────── */}
        {uploadProgress && (
          <div className="audit-runner__progress">{uploadProgress}</div>
        )}
        {errorMessage && (
          <div className="audit-runner__error" role="alert">
            {errorMessage}
          </div>
        )}

        {/* ── Submit ───────────────────────────────────────────────────── */}
        <button
          className="btn btn--primary audit-runner__submit"
          onClick={handleSubmit}
          disabled={isUploading || !allRequiredFilled}
        >
          {isUploading
            ? uploadProgress ?? "Uploading…"
            : labels.btn_upload_and_map ?? "Upload & Map Fields"}
        </button>
      </div>
    </div>
  );
}