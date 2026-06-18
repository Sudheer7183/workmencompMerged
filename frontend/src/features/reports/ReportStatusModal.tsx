/**
 * ReportStatusModal.tsx — Phase 5
 *
 * Modal that wraps ReportJobPoller and ReportDownloadLink.
 * Shows three visual states:
 *   GENERATING — spinner + "Generating your report..."
 *   COMPLETE   — checkmark + "Report ready" + Download Now button
 *   FAILED     — error icon + message + Retry button
 *
 * Per V9 S26.
 */

import React, { useCallback, useState } from "react";
import { ReportJobPoller } from "./ReportJobPoller";
import { ReportDownloadLink } from "./ReportDownloadLink";
import { type OutputFormat, type ReportType } from "./services/reportsApi";
import { useLabels } from "@/hooks/useLabels";

type ModalState = "GENERATING" | "COMPLETE" | "FAILED";

interface ReportStatusModalProps {
  /** job_id returned by POST /reports/generate */
  jobId: string;
  reportType: ReportType;
  outputFormat: OutputFormat;
  policyNumber?: string;
  /** Called when the user closes the modal */
  onClose: () => void;
  /** Called when the user clicks Retry — parent should re-generate */
  onRetry: () => void;
}

export function ReportStatusModal({
  jobId,
  reportType,
  outputFormat,
  policyNumber,
  onClose,
  onRetry,
}: ReportStatusModalProps): React.JSX.Element {
  const label_reports = useLabels("reports");
  const label_shared = useLabels("shared");
  const [modalState, setModalState] = useState<ModalState>("GENERATING");
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  const handleComplete = useCallback((url: string): void => {
    setFileUrl(url);
    setModalState("COMPLETE");
  }, []);

  const handleError = useCallback((detail: string): void => {
    setErrorDetail(detail);
    setModalState("FAILED");
  }, []);

  return (
    <div
      className="report-status-modal__overlay"
      role="dialog"
      aria-modal="true"
      aria-label={label_reports("modal.status_title", "report_status_modal_title") ?? "Report Status"}
      data-testid="report-status-modal"
    >
      {/* The poller is render-less — mounts while GENERATING, stops on terminal state */}
      {modalState === "GENERATING" && (
        <ReportJobPoller
          jobId={jobId}
          onComplete={handleComplete}
          onError={handleError}
        />
      )}

      <div className="report-status-modal__panel">
        <button
          type="button"
          className="report-status-modal__close"
          onClick={onClose}
          aria-label={label_shared("close", "close") ?? "Close"}
          data-testid="report-modal-close-btn"
        >
          ✕
        </button>

        {/* ── GENERATING ──────────────────────────────────────────────────── */}
        {modalState === "GENERATING" && (
          <div
            className="report-status-modal__body"
            data-testid="report-status-generating"
          >
            <div
              className="report-status-modal__spinner"
              role="status"
              aria-label={label_reports("status.generating", "report_generating") ?? "Generating…"}
            />
            <p className="report-status-modal__status-text">
              {label_reports("status.generating", "report_generating") ?? "Generating your report…"}
            </p>
            <p className="report-status-modal__detail">
              {label_reports("status.generating_detail", "report_generating_detail") ??
                "This may take a few moments. The file will download automatically when ready."}
            </p>
          </div>
        )}

        {/* ── COMPLETE ────────────────────────────────────────────────────── */}
        {modalState === "COMPLETE" && fileUrl && (
          <div
            className="report-status-modal__body"
            data-testid="report-status-complete"
          >
            <span
              className="report-status-modal__icon--success"
              aria-hidden="true"
            >
              ✅
            </span>
            <p className="report-status-modal__status-text">
              {label_reports("status.ready", "report_ready") ?? "Report ready!"}
            </p>
            <div className="report-status-modal__actions">
              <ReportDownloadLink
                fileUrl={fileUrl}
                reportType={reportType}
                outputFormat={outputFormat}
                policyNumber={policyNumber}
              />
              <button
                type="button"
                className="btn btn--ghost"
                onClick={onClose}
              >
                {label_shared("close", "close") ?? "Close"}
              </button>
            </div>
          </div>
        )}

        {/* ── FAILED ──────────────────────────────────────────────────────── */}
        {modalState === "FAILED" && (
          <div
            className="report-status-modal__body"
            data-testid="report-status-failed"
          >
            <span
              className="report-status-modal__icon--error"
              aria-hidden="true"
            >
              ❌
            </span>
            <p className="report-status-modal__status-text">
              {label_reports("status.failed", "report_failed") ?? "Report generation failed"}
            </p>
            {errorDetail && (
              <p className="report-status-modal__detail">{errorDetail}</p>
            )}
            <div className="report-status-modal__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={onRetry}
                data-testid="report-retry-btn"
              >
                {label_shared("retry", "retry") ?? "Retry"}
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={onClose}
              >
                {label_shared("close", "close") ?? "Close"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
