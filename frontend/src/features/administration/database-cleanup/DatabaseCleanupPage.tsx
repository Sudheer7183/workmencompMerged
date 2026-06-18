/**
 * DatabaseCleanupPage — Phase 6.
 *
 * Two-step monthly cleanup workflow per V9 S22.4.
 * Only accessible to TENANT_ADMIN.
 *
 * Layout:
 *   1. Page header with title and subtitle.
 *   2. "What is preserved" section — read-only informational list.
 *   3. Preview panel — POST /api/v1/database-cleanup/preview.
 *   4. Confirmation input + Execute button (enabled only when input === "CONFIRM").
 *   5. Cleanup history table — last 20 runs.
 */

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchCleanupPreview,
  executeCleanup,
  fetchCleanupHistory,
  type CleanupPreview,
  type CleanupHistoryEntry,
} from "./cleanupService";

// ─── Preserved data categories (V9 S22.3) ────────────────────────────────────

const PRESERVED_ITEMS: string[] = [
  "Calculation rules & engine configuration",
  "UI labels & display configuration",
  "Theme configuration & custom themes",
  "Carrier report templates",
  "Ingestion sources & field mapping configurations",
  "Organisation profile, contacts & branding",
  "User accounts & role assignments",
  "Cleanup run history (this table)",
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  return n.toLocaleString();
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

function totalRows(preview: CleanupPreview): number {
  return Object.values(preview).reduce((sum, n) => sum + n, 0);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface PreviewTableProps {
  preview: CleanupPreview;
}

function PreviewTable({ preview }: PreviewTableProps): React.JSX.Element {
  const rows: [string, number][] = [
    ["Premium Variance",          preview.premium_variance],
    ["Payroll Variance (Policy)", preview.payroll_variance_policy],
    ["Payroll Variance (Class)",  preview.payroll_variance_class],
    ["Zero Payroll",              preview.zero_payroll],
    ["Missing Payroll",           preview.missing_payroll],
    ["Policies",                  preview.policies],
    ["Policyholders",             preview.policyholders],
    ["Ingestion Runs",            preview.ingestion_runs],
    ["Ingestion Errors",          preview.ingestion_errors],
    ["Ingestion Skipped Rows",    preview.ingestion_skipped_rows],
    ["Ingestion Rollbacks",       preview.ingestion_rollbacks],
    ["Field Mapping Sessions",    preview.field_mapping_sessions],
    ["Field Mapping Proposals",   preview.field_mapping_proposals],
    ["Report Jobs (terminal)",    preview.report_jobs],
  ];

  return (
    <table className="cleanup-preview__table" aria-label="Rows to be deleted">
      <thead>
        <tr>
          <th className="cleanup-preview__th">Table</th>
          <th className="cleanup-preview__th cleanup-preview__th--right">Rows to delete</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, count]) => (
          <tr key={label} className="cleanup-preview__row">
            <td className="cleanup-preview__td">{label}</td>
            <td className={`cleanup-preview__td cleanup-preview__td--right ${count > 0 ? "cleanup-preview__count--nonzero" : ""}`}>
              {formatNumber(count)}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="cleanup-preview__total-row">
          <td className="cleanup-preview__td cleanup-preview__td--total">Total rows</td>
          <td className="cleanup-preview__td cleanup-preview__td--right cleanup-preview__td--total">
            {formatNumber(totalRows(preview))}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

interface HistoryTableProps {
  entries: CleanupHistoryEntry[];
}

function HistoryTable({ entries }: HistoryTableProps): React.JSX.Element {
  if (entries.length === 0) {
    return (
      <p className="cleanup-history__empty">No cleanup runs recorded yet.</p>
    );
  }

  return (
    <table className="cleanup-history__table" aria-label="Cleanup history">
      <thead>
        <tr>
          <th className="cleanup-history__th">Run ID</th>
          <th className="cleanup-history__th">Started</th>
          <th className="cleanup-history__th">Completed</th>
          <th className="cleanup-history__th">Status</th>
          <th className="cleanup-history__th cleanup-history__th--right">Policies archived</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.cleanup_id} className="cleanup-history__row">
            <td className="cleanup-history__td cleanup-history__td--mono">
              #{entry.cleanup_id}
            </td>
            <td className="cleanup-history__td">{formatDate(entry.initiated_at)}</td>
            <td className="cleanup-history__td">{formatDate(entry.completed_at)}</td>
            <td className="cleanup-history__td">
              <span className={`cleanup-history__status cleanup-history__status--${entry.status.toLowerCase()}`}>
                {entry.status}
              </span>
            </td>
            <td className="cleanup-history__td cleanup-history__td--right">
              {entry.policies_archived !== null ? formatNumber(entry.policies_archived) : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function DatabaseCleanupPage(): React.JSX.Element {
  const queryClient = useQueryClient();
  const [confirmInput, setConfirmInput] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string>("");

  const {
    data: preview,
    isFetching: previewLoading,
    error: previewError,
    refetch: refetchPreview,
  } = useQuery({
    queryKey: ["cleanup-preview"],
    queryFn: fetchCleanupPreview,
    enabled: false,       // manual trigger only
    retry: false,
  });

  const {
    data: history,
    isLoading: historyLoading,
  } = useQuery({
    queryKey: ["cleanup-history"],
    queryFn: fetchCleanupHistory,
    staleTime: 60_000,
  });

  const executeMutation = useMutation({
    mutationFn: executeCleanup,
    onSuccess: (result) => {
      setSuccessMessage(
        `Cleanup #${result.cleanup_id} completed. ${result.policies_archived ?? 0} policies archived.`
      );
      setConfirmInput("");
      // Invalidate affected queries so the UI reflects the clean state.
      queryClient.invalidateQueries({ queryKey: ["cleanup-history"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const canExecute =
    confirmInput === "CONFIRM" &&
    !executeMutation.isPending;

  return (
    <div className="db-cleanup">
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <header className="db-cleanup__header">
        <h1 className="db-cleanup__title">Database Cleanup</h1>
        <p className="db-cleanup__subtitle">
          Clear operational data to begin a new processing cycle. Configuration,
          themes, labels, and audit history are always preserved.
        </p>
      </header>

      {/* ── Preserved data section ───────────────────────────────────────── */}
      <section className="db-cleanup__preserved" aria-labelledby="preserved-heading">
        <h2 className="db-cleanup__section-title" id="preserved-heading">
          Always Preserved
        </h2>
        <ul className="db-cleanup__preserved-list">
          {PRESERVED_ITEMS.map((item) => (
            <li key={item} className="db-cleanup__preserved-item">
              <span className="db-cleanup__preserved-icon" aria-hidden="true">✓</span>
              {item}
            </li>
          ))}
        </ul>
      </section>

      {/* ── Preview section ──────────────────────────────────────────────── */}
      <section className="db-cleanup__preview-section" aria-labelledby="preview-heading">
        <div className="db-cleanup__section-header">
          <h2 className="db-cleanup__section-title" id="preview-heading">
            Step 1 — Preview
          </h2>
          <button
            className="db-cleanup__btn db-cleanup__btn--secondary"
            onClick={() => refetchPreview()}
            disabled={previewLoading}
            data-testid="cleanup-preview-btn"
            type="button"
          >
            {previewLoading ? "Loading…" : "Run Preview"}
          </button>
        </div>

        {previewError && (
          <p className="db-cleanup__error" role="alert">
            Failed to load preview. Please try again.
          </p>
        )}

        {preview && (
          <div className="db-cleanup__preview-results">
            <p className="db-cleanup__preview-summary">
              The following rows will be permanently deleted from this tenant.
            </p>
            <PreviewTable preview={preview} />
          </div>
        )}

        {!preview && !previewLoading && !previewError && (
          <p className="db-cleanup__hint">
            Click <strong>Run Preview</strong> to see a count of all rows that
            would be deleted before committing.
          </p>
        )}
      </section>

      {/* ── Execute section ──────────────────────────────────────────────── */}
      <section className="db-cleanup__execute-section" aria-labelledby="execute-heading">
        <h2 className="db-cleanup__section-title" id="execute-heading">
          Step 2 — Execute
        </h2>
        <p className="db-cleanup__execute-warning">
          <strong>This action is irreversible.</strong> Type{" "}
          <code className="db-cleanup__code">CONFIRM</code> in the field below
          to enable the execute button.
        </p>

        <div className="db-cleanup__confirm-row">
          <label htmlFor="confirm-input" className="db-cleanup__confirm-label">
            Type CONFIRM to proceed
          </label>
          <input
            id="confirm-input"
            type="text"
            className={`db-cleanup__confirm-input ${
              confirmInput.length > 0 && confirmInput !== "CONFIRM"
                ? "db-cleanup__confirm-input--invalid"
                : ""
            }`}
            value={confirmInput}
            onChange={(e) => {
              setConfirmInput(e.target.value);
              setSuccessMessage("");
              executeMutation.reset();
            }}
            placeholder="CONFIRM"
            autoComplete="off"
            spellCheck={false}
            data-testid="cleanup-confirm-input"
          />
          <button
            className="db-cleanup__btn db-cleanup__btn--danger"
            onClick={() => executeMutation.mutate()}
            disabled={!canExecute}
            data-testid="cleanup-execute-btn"
            type="button"
          >
            {executeMutation.isPending ? "Executing…" : "Execute Cleanup"}
          </button>
        </div>

        {executeMutation.isError && (
          <p className="db-cleanup__error" role="alert">
            Cleanup failed. Please check the history table for details.
          </p>
        )}

        {successMessage && (
          <p
            className="db-cleanup__success"
            role="status"
            data-testid="cleanup-success-msg"
          >
            {successMessage}
          </p>
        )}
      </section>

      {/* ── History section ──────────────────────────────────────────────── */}
      <section className="db-cleanup__history-section" aria-labelledby="history-heading">
        <h2 className="db-cleanup__section-title" id="history-heading">
          Cleanup History
        </h2>

        {historyLoading ? (
          <p className="db-cleanup__loading">Loading history…</p>
        ) : (
          <HistoryTable entries={history ?? []} />
        )}
      </section>
    </div>
  );
}
