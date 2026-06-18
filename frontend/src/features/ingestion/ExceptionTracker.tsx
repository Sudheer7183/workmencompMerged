/**
 * ExceptionTracker — Phase 4.
 *
 * Displays exception tracking for a completed or partial ingestion run.
 * Shows:
 *   1. Summary panel — row counts, run status badge
 *   2. Skipped rows table — with inline raw data expansion, correct/re-ingest, dismiss
 *   3. Error log table — all ingestion_errors for the run
 *   4. Rollback button — TENANT_ADMIN only, with confirmation dialog
 *
 * Route: /audit-runner/:runId/exceptions
 * V9 S17.4, S26.2
 */

import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { ReportStatusModal } from "@/features/reports/ReportStatusModal";
import { generateReport } from "@/features/reports/services/reportsApi";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunStatus {
  run_id: number;
  status: string;
  rows_ingested: number | null;
  rows_skipped: number;
  rows_failed: number;
  error_detail: string | null;
  started_at: string;
  completed_at: string | null;
}

interface SkippedRow {
  skip_id: number;
  run_id: number;
  row_number: number;
  raw_data: Record<string, unknown>;
  skip_reason: string;
  error_codes: string[];
  resolution_status: "PENDING" | "CORRECTED" | "DISMISSED";
  corrected_data: Record<string, unknown> | null;
  resolved_by: string | null;
  resolved_at: string | null;
}

interface IngestionError {
  error_id: number;
  run_id: number;
  row_number: number | null;
  field_name: string | null;
  error_type: string;
  error_message: string;
  raw_value: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }): React.JSX.Element {
  const classMap: Record<string, string> = {
    complete: "badge badge--success",
    partial: "badge badge--warning",
    failed: "badge badge--error",
    rolled_back: "badge badge--neutral",
    processing: "badge badge--info",
  };
  return (
    <span
      className={classMap[status] ?? "badge badge--neutral"}
      data-testid="exception-tracker__status-badge"
    >
      {status.replace("_", " ").toUpperCase()}
    </span>
  );
}

function ErrorCodeBadge({ code }: { code: string }): React.JSX.Element {
  return (
    <span className="exception-tracker__error-code-badge" title={code}>
      {code.replace(/_/g, " ")}
    </span>
  );
}

