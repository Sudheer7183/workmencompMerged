/**
 * IngestionProgress — Phase 3.
 *
 * Displayed after TENANT_ADMIN approves a mapping session.
 * Polls GET /api/v1/ingestion/runs/{runId} every 2 s until status is
 * terminal (complete | partial | failed).
 *
 * On complete: show "Run Calculation Engine" button only when engine mode
 * is ON for this carrier (resolves via useCarrierCalcConfig).
 *
 * States handled:
 *   mapping_approved → "Mapping approved — preparing ingestion"
 *   processing       → animated progress indicator
 *   complete         → success + row count
 *   partial          → partial success + skipped count
 *   failed           → error detail + Try Again
 *
 * Route: /audit-runner/:runId/progress
 * V9 S16.5, S6.4
 */

import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useCarrierCalcConfig } from "@/features/carrier-config/hooks/useCarrierCalcConfig";
// import { fetchRunStatus, type IngestionRunStatus } from "./services/ingestionApi";
import axios from "axios";
import { fetchRunStatus, type IngestionRunStatus } from "./services/ingestionApi";


/** Status values that stop polling. */
const TERMINAL_STATUSES = new Set(["complete", "partial", "failed"]);

/** Polling interval in milliseconds. */
const POLL_INTERVAL_MS = 2_000;

interface StatusDisplayProps {
  run: IngestionRunStatus;
  engineEnabled: boolean;
  labels: ReturnType<typeof useLabels>;
  onRunEngine: () => void;
  onTryAgain: () => void;
}

function StatusDisplay({
  run,
  engineEnabled,
  labels,
  onRunEngine,
  onTryAgain,
}: StatusDisplayProps): React.JSX.Element {
  if (run.status === "mapping_approved") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--preparing">
        <span className="ingestion-progress__spinner" aria-hidden="true" />
        <p className="ingestion-progress__message">
          {labels.progress_mapping_approved ?? "Mapping approved — preparing ingestion…"}
        </p>
      </div>
    );
  }

  if (run.status === "processing" || run.status === "awaiting_mapping") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--processing">
        <span className="ingestion-progress__spinner" aria-hidden="true" />
        <p className="ingestion-progress__message">
          {labels.progress_processing ?? "Processing data — this may take a moment…"}
        </p>
      </div>
    );
  }

  if (run.status === "complete") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--complete">
        <span className="ingestion-progress__icon ingestion-progress__icon--success" aria-hidden="true">
          ✓
        </span>
        <p className="ingestion-progress__message">
          {labels.progress_complete ?? "Ingestion complete."}
        </p>
        <p className="ingestion-progress__detail">
          {labels.progress_rows_loaded ?? "Rows loaded:"}{" "}
          <strong>{run.rows_ingested ?? 0}</strong>
        </p>

        {engineEnabled && (
          <button
            className="btn btn--primary ingestion-progress__cta"
            onClick={onRunEngine}
          >
            {labels.btn_run_calc_engine ?? "Run Calculation Engine"}
          </button>
        )}
      </div>
    );
  }

  if (run.status === "partial") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--partial">
        <span className="ingestion-progress__icon ingestion-progress__icon--warning" aria-hidden="true">
          ⚠
        </span>
        <p className="ingestion-progress__message">
          {labels.progress_partial ?? "Ingestion partially completed."}
        </p>
        <p className="ingestion-progress__detail">
          {labels.progress_rows_loaded ?? "Rows loaded:"}{" "}
          <strong>{run.rows_ingested ?? 0}</strong>
          {" · "}
          {labels.progress_rows_skipped ?? "Skipped:"}{" "}
          <strong>{run.rows_skipped}</strong>
        </p>

        {engineEnabled && (
          <button
            className="btn btn--primary ingestion-progress__cta"
            onClick={onRunEngine}
          >
            {labels.btn_run_calc_engine ?? "Run Calculation Engine"}
          </button>
        )}
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="ingestion-progress__state ingestion-progress__state--failed">
        <span className="ingestion-progress__icon ingestion-progress__icon--error" aria-hidden="true">
          ✕
        </span>
        <p className="ingestion-progress__message">
          {labels.progress_failed ?? "Ingestion failed."}
        </p>
        {run.error_detail && (
          <pre className="ingestion-progress__error-detail">{run.error_detail}</pre>
        )}
        <button
          className="btn btn--secondary ingestion-progress__cta"
          onClick={onTryAgain}
        >
          {labels.btn_try_again ?? "Try Again"}
        </button>
      </div>
    );
  }

  // Unknown / transitional status
  return (
    <div className="ingestion-progress__state">
      <span className="ingestion-progress__spinner" aria-hidden="true" />
      <p className="ingestion-progress__message">
        {labels.progress_waiting ?? "Waiting for ingestion to start…"}
      </p>
    </div>
  );
}

