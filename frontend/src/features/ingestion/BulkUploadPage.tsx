/**
 * BulkUploadPage — Upload multiple policies at once via ZIP, folder, or
 * multi-file selection.
 *
 * Supports all three ingestion modes:
 *   • Calculation Engine Type 1  (XML + Payroll + Audit per policy)
 *   • Calculation Engine Type 2  (Payroll + Audit per policy)
 *   • Display Only               (single XLSX per policy)
 *
 * Flow:
 *   1. User drops a ZIP / folder / selects multiple files
 *   2. Frontend groups files by detected policy key
 *   3. Queue table shows each policy group with status (complete / incomplete)
 *   4. User reviews and can remove individual groups or unmatched files
 *   5. "Upload All" processes each complete group sequentially
 *   6. Results summary shown after all uploads complete
 */

import React, { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { uploadFile, approveMapping, fetchCarrierIngestionMode, type CarrierIngestionMode } from "./services/ingestionApi";
import { useQuery } from "@tanstack/react-query";
import {
  groupFilesIntoPolicies,
  extractZipFiles,
  type PolicyFileGroup,
} from "./bulkUploadUtils";

type IngestionMode = "calc_engine" | "display_only";
type UploadType = "type1" | "type2";

// ─────────────────────────────────────────────────────────────────────────────
// Per-group upload result
// ─────────────────────────────────────────────────────────────────────────────

interface GroupResult {
  policyKey: string;
  status: "pending" | "uploading" | "done" | "error";
  runId: number | null;
  error: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Slot order for upload (non-audit first, audit last)
// ─────────────────────────────────────────────────────────────────────────────

function orderedSlotTypes(mode: IngestionMode): string[] {
  if (mode === "display_only") return ["display", "csv"];
  return ["xml", "payroll", "audit"];
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function BulkUploadPage(): React.JSX.Element {
  const label         = useLabels("audit_runner");
  const navigate      = useNavigate();
  const { carrierId } = useTenantCarrier();

  // ── Carrier mode lock (same enforcement as single-file upload) ─────────────
  const { data: carrierModeData, isLoading: isLoadingMode } =
    useQuery<CarrierIngestionMode>({
      queryKey: ["carrier-ingestion-mode", carrierId],
      queryFn: () => fetchCarrierIngestionMode(carrierId),
      enabled: carrierId > 0,
      staleTime: 30_000,
    });

  const lockedMode   = carrierModeData?.locked_mode ?? null;
  const isModeLocked = lockedMode !== null;

  const [ingestionMode, setIngestionMode] = useState<IngestionMode>("calc_engine");
  const [uploadType,    setUploadType]    = useState<UploadType>("type2");

  // Sync with locked mode once query resolves
  React.useEffect(() => {
    if (lockedMode !== null) {
      setIngestionMode(lockedMode);
      setGroups([]);
      setUnmatched([]);
    }
  }, [lockedMode]);

  const [groups,    setGroups]    = useState<PolicyFileGroup[]>([]);
  const [unmatched, setUnmatched] = useState<File[]>([]);
  const [results,   setResults]   = useState<GroupResult[]>([]);

  const [isProcessing,     setIsProcessing]     = useState(false);
  const [currentGroupIdx,  setCurrentGroupIdx]  = useState<number | null>(null);
  const [overallDone,      setOverallDone]       = useState(false);

  const zipInputRef    = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const multiInputRef  = useRef<HTMLInputElement>(null);

  // ── File intake ─────────────────────────────────────────────────────────

  const processFiles = useCallback(
    async (rawFiles: File[]) => {
      // Expand any ZIP files first
      const expanded: File[] = [];
      for (const f of rawFiles) {
        if (f.name.toLowerCase().endsWith(".zip")) {
          const inner = await extractZipFiles(f);
          expanded.push(...inner);
        } else {
          expanded.push(f);
        }
      }

      const { groups: g, unmatched: u } = groupFilesIntoPolicies(
        expanded,
        ingestionMode,
        uploadType,
      );
      setGroups(g);
      setUnmatched(u);
      setResults([]);
      setOverallDone(false);
    },
    [ingestionMode, uploadType],
  );

  function handleZipChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) void processFiles(files);
  }

  function handleFolderChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) void processFiles(files);
  }

  function handleMultiChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) void processFiles(files);
  }

  function handleDropZone(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) void processFiles(files);
  }

  function handleRemoveGroup(policyKey: string): void {
    setGroups((prev) => prev.filter((g) => g.policyKey !== policyKey));
  }

  function handleRemoveUnmatched(name: string): void {
    setUnmatched((prev) => prev.filter((f) => f.name !== name));
  }

  // ── Upload all complete groups ───────────────────────────────────────────

  async function handleUploadAll(): Promise<void> {
    const completeGroups = groups.filter((g) => g.isComplete);
    if (completeGroups.length === 0) return;

    setIsProcessing(true);
    setOverallDone(false);
    setResults(
      completeGroups.map((g) => ({
        policyKey: g.policyKey,
        status:    "pending",
        runId:     null,
        error:     null,
      })),
    );

    const slotOrder = orderedSlotTypes(ingestionMode);
    let lastRunId = 0;

    for (let gi = 0; gi < completeGroups.length; gi++) {
      const group = completeGroups[gi];
      setCurrentGroupIdx(gi);
      setResults((prev) =>
        prev.map((r, i) => (i === gi ? { ...r, status: "uploading" } : r)),
      );

      try {
        // Sort: xml → payroll → audit/display (audit always last)
        const orderedFiles = [...group.files].sort((a, b) => {
          const ai = slotOrder.indexOf(a.slotType);
          const bi = slotOrder.indexOf(b.slotType);
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        });

        let groupRunId     = 0;
        let groupSessionId = 0;

        for (let fi = 0; fi < orderedFiles.length; fi++) {
          const entry      = orderedFiles[fi];
          const isLastFile = fi === orderedFiles.length - 1;

          const resp = await uploadFile(
            carrierId, 1, entry.file, ingestionMode,
          );
          groupRunId     = resp.run_id;
          groupSessionId = resp.session_id;

          if (isLastFile) {
            // The final file (audit XLSX or display XLSX) always needs
            // field mapping review — navigate there now and stop.
            // User reviews and approves mappings, ingestion completes,
            // then they return to this page to upload the next policy.
            setResults((prev) =>
              prev.map((r, i) =>
                i === gi ? { ...r, status: "done", runId: groupRunId } : r,
              ),
            );
            setIsProcessing(false);
            setCurrentGroupIdx(null);

            // Serialise the remaining groups (gi+1 onward) into router state
            // so FieldMappingReview can continue the bulk queue automatically
            // after the user approves this mapping — no manual return needed.
            const remainingGroups = completeGroups.slice(gi + 1);
            const bulkQueue = remainingGroups.map((g) => ({
              policyKey: g.policyKey,
              files: g.files.map((fe) => ({
                slotType: fe.slotType,
                // File objects are not serialisable — pass name + reconstruct
                // using a temporary store keyed by filename
                name: fe.file.name,
              })),
            }));
            // Store File objects in sessionStorage so FieldMappingReview can
            // retrieve them (File objects can't travel through router state)
            const fileStore: Record<string, File> = {};
            remainingGroups.forEach((g) =>
              g.files.forEach((fe) => { fileStore[fe.file.name] = fe.file; })
            );
            sessionStorage.setItem(
              "bulkUploadFileStore",
              JSON.stringify(Object.keys(fileStore))
            );
            // Store File objects via a module-level variable accessible across routes
            window.__bulkFileStore = fileStore;
            window.__bulkIngestionMode = ingestionMode;
            window.__bulkCarrierId = carrierId;

            // For display_only: collect run_ids of all prior groups that were
            // already uploaded+auto-approved (gi=0 means none yet).
            // These are passed as completedRunIds so FieldMappingReview can
            // accumulate and eventually send all of them to runAuditEngine.
            const priorRunIds: number[] = [];
            // No prior approved runs at gi=0; for gi>0 this branch is
            // unreachable (only the first group navigates here from BulkUpload).
            navigate(`/audit-runner/${groupRunId}/mapping`, {
              state: {
                sessionId:       groupSessionId,
                runId:           groupRunId,
                bulkQueue,
                hasBulkQueue:    remainingGroups.length > 0,
                completedRunIds: priorRunIds,
              },
            });
            return;
          } else {
            // Non-final files (XML, payroll) — auto-approve immediately.
            // These files use high-confidence canonical field mappings
            // and do not require manual review.
            await approveMapping(resp.session_id);
            await new Promise((r) => setTimeout(r, 600));
          }
        }

        lastRunId = groupRunId;
        setResults((prev) =>
          prev.map((r, i) =>
            i === gi ? { ...r, status: "done", runId: groupRunId } : r,
          ),
        );
      } catch (err: unknown) {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail;
        const msg =
          detail ??
          (err instanceof Error ? err.message : "Upload failed");

        setResults((prev) =>
          prev.map((r, i) =>
            i === gi ? { ...r, status: "error", error: msg } : r,
          ),
        );
        // Continue processing remaining groups even if one fails
      }
    }

    setIsProcessing(false);
    setCurrentGroupIdx(null);
    setOverallDone(true);

    // Navigate to the last successful run's progress page
    if (lastRunId > 0) {
      navigate(`/audit-runner/${lastRunId}/progress`);
    }
  }

  // ── Derived ──────────────────────────────────────────────────────────────

  const completeCount   = groups.filter((g) => g.isComplete).length;
  const incompleteCount = groups.filter((g) => !g.isComplete).length;
  const doneCount       = results.filter((r) => r.status === "done").length;
  const errorCount      = results.filter((r) => r.status === "error").length;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="bulk-upload" data-testid="bulk-upload">

      {/* ── Header */}
      <div className="audit-runner__header">
        <h1 className="audit-runner__title">
          {label("bulk.title", "Bulk Upload")}
        </h1>
        <p className="audit-runner__subtitle">
          {label(
            "bulk.subtitle",
            "Upload a ZIP file, drop a folder, or select multiple files. " +
            "Files are automatically grouped by policy number.",
          )}
        </p>
      </div>

      <div className="audit-runner__card">

        {/* ── Mode + Type selectors */}
        <div className="ingest-toggle">
          <span className="ingest-toggle__label">Pipeline Mode</span>
          <div className="ingest-toggle__pills" role="group">
            {isModeLocked && (
              <span className="ingest-toggle__lock-badge" title="Mode locked by prior ingestion history">
                🔒 Locked to {lockedMode === "calc_engine" ? "Calculation Engine" : "Display Only"}
              </span>
            )}
            {(["calc_engine", "display_only"] as IngestionMode[]).map((m) => (
              <button
                key={m}
                type="button"
                className={[
                  "ingest-toggle__pill",
                  ingestionMode === m ? "ingest-toggle__pill--active" : "",
                  m === "display_only" && ingestionMode === m ? "ingest-toggle__pill--display" : "",
                  isModeLocked && ingestionMode !== m ? "ingest-toggle__pill--locked-inactive" : "",
                ].filter(Boolean).join(" ")}
                onClick={() => {
                  if (isModeLocked) return;
                  setIngestionMode(m);
                  setGroups([]);
                  setUnmatched([]);
                }}
                disabled={isProcessing || isModeLocked || isLoadingMode}
                aria-disabled={isModeLocked}
                title={isModeLocked && ingestionMode !== m
                  ? `This carrier is locked to ${lockedMode === "calc_engine" ? "Calculation Engine" : "Display Only"} mode`
                  : undefined}
              >
                <span className="ingest-toggle__pill-dot" />
                {m === "calc_engine" ? "Calculation Engine" : "Display Only"}
              </button>
            ))}
          </div>
        </div>

        {ingestionMode === "calc_engine" && (
          <div className="upload-type" style={{ marginTop: "12px" }}>
            <span className="upload-type__label">Upload Type</span>
            <div className="upload-type__options">
              {(["type2", "type1"] as UploadType[]).map((t) => (
                <label key={t} className="upload-type__option">
                  <input
                    type="radio"
                    name="bulk_upload_type"
                    value={t}
                    checked={uploadType === t}
                    onChange={() => setUploadType(t)}
                    disabled={isProcessing || isLoadingMode}
                  />
                  <span className="upload-type__option-body">
                    <span className="upload-type__option-name">
                      {t === "type1" ? "Type 1 — 3 Files" : "Type 2 — 2 Files"}
                    </span>
                    <span className="upload-type__option-desc">
                      {t === "type1"
                        ? "XML + Payroll XLSX + Audit XLSX per policy"
                        : "Payroll XLSX + Audit XLSX per policy"}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* ── Drop zone + intake buttons */}
        <div
          className="bulk-upload__dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDropZone}
          style={{
            border: "2px dashed var(--border)",
            borderRadius: "10px",
            padding: "32px",
            textAlign: "center",
            marginTop: "20px",
            cursor: "pointer",
            background: "var(--surface-2)",
            transition: "border-color 0.2s",
          }}
        >
          <div style={{ fontSize: "32px", marginBottom: "8px" }}>📂</div>
          <p style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: "4px" }}>
            Drop files or a ZIP here
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "16px" }}>
            Supports: .xlsx, .xml, .csv files and .zip archives
          </p>

          <div style={{ display: "flex", gap: "10px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => zipInputRef.current?.click()}
              disabled={isProcessing}
            >
              📦 Upload ZIP
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => folderInputRef.current?.click()}
              disabled={isProcessing}
            >
              📁 Select Folder
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => multiInputRef.current?.click()}
              disabled={isProcessing}
            >
              📄 Select Multiple Files
            </button>
          </div>

          {/* Hidden inputs */}
          <input
            ref={zipInputRef}
            type="file"
            accept=".zip"
            onChange={handleZipChange}
            style={{ display: "none" }}
          />
          <input
            ref={folderInputRef}
            type="file"
            // @ts-expect-error webkitdirectory is non-standard but widely supported
            webkitdirectory="true"
            onChange={handleFolderChange}
            style={{ display: "none" }}
          />
          <input
            ref={multiInputRef}
            type="file"
            accept=".xlsx,.xml,.csv"
            multiple
            onChange={handleMultiChange}
            style={{ display: "none" }}
          />
        </div>

        {/* ── Naming convention hint */}
        <details style={{ marginTop: "12px" }}>
          <summary
            style={{ cursor: "pointer", color: "var(--text-muted)", fontSize: "12px" }}
          >
            File naming conventions
          </summary>
          <div
            style={{
              marginTop: "8px",
              padding: "12px",
              background: "var(--surface-2)",
              borderRadius: "6px",
              fontSize: "12px",
              color: "var(--text-muted)",
              lineHeight: "1.8",
            }}
          >
            <strong style={{ color: "var(--text-primary)" }}>
              Calc Engine (Type 2):
            </strong>
            <br />
            <code>POL001_payroll.xlsx</code> + <code>POL001_audit.xlsx</code>
            <br />
            <br />
            <strong style={{ color: "var(--text-primary)" }}>
              Calc Engine (Type 1):
            </strong>
            <br />
            <code>POL001.xml</code> + <code>POL001_payroll.xlsx</code> +{" "}
            <code>POL001_audit.xlsx</code>
            <br />
            <br />
            <strong style={{ color: "var(--text-primary)" }}>Display Only:</strong>
            <br />
            <code>POL001.xlsx</code> <em>(one file per policy)</em>
            <br />
            <br />
            Files with the same prefix before <code>_payroll</code>,{" "}
            <code>_audit</code>, or <code>.xml</code> are grouped as one policy.
          </div>
        </details>

        {/* ── Queue table */}
        {(groups.length > 0 || unmatched.length > 0) && (
          <div style={{ marginTop: "24px" }}>
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(99,102,241,0.08)",
                border: "1px solid rgba(99,102,241,0.25)",
                borderRadius: "8px",
                fontSize: "12px",
                color: "var(--text-muted)",
                marginBottom: "12px",
                lineHeight: "1.6",
              }}
            >
              <strong style={{ color: "var(--accent)" }}>ℹ How bulk upload works:</strong>
              {" "}Each policy is uploaded one at a time. After each upload you will be
              taken to the{" "}
              <strong style={{ color: "var(--text-primary)" }}>Field Mapping Review</strong>
              {" "}screen to approve mappings. Once approved, return here for the next policy.
              XML and payroll files are auto-approved without review.
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "12px",
              }}
            >
              <h3 style={{ margin: 0, fontSize: "14px", color: "var(--text-primary)" }}>
                Upload Queue
              </h3>
              <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                <span style={{ color: "var(--color-green)", fontWeight: 600 }}>
                  {completeCount} ready
                </span>
                {incompleteCount > 0 && (
                  <>
                    {" · "}
                    <span style={{ color: "var(--color-amber)" }}>
                      {incompleteCount} incomplete
                    </span>
                  </>
                )}
                {unmatched.length > 0 && (
                  <>
                    {" · "}
                    <span style={{ color: "var(--color-red)" }}>
                      {unmatched.length} unmatched
                    </span>
                  </>
                )}
              </div>
            </div>

            <div
              style={{
                border: "1px solid var(--border)",
                borderRadius: "8px",
                overflow: "hidden",
              }}
            >
              <table
                style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}
              >
                <thead>
                  <tr style={{ background: "var(--surface-2)" }}>
                    <th style={thStyle}>Policy Group</th>
                    <th style={thStyle}>Files</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Result</th>
                    <th style={thStyle}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group, gi) => {
                    const result = results.find((r) => r.policyKey === group.policyKey);
                    const isCurrentlyUploading =
                      isProcessing && currentGroupIdx === gi;
                    return (
                      <tr
                        key={group.policyKey}
                        style={{
                          borderTop: "1px solid var(--border)",
                          background: isCurrentlyUploading
                            ? "var(--surface-2)"
                            : "transparent",
                        }}
                      >
                        <td style={tdStyle}>
                          <code
                            style={{
                              color: "var(--text-primary)",
                              fontSize: "12px",
                            }}
                          >
                            {group.policyKey}
                          </code>
                        </td>
                        <td style={tdStyle}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                            {group.files.map((f) => (
                              <span
                                key={f.file.name}
                                style={{
                                  background: "var(--surface-2)",
                                  border: "1px solid var(--border)",
                                  borderRadius: "4px",
                                  padding: "2px 6px",
                                  fontSize: "11px",
                                  color: "var(--text-muted)",
                                }}
                                title={f.file.name}
                              >
                                {f.slotType.toUpperCase()} · {f.file.name}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td style={tdStyle}>
                          {group.isComplete ? (
                            <span style={{ color: "var(--color-green)" }}>✓ Ready</span>
                          ) : (
                            <span style={{ color: "var(--color-amber)" }}>
                              ⚠ Incomplete
                            </span>
                          )}
                        </td>
                        <td style={tdStyle}>
                          {result ? (
                            result.status === "done" ? (
                              <span style={{ color: "var(--color-green)" }}>
                                ✓ Run #{result.runId}
                              </span>
                            ) : result.status === "error" ? (
                              <span
                                style={{ color: "var(--color-red)", fontSize: "11px" }}
                                title={result.error ?? ""}
                              >
                                ✗ {result.error?.slice(0, 40)}…
                              </span>
                            ) : result.status === "uploading" ? (
                              <span style={{ color: "var(--text-muted)" }}>
                                ⟳ Uploading…
                              </span>
                            ) : (
                              <span style={{ color: "var(--text-muted)" }}>Pending</span>
                            )
                          ) : (
                            <span style={{ color: "var(--text-muted)" }}>—</span>
                          )}
                        </td>
                        <td style={tdStyle}>
                          <button
                            type="button"
                            className="btn btn--sm btn--secondary"
                            onClick={() => handleRemoveGroup(group.policyKey)}
                            disabled={isProcessing}
                            aria-label={`Remove ${group.policyKey}`}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}

                  {/* Unmatched files */}
                  {unmatched.map((f) => (
                    <tr
                      key={f.name}
                      style={{ borderTop: "1px solid var(--border)", opacity: 0.6 }}
                    >
                      <td style={tdStyle} colSpan={2}>
                        <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                          {f.name}
                        </span>
                      </td>
                      <td style={tdStyle}>
                        <span style={{ color: "var(--color-red)", fontSize: "12px" }}>
                          Unmatched
                        </span>
                      </td>
                      <td style={tdStyle}>—</td>
                      <td style={tdStyle}>
                        <button
                          type="button"
                          className="btn btn--sm btn--secondary"
                          onClick={() => handleRemoveUnmatched(f.name)}
                          disabled={isProcessing}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* ── Overall progress summary while uploading */}
            {isProcessing && results.length > 0 && (
              <div
                style={{
                  marginTop: "12px",
                  padding: "10px 14px",
                  background: "var(--surface-2)",
                  borderRadius: "6px",
                  fontSize: "13px",
                  color: "var(--text-muted)",
                }}
              >
                Processing {doneCount + errorCount + 1} of {results.length}…
                &nbsp;
                <span style={{ color: "var(--color-green)" }}>
                  {doneCount} done
                </span>
                {errorCount > 0 && (
                  <>
                    &nbsp;·&nbsp;
                    <span style={{ color: "var(--color-red)" }}>
                      {errorCount} failed
                    </span>
                  </>
                )}
              </div>
            )}

            {/* ── Done summary */}
            {overallDone && (
              <div
                style={{
                  marginTop: "12px",
                  padding: "12px 16px",
                  background:
                    errorCount === 0
                      ? "rgba(34,197,94,0.08)"
                      : "rgba(239,68,68,0.08)",
                  border: `1px solid ${errorCount === 0 ? "var(--color-green)" : "var(--color-red)"}`,
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
              >
                {errorCount === 0 ? (
                  <span style={{ color: "var(--color-green)", fontWeight: 600 }}>
                    ✓ All {doneCount} policies uploaded successfully.
                  </span>
                ) : (
                  <span style={{ color: "var(--color-red)", fontWeight: 600 }}>
                    {doneCount} succeeded · {errorCount} failed — review errors above.
                  </span>
                )}
              </div>
            )}

            {/* ── Upload All button */}
            {!overallDone && (
              <button
                type="button"
                className="btn btn--primary"
                style={{ marginTop: "16px", width: "100%" }}
                onClick={() => void handleUploadAll()}
                disabled={isProcessing || completeCount === 0}
              >
                {isProcessing
                  ? `Uploading ${doneCount + 1} / ${completeCount}…`
                  : `Upload All ${completeCount} ${completeCount === 1 ? "Policy" : "Policies"}`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Shared table cell styles
const thStyle: React.CSSProperties = {
  padding: "10px 14px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: "11px",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--text-muted)",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 14px",
  verticalAlign: "middle",
};