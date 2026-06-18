

import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import {
  uploadFile,
  approveMapping,
  fetchCarrierIngestionMode,
  type IngestionMode,
  type CarrierIngestionMode,
} from "./services/ingestionApi";

// ── Types ─────────────────────────────────────────────────────────────────────

type UploadType = "type1" | "type2" | "type3";

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
  if (uploadType === "type3") {
    return [
      {
        id: "csv",
        label: "CSV Data File",
        accept: ".csv,text/csv,text/plain",
        hint: "Comma/tab/semicolon separated data file",
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

function buildDisplayOnlySlot(): FileSlot[] {
  return [
    {
      id: "display",
      label: "Pre-calculated Report XLSX",
      accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      hint: "Pre-calculated display file",
      required: true,
      file: null,
    },
  ];
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AuditRunnerPage(): React.JSX.Element {
  const label = useLabels("audit_runner");
  const navigate = useNavigate();
  const { carrierId } = useTenantCarrier();

  // ── Fetch the carrier's locked ingestion mode ─────────────────────────────
  const { data: carrierModeData, isLoading: isLoadingMode } =
    useQuery<CarrierIngestionMode>({
      queryKey: ["carrier-ingestion-mode", carrierId],
      queryFn: () => fetchCarrierIngestionMode(carrierId),
      enabled: carrierId > 0,
      staleTime: 30_000,
    });

  const lockedMode = carrierModeData?.locked_mode ?? null;
  const isModeLocked = lockedMode !== null;

  // ── Local state ───────────────────────────────────────────────────────────
  // Initialise mode from locked mode once it loads; default to calc_engine
  const [ingestionMode, setIngestionMode] = useState<IngestionMode>("calc_engine");
  const [uploadType, setUploadType] = useState<UploadType>("type2");
  const [slots, setSlots] = useState<FileSlot[]>(() => buildSlots("type2"));
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync ingestionMode with the locked mode once the query resolves
  useEffect(() => {
    if (lockedMode !== null) {
      setIngestionMode(lockedMode);
      if (lockedMode === "display_only") {
        setSlots(buildDisplayOnlySlot());
      } else {
        setSlots(buildSlots(uploadType));
      }
    }
  }, [lockedMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ── Mode switching (only allowed when not locked) ─────────────────────────

  function handleModeChange(mode: IngestionMode): void {
    if (isModeLocked) return; // silently block — UI already prevents it
    setIngestionMode(mode);
    setErrorMessage(null);
    if (mode === "display_only") {
      setSlots(buildDisplayOnlySlot());
    } else {
      setSlots(buildSlots(uploadType));
    }
  }

  function handleUploadTypeChange(type: UploadType): void {
    setUploadType(type);
    setSlots(buildSlots(type));
    setErrorMessage(null);
  }

  // ── File selection ────────────────────────────────────────────────────────

  function handleFileSelect(slotId: string, file: File | null): void {
    setSlots((prev) => prev.map((s) => (s.id === slotId ? { ...s, file } : s)));
    setErrorMessage(null);
  }

  function handleInputChange(slotId: string, e: React.ChangeEvent<HTMLInputElement>): void {
    handleFileSelect(slotId, e.target.files?.[0] ?? null);
  }

  function handleDrop(slotId: string, e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    const file = e.dataTransfer.files[0] ?? null;
    if (file) handleFileSelect(slotId, file);
  }

  function handleRemoveFile(slotId: string): void {
    handleFileSelect(slotId, null);
    const input = inputRefs.current[slotId];
    if (input) input.value = "";
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  async function handleSubmit(): Promise<void> {
    const requiredSlots = slots.filter((s) => s.required);
    const missing = requiredSlots.filter((s) => !s.file);
    if (missing.length > 0) {
      setErrorMessage(`Please select: ${missing.map((s) => s.label).join(", ")}`);
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    const filledSlots = slots.filter((s) => s.file);
    const auditSlot = filledSlots.find((s) => s.id === "audit");
    const nonAuditSlots = filledSlots.filter((s) => s.id !== "audit");
    const orderedSlots = [...nonAuditSlots, ...(auditSlot ? [auditSlot] : [])];

    let lastRunId = 0;
    let lastSessionId = 0;

    try {
      for (let i = 0; i < orderedSlots.length; i++) {
        const slot = orderedSlots[i];
        const isLast = i === orderedSlots.length - 1;

        setUploadProgress(`Uploading ${i + 1} of ${orderedSlots.length}: ${slot.label}…`);

        const response = await uploadFile(carrierId, 1, slot.file!, ingestionMode);
        lastRunId = response.run_id;
        lastSessionId = response.session_id;

        if (!isLast && ingestionMode === "calc_engine") {
          setUploadProgress(`Processing ${slot.label}…`);
          await approveMapping(response.session_id);
          await new Promise((resolve) => setTimeout(resolve, 800));
        }
      }

      navigate(`/audit-runner/${lastRunId}/mapping`, {
        state: { sessionId: lastSessionId, runId: lastRunId },
      });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErrorMessage(
        detail ??
          (err instanceof Error ? err.message : null) ??
          label("upload.error", "Upload failed. Please try again.")
      );
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  }

  // ── Derived ────────────────────────────────────────────────────────────────

  const allRequiredFilled = slots.filter((s) => s.required).every((s) => s.file !== null);

  const modeHintText = isModeLocked
    ? ingestionMode === "calc_engine"
      ? "Locked — Calculation Engine. Raw files are processed by the audit engine."
      : "Locked — Display Only. Pre-calculated values are displayed as-is."
    : ingestionMode === "calc_engine"
    ? "Raw files — premium and variance calculated by the engine"
    : "Pre-calculated files — values displayed as-is";

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="audit-runner" data-testid="audit-runner">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="audit-runner__header">
        <h1 className="audit-runner__title" data-testid="audit-runner__title">
          {label("title", "Audit Runner")}
        </h1>
        <p className="audit-runner__subtitle">
          {label(
            "subtitle",
            "Upload carrier data files to begin the audit ingestion pipeline."
          )}
        </p>
      </div>

      {/* ── Single / Bulk Upload tabs ──────────────────────────────────── */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "8px" }}>
        <button
          type="button"
          className="btn btn--secondary"
          style={{
            borderBottom: "2px solid var(--brand)",
            borderRadius: "6px 6px 0 0",
            fontWeight: 600,
          }}
          disabled
        >
          Single Upload
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          style={{ borderRadius: "6px 6px 0 0" }}
          onClick={() => navigate("/bulk-upload")}
        >
          Bulk Upload (ZIP / Folder)
        </button>
      </div>

      <div className="audit-runner__card" data-testid="audit-runner__card">

        {/* ── Ingestion Mode Toggle ────────────────────────────────────── */}
        <div className="ingest-toggle" data-testid="audit-runner__mode-toggle">
          <div className="ingest-toggle__label-row">
            <span className="ingest-toggle__label">Pipeline Mode</span>
            {isModeLocked && (
              <span className="ingest-toggle__lock-badge" title="Mode is locked based on this carrier's ingestion history">
                🔒 Locked
              </span>
            )}
          </div>

          <div
            className={[
              "ingest-toggle__pills",
              isModeLocked ? "ingest-toggle__pills--locked" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            role="group"
            aria-label="Ingestion mode"
          >
            <button
              type="button"
              className={[
                "ingest-toggle__pill",
                ingestionMode === "calc_engine" ? "ingest-toggle__pill--active" : "",
                isModeLocked && ingestionMode !== "calc_engine"
                  ? "ingest-toggle__pill--locked-inactive"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => handleModeChange("calc_engine")}
              disabled={isModeLocked || isLoadingMode}
              aria-pressed={ingestionMode === "calc_engine"}
              aria-disabled={isModeLocked}
              data-testid="audit-runner__mode-calc-engine"
              title={
                isModeLocked && ingestionMode !== "calc_engine"
                  ? "This carrier is locked to Display Only mode"
                  : "Use the calculation engine pipeline"
              }
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
                isModeLocked && ingestionMode !== "display_only"
                  ? "ingest-toggle__pill--locked-inactive"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => handleModeChange("display_only")}
              disabled={isModeLocked || isLoadingMode}
              aria-pressed={ingestionMode === "display_only"}
              aria-disabled={isModeLocked}
              data-testid="audit-runner__mode-display-only"
              title={
                isModeLocked && ingestionMode !== "display_only"
                  ? "This carrier is locked to Calculation Engine mode"
                  : "Use the display-only pipeline"
              }
            >
              <span className="ingest-toggle__pill-dot" />
              Display Only
            </button>
          </div>

          <p className="ingest-toggle__hint">{modeHintText}</p>

          {isModeLocked && (
            <p className="ingest-toggle__lock-notice">
              This carrier already has ingestion history using{" "}
              <strong>
                {ingestionMode === "calc_engine" ? "Calculation Engine" : "Display Only"}
              </strong>{" "}
              mode. To use a different mode, roll back all existing runs from the Audit
              Runner history first.
            </p>
          )}
        </div>

        {/* ── Upload Type selector (calc_engine only) ──────────────────── */}
        {ingestionMode === "calc_engine" && (
          <div className="upload-type" data-testid="audit-runner__upload-type">
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
                  data-testid="audit-runner__type2-radio"
                />
                <span className="upload-type__option-body">
                  <span className="upload-type__option-name">Type 2 — 2 Files</span>
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
                  <span className="upload-type__option-name">Type 1 — 3 Files</span>
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
              className={["file-slot", slot.file ? "file-slot--filled" : ""]
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
                    if (e.key === "Enter") inputRefs.current[slot.id]?.click();
                  }}
                >
                  <span className="file-slot__dropzone-icon">⊕</span>
                  <span className="file-slot__dropzone-text">Click or drag to select</span>
                </div>
              )}

              <input
                ref={(el) => { inputRefs.current[slot.id] = el; }}
                type="file"
                accept={slot.accept}
                onChange={(e) => handleInputChange(slot.id, e)}
                className="audit-runner__file-input"
                aria-hidden="true"
                data-testid={`audit-runner__file-input-${slot.id}`}
              />
            </div>
          ))}
        </div>

        {/* ── Progress / Error ─────────────────────────────────────────── */}
        {uploadProgress && (
          <div className="audit-runner__progress" data-testid="audit-runner__progress">
            {uploadProgress}
          </div>
        )}
        {errorMessage && (
          <div className="audit-runner__error" role="alert" data-testid="audit-runner__error">
            {errorMessage}
          </div>
        )}

        {/* ── Submit ───────────────────────────────────────────────────── */}
        <button
          className="btn btn--primary audit-runner__submit"
          onClick={handleSubmit}
          disabled={isUploading || !allRequiredFilled || isLoadingMode}
          data-testid="audit-runner__submit-btn"
        >
          {isUploading
            ? uploadProgress ?? "Uploading…"
            : label("btn.upload_and_map", "Upload & Map Fields")}
        </button>
      </div>
    </div>
  );
}