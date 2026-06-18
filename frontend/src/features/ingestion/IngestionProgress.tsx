

import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams,useLocation  } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useCarrierCalcConfig } from "@/features/carrier-config/hooks/useCarrierCalcConfig";
import axios from "axios";
import { fetchRunStatus, runAuditEngine, type IngestionRunStatus } from "./services/ingestionApi";

/** Status values that stop polling. */
const TERMINAL_STATUSES = new Set(["complete", "partial", "failed"]);

/** Polling interval in milliseconds. */
const POLL_INTERVAL_MS = 2_000;

// ---------------------------------------------------------------------------
// StatusDisplay — receives label functions as props so it has no dependency
// on hook scope outside itself (Rules of Hooks: hooks must be called in the
// component that renders them, not inside sub-functions or child components
// that don't call the hook themselves).
// ---------------------------------------------------------------------------

interface StatusDisplayProps {
  run: IngestionRunStatus;
  engineEnabled: boolean;
  /** label_ingestion hook result passed from parent */
  labelIngestion: (key: string, fallback: string) => string;
  /** label_shared hook result passed from parent */
  labelShared: (key: string, fallback: string) => string;
  onRunEngine: () => void;
  onTryAgain: () => void;
  onViewErrors: (runId: number) => void;
  /** Whether the engine API call is in-flight */
  engineRunning: boolean;
  /** Error message from last engine run attempt, or null */
  engineError: string | null;
}