export function IngestionProgress(): React.JSX.Element {
  const labels   = useLabels();
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const { carrierId } = useTenantCarrier();

  const numericRunId = runId != null ? Number(runId) : null;

  const { config: calcConfig } = useCarrierCalcConfig(carrierId);
  const engineEnabled = calcConfig?.use_calculation_engine ?? true;

  const [runStatus, setRunStatus]   = useState<IngestionRunStatus | null>(null);
  const [pollError, setPollError]   = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /** Fetch the current run status once and update state. */
  async function fetchOnce(): Promise<void> {
    if (numericRunId == null) return;
    try {
      const data = await fetchRunStatus(numericRunId);
      setRunStatus(data);
      setPollError(null);
      if (TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Polling error.";
      setPollError(msg);
      // Stop polling on auth errors — no point hammering the backend.
      // The axios interceptor (Fix 1) will have already attempted a token
      // refresh; if we still got 401 the session is truly expired.
      if (axios.isAxiosError(err) && (err.response?.status === 401 || err.response?.status === 403)) {
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
    intervalRef.current = setInterval(() => { void fetchOnce(); }, POLL_INTERVAL_MS);
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numericRunId]);

  function handleRunEngine(): void {
    if (numericRunId == null) return;
    navigate(`/policies`, {
      state: { triggerEngineRunId: numericRunId },
    });
  }

  function handleTryAgain(): void {
    navigate("/audit-runner");
  }

  if (numericRunId == null) {
    return (
      <div className="ingestion-progress ingestion-progress--error">
        <p>{labels.progress_no_run_id ?? "No run ID found. Please start a new upload."}</p>
        <button className="btn btn--primary" onClick={() => navigate("/audit-runner")}>
          {labels.btn_back_to_upload ?? "Back to Upload"}
        </button>
      </div>
    );
  }

  return (
    <div className="ingestion-progress">
      {/* Page header */}
      <div className="ingestion-progress__header">
        <h1 className="ingestion-progress__title">
          {labels.progress_title ?? "Ingestion Progress"}
        </h1>
        <p className="ingestion-progress__subtitle">
          {labels.progress_subtitle ?? "Run"} #{numericRunId}
        </p>
      </div>

      {/* Polling error banner */}
      {pollError != null && (
        <div className="ingestion-progress__poll-error" role="alert">
          {labels.progress_poll_error ?? "Could not reach server:"} {pollError}
        </div>
      )}

      {/* Main status area */}
      <div className="ingestion-progress__card">
        {runStatus == null ? (
          <div className="ingestion-progress__state">
            <span className="ingestion-progress__spinner" aria-hidden="true" />
            <p className="ingestion-progress__message">
              {labels.loading ?? "Loading…"}
            </p>
          </div>
        ) : (
          <StatusDisplay
            run={runStatus}
            engineEnabled={engineEnabled}
            labels={labels}
            onRunEngine={handleRunEngine}
            onTryAgain={handleTryAgain}
          />
        )}
      </div>
    </div>
  );
}