/** Collapsible raw data viewer for a skipped row. */
function RawDataViewer({ data }: { data: Record<string, unknown> }): React.JSX.Element {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="exception-tracker__raw-data">
      <button
        className="exception-tracker__raw-data-toggle"
        onClick={() => setExpanded((p) => !p)}
        aria-expanded={expanded}
        data-testid="exception-tracker__view-raw-btn"
      >
        {expanded ? "▲ Hide Raw Data" : "▼ View Raw Data"}
      </button>
      {expanded && (
        <pre
          className="exception-tracker__raw-data-content"
          data-testid="exception-tracker__raw-data-content"
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

/** Inline corrected-data editor for a skipped row. */
function CorrectionEditor({
  row,
  onSubmit,
  onCancel,
}: {
  row: SkippedRow;
  onSubmit: (correctedData: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}): React.JSX.Element {
  const [value, setValue] = useState(
    JSON.stringify(row.corrected_data ?? row.raw_data, null, 2)
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(): Promise<void> {
    setError(null);
    try {
      const parsed = JSON.parse(value);
      setSubmitting(true);
      await onSubmit(parsed);
    } catch (e) {
      setError(e instanceof SyntaxError ? "Invalid JSON" : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="exception-tracker__correction-editor"
      data-testid="exception-tracker__correction-editor"
    >
      <p className="exception-tracker__correction-hint">
        Edit the JSON below and click "Save &amp; Re-ingest":
      </p>
      <textarea
        className="exception-tracker__correction-textarea"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={8}
        data-testid="exception-tracker__correction-textarea"
      />
      {error && (
        <p className="exception-tracker__correction-error" role="alert">
          {error}
        </p>
      )}
      <div className="exception-tracker__correction-actions">
        <button
          className="btn btn--primary"
          onClick={handleSubmit}
          disabled={submitting}
          data-testid="exception-tracker__save-reingest-btn"
        >
          {submitting ? "Saving…" : "Save & Re-ingest"}
        </button>
        <button
          className="btn btn--secondary"
          onClick={onCancel}
          data-testid="exception-tracker__cancel-edit-btn"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/** Rollback confirmation dialog — requires typing "ROLLBACK". */
function RollbackDialog({
  runId,
  onConfirm,
  onCancel,
  loading,
}: {
  runId: number;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}): React.JSX.Element {
  const [confirmText, setConfirmText] = useState("");
  const isConfirmed = confirmText === "ROLLBACK";

  return (
    <div
      className="exception-tracker__rollback-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rollback-dialog-title"
      data-testid="exception-tracker__rollback-dialog"
    >
      <div className="exception-tracker__rollback-dialog-inner">
        <h2
          id="rollback-dialog-title"
          className="exception-tracker__rollback-dialog-title"
        >
          Confirm Rollback — Run #{runId}
        </h2>
        <p className="exception-tracker__rollback-dialog-warning">
          This action will permanently delete all policy data ingested by run #{runId}.
          Error logs and skipped row records will be preserved. This cannot be undone.
        </p>
        <label className="exception-tracker__rollback-label">
          Type <strong>ROLLBACK</strong> to confirm:
          <input
            type="text"
            className="exception-tracker__rollback-input"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="ROLLBACK"
            data-testid="exception-tracker__rollback-confirm-input"
            autoFocus
          />
        </label>
        <div className="exception-tracker__rollback-dialog-actions">
          <button
            className="btn btn--danger"
            onClick={onConfirm}
            disabled={!isConfirmed || loading}
            data-testid="exception-tracker__rollback-confirm-btn"
          >
            {loading ? "Rolling back…" : "Confirm Rollback"}
          </button>
          <button
            className="btn btn--secondary"
            onClick={onCancel}
            data-testid="exception-tracker__rollback-cancel-btn"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ExceptionTracker(): React.JSX.Element {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const label_calc_engine = useLabels("calc_engine");
  const label_shared = useLabels("shared");
  const { user } = useAuth();

  const isTenantAdmin = user?.role === "TENANT_ADMIN";
  const parsedRunId = Number(runId ?? 0);
  const { carrierId } = useTenantCarrier();

  const [run, setRun] = useState<RunStatus | null>(null);
  const [skippedRows, setSkippedRows] = useState<SkippedRow[]>([]);
  const [errors, setErrors] = useState<IngestionError[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Editing state.
  const [editingSkipId, setEditingSkipId] = useState<number | null>(null);

  // Report generation state (Phase 5 — replaces Phase 4 stub).
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // Rollback dialog state.
  const [showRollbackDialog, setShowRollbackDialog] = useState(false);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);

  const fetchData = useCallback(async (): Promise<void> => {
    if (!parsedRunId) return;
    setLoading(true);
    setLoadError(null);

    try {
      const [runRes, skippedRes, errorsRes] = await Promise.all([
        axios.get<RunStatus>(`/api/v1/ingestion/runs/${parsedRunId}`),
        axios.get<SkippedRow[]>(`/api/v1/ingestion/runs/${parsedRunId}/skipped`),
        axios.get<IngestionError[]>(`/api/v1/ingestion/runs/${parsedRunId}/errors`),
      ]);
      setRun(runRes.data);
      setSkippedRows(skippedRes.data);
      setErrors(errorsRes.data);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to load exception data.";
      setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [parsedRunId]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  async function handleSaveAndReingest(
    skipId: number,
    correctedData: Record<string, unknown>
  ): Promise<void> {
    // Step 1: Save corrected data.
    await axios.put(`/api/v1/ingestion/skipped/${skipId}/correct`, {
      corrected_data: correctedData,
    });
    // Step 2: Re-ingest.
    await axios.post(`/api/v1/ingestion/skipped/${skipId}/reingest`);
    setEditingSkipId(null);
    await fetchData();
  }

  async function handleDismiss(skipId: number): Promise<void> {
    await axios.post(`/api/v1/ingestion/skipped/${skipId}/dismiss`);
    await fetchData();
  }

  async function handleExportErrorReport(): Promise<void> {
    // Phase 5: real report generation — replaces Phase 4 stub.
    try {
      const { job_id } = await generateReport({
        carrier_id: carrierId,
        report_type: "exception_report",
        output_format: "excel",
        run_id: parsedRunId,
      });
      setActiveJobId(job_id);
    } catch {
      // Error is surfaced via the ReportStatusModal on next open
    }
  }

  async function handleRollback(): Promise<void> {
    setRollbackLoading(true);
    setRollbackError(null);
    try {
      await axios.post(`/api/v1/ingestion/runs/${parsedRunId}/rollback`);
      setShowRollbackDialog(false);
      await fetchData();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Rollback failed.";
      setRollbackError(msg);
    } finally {
      setRollbackLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="exception-tracker exception-tracker--loading" data-testid="exception-tracker">
        <span className="exception-tracker__spinner" aria-hidden="true" />
        <p>{label_shared("loading", "Loading…") ?? "Loading exception data…"}</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="exception-tracker exception-tracker--error" data-testid="exception-tracker">
        <p className="exception-tracker__load-error" role="alert">
          {loadError}
        </p>
        <button className="btn btn--secondary" onClick={() => void fetchData()}>
          Retry
        </button>
      </div>
    );
  }

  const canRollback =
    isTenantAdmin &&
    run !== null &&
    ["complete", "partial"].includes(run.status);

  return (
    <div className="exception-tracker" data-testid="exception-tracker">
      {/* ── Summary panel ───────────────────────────────────────────────── */}
      <header className="exception-tracker__header">
        <h1 className="exception-tracker__title" data-testid="exception-tracker__title">
          {label_shared("exception_tracker_title", "exception_tracker_title") ?? "Exception Tracker"} — Run #{parsedRunId}
        </h1>
        <button
          className="btn btn--ghost exception-tracker__back-btn"
          onClick={() => navigate(-1)}
          data-testid="exception-tracker__back-btn"
        >
          ← Back
        </button>
      </header>

      {run && (
        <section
          className="exception-tracker__summary"
          aria-label="Run summary"
          data-testid="exception-tracker__summary"
        >
          <div className="exception-tracker__summary-stat">
            <span className="exception-tracker__summary-label">Status</span>
            <StatusBadge status={run.status} />
          </div>
          <div className="exception-tracker__summary-stat">
            <span className="exception-tracker__summary-label">
              {label_shared("rows_ingested", "rows_ingested") ?? "Rows Ingested"}
            </span>
            <span
              className="exception-tracker__summary-value"
              data-testid="exception-tracker__rows-ingested"
            >
              {run.rows_ingested ?? 0}
            </span>
          </div>
          <div className="exception-tracker__summary-stat">
            <span className="exception-tracker__summary-label">
              {label_shared("rows_skipped", "rows_skipped") ?? "Rows Skipped"}
            </span>
            <span
              className="exception-tracker__summary-value exception-tracker__summary-value--warn"
              data-testid="exception-tracker__rows-skipped"
            >
              {run.rows_skipped}
            </span>
          </div>
          <div className="exception-tracker__summary-stat">
            <span className="exception-tracker__summary-label">
              {label_shared("errors_logged", "errors_logged") ?? "Errors Logged"}
            </span>
            <span
              className="exception-tracker__summary-value exception-tracker__summary-value--error"
              data-testid="exception-tracker__errors-count"
            >
              {errors.length}
            </span>
          </div>
          {run.error_detail && (
            <div className="exception-tracker__run-error">
              <strong>Run Error:</strong> {run.error_detail}
            </div>
          )}

          {/* Rollback button — TENANT_ADMIN only */}
          {canRollback && (
            <button
              className="btn btn--danger exception-tracker__rollback-btn"
              onClick={() => setShowRollbackDialog(true)}
              data-testid="exception-tracker__rollback-btn"
            >
              {label_shared("btn_rollback", "btn_rollback") ?? "Rollback Run"}
            </button>
          )}

          {rollbackError && (
            <p
              className="exception-tracker__rollback-error"
              role="alert"
              data-testid="exception-tracker__rollback-error"
            >
              {rollbackError}
            </p>
          )}

          {/* Export Error Report — Phase 4 stub; Phase 5 implements generation */}
          <button
            className="btn btn--secondary exception-tracker__export-btn"
            onClick={() => void handleExportErrorReport()}
            data-testid="exception-tracker__export-btn"
          >
            {label_shared("btn_export_error_report", "btn_export_error_report") ?? "Export Error Report"}
          </button>

          {/* Phase 5: ReportStatusModal is shown when activeJobId is set */}
        </section>
      )}

      {/* ── Report Status Modal (Phase 5) ────────────────────────────────── */}
      {activeJobId && (
        <ReportStatusModal
          jobId={activeJobId}
          reportType="exception_report"
          outputFormat="excel"
          onClose={() => setActiveJobId(null)}
          onRetry={() => {
            setActiveJobId(null);
            void handleExportErrorReport();
          }}
        />
      )}

      {/* ── Skipped rows table ───────────────────────────────────────────── */}
      <section
        className="exception-tracker__section"
        aria-label="Skipped rows"
        data-testid="exception-tracker__skipped-section"
      >
        <h2 className="exception-tracker__section-title">
          {label_shared("skipped_rows_heading", "skipped_rows_heading") ?? "Skipped Rows"}
          <span className="exception-tracker__section-count">({skippedRows.length})</span>
        </h2>

        {skippedRows.length === 0 ? (
          <p className="exception-tracker__empty" data-testid="exception-tracker__no-skipped">
            {label_shared("no_skipped_rows", "no_skipped_rows") ?? "No skipped rows for this run."}
          </p>
        ) : (
          <div className="exception-tracker__table-wrapper">
            <table
              className="exception-tracker__table"
              data-testid="exception-tracker__skipped-table"
            >
              <thead>
                <tr>
                  <th>{label_shared("col_row_number", "col_row_number") ?? "Row #"}</th>
                  <th>{label_shared("col_error_codes", "col_error_codes") ?? "Error Code(s)"}</th>
                  <th>{label_shared("col_skip_reason", "col_skip_reason") ?? "Reason"}</th>
                  <th>{label_shared("col_raw_data", "col_raw_data") ?? "Raw Data"}</th>
                  <th>{label_shared("col_status", "col_status") ?? "Status"}</th>
                  <th>{label_calc_engine("col.actions", "Actions") ?? "Actions"}</th>
                </tr>
              </thead>
              <tbody>
                {skippedRows.map((row) => (
                  <tr
                    key={row.skip_id}
                    className={`exception-tracker__row exception-tracker__row--${row.resolution_status.toLowerCase()}`}
                    data-testid={`exception-tracker__skipped-row-${row.skip_id}`}
                  >
                    <td data-testid="exception-tracker__row-number">{row.row_number}</td>
                    <td>
                      {row.error_codes.map((code) => (
                        <ErrorCodeBadge key={code} code={code} />
                      ))}
                    </td>
                    <td className="exception-tracker__skip-reason">{row.skip_reason}</td>
                    <td>
                      <RawDataViewer data={row.raw_data} />
                    </td>
                    <td>
                      <span
                        className={`badge badge--${row.resolution_status === "PENDING" ? "warning" : row.resolution_status === "CORRECTED" ? "success" : "neutral"}`}
                        data-testid="exception-tracker__resolution-status"
                      >
                        {row.resolution_status}
                      </span>
                    </td>
                    <td>
                      {row.resolution_status === "PENDING" && (
                        editingSkipId === row.skip_id ? (
                          <CorrectionEditor
                            row={row}
                            onSubmit={(data) => handleSaveAndReingest(row.skip_id, data)}
                            onCancel={() => setEditingSkipId(null)}
                          />
                        ) : (
                          <div className="exception-tracker__row-actions">
                            <button
                              className="btn btn--small btn--secondary"
                              onClick={() => setEditingSkipId(row.skip_id)}
                              data-testid="exception-tracker__edit-reingest-btn"
                            >
                              {label_shared("btn_edit_reingest", "btn_edit_reingest") ?? "Edit & Re-ingest"}
                            </button>
                            <button
                              className="btn btn--small btn--ghost"
                              onClick={() => void handleDismiss(row.skip_id)}
                              data-testid="exception-tracker__dismiss-btn"
                            >
                              {label_shared("btn_dismiss", "btn_dismiss") ?? "Dismiss"}
                            </button>
                          </div>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Error log table ──────────────────────────────────────────────── */}
      <section
        className="exception-tracker__section"
        aria-label="Error log"
        data-testid="exception-tracker__errors-section"
      >
        <h2 className="exception-tracker__section-title">
          {label_shared("error_log_heading", "error_log_heading") ?? "Error Log"}
          <span className="exception-tracker__section-count">({errors.length})</span>
        </h2>

        {errors.length === 0 ? (
          <p className="exception-tracker__empty" data-testid="exception-tracker__no-errors">
            {label_shared("no_errors", "no_errors") ?? "No errors recorded for this run."}
          </p>
        ) : (
          <div className="exception-tracker__table-wrapper">
            <table
              className="exception-tracker__table"
              data-testid="exception-tracker__errors-table"
            >
              <thead>
                <tr>
                  <th>{label_shared("col_row_number", "col_row_number") ?? "Row #"}</th>
                  <th>{label_shared("col_field", "col_field") ?? "Field"}</th>
                  <th>{label_shared("col_error_type", "col_error_type") ?? "Error Type"}</th>
                  <th>{label_shared("col_error_message", "col_error_message") ?? "Message"}</th>
                  <th>{label_shared("col_raw_value", "col_raw_value") ?? "Raw Value"}</th>
                </tr>
              </thead>
              <tbody>
                {errors.map((err) => (
                  <tr key={err.error_id} data-testid={`exception-tracker__error-row-${err.error_id}`}>
                    <td>{err.row_number ?? "—"}</td>
                    <td>{err.field_name ?? "—"}</td>
                    <td>
                      <ErrorCodeBadge code={err.error_type} />
                    </td>
                    <td className="exception-tracker__error-message">{err.error_message}</td>
                    <td className="exception-tracker__raw-value">{err.raw_value ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Rollback dialog ───────────────────────────────────────────────── */}
      {showRollbackDialog && (
        <div
          className="exception-tracker__dialog-overlay"
          data-testid="exception-tracker__dialog-overlay"
        >
          <RollbackDialog
            runId={parsedRunId}
            onConfirm={() => void handleRollback()}
            onCancel={() => {
              setShowRollbackDialog(false);
              setRollbackError(null);
            }}
            loading={rollbackLoading}
          />
        </div>
      )}
    </div>
  );
}
