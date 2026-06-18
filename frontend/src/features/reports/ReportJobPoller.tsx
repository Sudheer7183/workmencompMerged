/**
 * ReportJobPoller.tsx — Phase 5
 *
 * Polls GET /api/v1/reports/{jobId}/status every 3 seconds while status is
 * QUEUED or PROCESSING. Calls onComplete(file_url) when COMPLETE, or
 * onError(detail) when FAILED. Stops automatically after 5 minutes.
 *
 * Per V9 S26.
 */

import { useEffect, useRef } from "react";
import { getReportStatus, type JobStatus } from "./services/reportsApi";

interface ReportJobPollerProps {
  /** UUID job_id returned from POST /reports/generate */
  jobId: string;
  /** Called when status transitions to COMPLETE with the file_url */
  onComplete: (fileUrl: string) => void;
  /** Called when status transitions to FAILED with the error_detail */
  onError: (detail: string) => void;
}

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_DURATION_MS = 5 * 60 * 1000; // 5 minutes

export function ReportJobPoller({
  jobId,
  onComplete,
  onError,
}: ReportJobPollerProps): null {
  const startTimeRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef<boolean>(true);

  useEffect(() => {
    activeRef.current = true;
    startTimeRef.current = Date.now();

    async function poll(): Promise<void> {
      if (!activeRef.current) return;

      // Timeout guard — stop polling after MAX_POLL_DURATION_MS
      if (Date.now() - startTimeRef.current > MAX_POLL_DURATION_MS) {
        onError(
          "Report generation timed out after 5 minutes. Please try again."
        );
        return;
      }

      try {
        const statusData = await getReportStatus(jobId);
        if (!activeRef.current) return;

        if (statusData.status === "COMPLETE") {
          onComplete(statusData.file_url ?? "");
          return;
        }

        if (statusData.status === "FAILED") {
          onError(
            statusData.error_detail ??
              "Report generation failed. Please try again."
          );
          return;
        }

        // QUEUED or PROCESSING — schedule next poll
        timerRef.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      } catch {
        if (!activeRef.current) return;
        // Network errors are transient — retry unless we've exceeded the timeout
        timerRef.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    }

    void poll();

    return () => {
      activeRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [jobId, onComplete, onError]);

  // Render-less component — purely orchestrates polling side-effects
  return null;
}