function StatusDisplay({
  run,
  engineEnabled,
  labelIngestion,
  labelShared,
  onRunEngine,
  onTryAgain,
  onViewErrors,
  engineRunning,
  engineError,
}: StatusDisplayProps): React.JSX.Element {
  if (run.status === "mapping_approved") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--preparing">
        <span className="ingestion-progress__spinner" aria-hidden="true" />
        <p className="ingestion-progress__message">
          {labelIngestion(
            "progress.mapping_approved",
            "Mapping approved — preparing ingestion…"
          )}
        </p>
      </div>
    );
  }

  if (run.status === "processing" || run.status === "awaiting_mapping") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--processing">
        <span className="ingestion-progress__spinner" aria-hidden="true" />
        <p className="ingestion-progress__message">
          {labelIngestion(
            "progress.processing",
            "Processing data — this may take a moment…"
          )}
        </p>
      </div>
    );
  }

  if (run.status === "complete") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--complete">
        <span
          className="ingestion-progress__icon ingestion-progress__icon--success"
          aria-hidden="true"
        >
          ✓
        </span>
        <p className="ingestion-progress__message">
          {labelIngestion("progress.complete", "Ingestion complete.")}
        </p>
        <p className="ingestion-progress__detail">
          {labelIngestion("progress.rows_loaded", "Rows loaded:")}{" "}
          <strong>{run.rows_ingested ?? 0}</strong>
        </p>
        {engineEnabled && (
          <button
            className="btn btn--primary ingestion-progress__cta"
            onClick={() => { onRunEngine(); }}
            disabled={engineRunning}
          >
            {engineRunning
              ? labelIngestion("btn.running_engine", "Running…")
              : labelIngestion("btn.run_calc_engine", "Run Calculation Engine")}
          </button>
        )}
        {engineError != null && (
          <p className="ingestion-progress__engine-error" role="alert">
            {engineError}
          </p>
        )}
      </div>
    );
  }

  if (run.status === "partial") {
    const runId = (run as { run_id?: number }).run_id;
    return (
      <div className="ingestion-progress__state ingestion-progress__state--partial">
        <span
          className="ingestion-progress__icon ingestion-progress__icon--warning"
          aria-hidden="true"
        >
          ⚠
        </span>
        <p className="ingestion-progress__message">
          {labelIngestion("progress.partial", "Ingestion partially completed.")}
        </p>
        <p className="ingestion-progress__detail">
          {labelIngestion("progress.rows_loaded", "Rows loaded:")}{" "}
          <strong>{run.rows_ingested ?? 0}</strong>
          {" · "}
          {labelIngestion("progress.rows_skipped", "Skipped:")}{" "}
          <strong>{run.rows_skipped}</strong>
        </p>
        <button
          className="btn btn--secondary ingestion-progress__view-errors-btn"
          onClick={() => { if (runId) onViewErrors(runId); }}
          data-testid="ingestion-progress__view-errors-btn"
        >
          {labelShared("btn.view_errors", "View Errors")}
        </button>
        {engineEnabled && (
          <button
            className="btn btn--primary ingestion-progress__cta"
            onClick={() => { onRunEngine(); }}
            disabled={engineRunning}
          >
            {engineRunning
              ? labelIngestion("btn.running_engine", "Running…")
              : labelIngestion("btn.run_calc_engine", "Run Calculation Engine")}
          </button>
        )}
        {engineError != null && (
          <p className="ingestion-progress__engine-error" role="alert">
            {engineError}
          </p>
        )}
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--failed">
        <span
          className="ingestion-progress__icon ingestion-progress__icon--error"
          aria-hidden="true"
        >
          ✕
        </span>
        <p className="ingestion-progress__message">
          {labelIngestion("progress.failed", "Ingestion failed.")}
        </p>
        {run.error_detail && (
          <pre className="ingestion-progress__error-detail">{run.error_detail}</pre>
        )}
        <button
          className="btn btn--secondary ingestion-progress__cta"
          onClick={onTryAgain}
        >
          {labelIngestion("btn.try_again", "Try Again")}
        </button>
      </div>
    );
  }

  // Unknown / transitional status
  return (
    <div className="ingestion-progress__state">
      <span className="ingestion-progress__spinner" aria-hidden="true" />
      <p className="ingestion-progress__message">
        {labelIngestion("progress.waiting", "Waiting for ingestion to start…")}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// IngestionProgress — main component
// ---------------------------------------------------------------------------

export function IngestionProgress(): React.JSX.Element {
  // FIX: useLabels() was called with no arguments. The hook requires a
  // ScreenKey. Declare the two needed hooks with their correct screen keys.
  const label_ingestion    = useLabels("ingestion");
  const label_shared       = useLabels("shared");
  const label_field_mapping = useLabels("field_mapping");

  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const { carrierId } = useTenantCarrier();
  const location = useLocation();
  const locationState = location.state as { ingestionMode?: string; bulkRunIds?: number[] } | null;
  const ingestionModeFromState = locationState?.ingestionMode ?? null;
  // For display_only bulk sessions, all run_ids are passed here so the narrative
  // call has complete data. If absent, falls back to single-run mode.
  const bulkRunIdsFromState = locationState?.bulkRunIds ?? [];

  const numericRunId = runId != null ? Number(runId) : null;

  const { config: calcConfig } = useCarrierCalcConfig(carrierId);
  const engineEnabled = calcConfig?.use_calculation_engine ?? true;

  const [runStatus, setRunStatus] = useState<IngestionRunStatus | null>(null);
  const [engineRunning, setEngineRunning] = useState(false);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [engineResult, setEngineResult] = useState<{ narrative_generated: boolean; engine_ran: boolean } | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchOnce(): Promise<void> {
    if (numericRunId == null) return;
    try {
      const data = await fetchRunStatus(numericRunId);
      setRunStatus(data);
      setPollError(null);
      if (TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
        // Auto-generate narrative for display_only runs when ingestion completes.
        // For display_only, engineEnabled may be false so the button is hidden
        // and the user would never manually trigger it.
        if (
          data.status === "complete" &&
          ingestionModeFromState === "display_only" &&
          carrierId != null &&
          numericRunId != null
        ) {
          // Only auto-trigger here when FieldMappingReview did NOT already fire
          // runAuditEngine (i.e. when navigated to directly, not from bulk queue).
          // When bulkRunIds is present, FieldMappingReview already called the LLM
          // with the full session run_ids — skip to avoid overwriting with partial data.
          if (bulkRunIdsFromState.length === 0) {
            void runAuditEngine(carrierId, numericRunId).catch(() => {
              // Non-fatal — narrative generation failure shouldn't block the page
            });
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Polling error.";
      setPollError(msg);
      if (
        axios.isAxiosError(err) &&
        (err.response?.status === 401 || err.response?.status === 403)
      ) {
        stopPolling();
      }
    }
  }

  function stopPolling(): void {
    if (intervalRef.current != null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  useEffect(() => {
    void fetchOnce();
    intervalRef.current = setInterval(() => {
      void fetchOnce();
    }, POLL_INTERVAL_MS);
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numericRunId]);

  async function handleRunEngine(): Promise<void> {
    if (numericRunId == null || carrierId == null) return;
    setEngineRunning(true);
    setEngineError(null);
    setEngineResult(null);
    try {
      const result = await runAuditEngine(carrierId, numericRunId);
      setEngineResult({
        narrative_generated: result.narrative_generated,
        engine_ran: result.engine_ran,
      });
      // Navigate to the policy detail page to show the results and narrative
      if (result.policy_id) {
        navigate(`/policies/${result.policy_id}`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Engine run failed.";
      setEngineError(message);
    } finally {
      setEngineRunning(false);
    }
  }

  function handleTryAgain(): void {
    navigate("/audit-runner");
  }

  function handleViewErrors(runId: number): void {
    navigate(`/audit-runner/${runId}/exceptions`);
  }

  if (numericRunId == null) {
    return (
      <div className="ingestion-progress ingestion-progress--error">
        <p>
          {label_ingestion(
            "progress.no_run_id",
            "No run ID found. Please start a new upload."
          )}
        </p>
        <button
          className="btn btn--primary"
          onClick={() => navigate("/audit-runner")}
        >
          {label_field_mapping("btn.back_to_upload", "Back to Upload")}
        </button>
      </div>
    );
  }

  return (
    <div className="ingestion-progress">
      {/* Page header */}
      <div className="ingestion-progress__header">
        <h1 className="ingestion-progress__title">
          {label_ingestion("progress.title", "Ingestion Progress")}
        </h1>
        <p className="ingestion-progress__subtitle">
          {label_ingestion("progress.subtitle", "Run")} #{numericRunId}
        </p>
      </div>

      {/* Polling error banner */}
      {pollError != null && (
        <div className="ingestion-progress__poll-error" role="alert">
          {label_ingestion("progress.poll_error", "Could not reach server:")}{" "}
          {pollError}
        </div>
      )}

      {/* Main status area */}
      <div className="ingestion-progress__card">
        {runStatus == null ? (
          <div className="ingestion-progress__state">
            <span className="ingestion-progress__spinner" aria-hidden="true" />
            <p className="ingestion-progress__message">
              {label_shared("loading", "Loading…")}
            </p>
          </div>
        ) : (
          <StatusDisplay
            run={runStatus}
            engineEnabled={engineEnabled}
            labelIngestion={label_ingestion}
            labelShared={label_shared}
            onRunEngine={() => { void handleRunEngine(); }}
            onTryAgain={handleTryAgain}
            onViewErrors={handleViewErrors}
            engineRunning={engineRunning}
            engineError={engineError}
          />
        )}
      </div>
    </div>
  );
}