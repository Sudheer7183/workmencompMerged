/**
 * ExceptionReportActivation.test.tsx — Phase 5 frontend integration tests.
 *
 * Verifies the Phase 4 → Phase 5 activation:
 *   - "Export Error Report" calls the real generate endpoint (not 501 toast)
 *   - Correct payload: report_type='exception_report', run_id present
 *   - ReportStatusModal opens after clicking
 *   - Phase 4 stub toast is no longer shown
 *
 * Per Phase 5 prompt Section 7 test spec.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as reportsApi from "@/features/reports/services/reportsApi";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useLabels", () => ({
  useLabels: () => ({
    loading: "Loading…",
    btn_export_error_report: "Export Error Report",
    btn_rollback: "Rollback",
    exception_tracker_title: "Exception Tracker",
    exception_tracker_errors_title: "Errors",
    exception_tracker_skipped_title: "Skipped Rows",
    col_row_number: "Row",
    col_error_code: "Code",
    col_error_message: "Message",
    col_field_name: "Field",
    col_raw_value: "Raw Value",
    col_skip_reason: "Reason",
    col_resolution_status: "Status",
    run_status: "Status",
    run_total_rows: "Total Rows",
    run_skipped: "Skipped",
    run_processed: "Processed",
    report_generating: "Generating your report…",
    report_ready: "Report ready!",
    report_failed: "Report generation failed",
    report_download_now: "Download Now",
    retry: "Retry",
    close: "Close",
  }),
}));

vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: () => ({ carrierId: 1 }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { role: "TENANT_ADMIN", email: "admin@test.com" },
  }),
}));

vi.mock("@/features/reports/services/reportsApi", () => ({
  generateReport: vi.fn(),
  getReportStatus: vi.fn(),
  isExcelOnly: () => true,
}));

// Mock axios for ExceptionTracker data calls
vi.mock("axios", () => ({
  default: {
    get: vi.fn().mockImplementation((url: string) => {
      if (url.includes("/runs/42")) {
        return Promise.resolve({
          data: {
            run_id: 42,
            status: "partial",
            total_rows: 100,
            processed_rows: 95,
            skipped_rows: 5,
            carrier_id: 1,
            started_at: "2026-01-01T00:00:00Z",
            completed_at: "2026-01-01T00:01:00Z",
            skip_on_error: true,
          },
        });
      }
      if (url.includes("/skipped")) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes("/errors")) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: {} });
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    isAxiosError: () => false,
  },
}));

const mockGenerateReport = vi.mocked(reportsApi.generateReport);
const mockGetStatus = vi.mocked(reportsApi.getReportStatus);

// ── Tests ──────────────────────────────────────────────────────────────────

describe("ExceptionReportActivation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGenerateReport.mockResolvedValue({ job_id: "exception-report-job" });
    mockGetStatus.mockResolvedValue({
      job_id: "exception-report-job",
      status: "QUEUED",
      file_url: null,
      report_type: "exception_report",
      output_format: "excel",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });
  });

  async function renderExceptionTracker() {
    const { ExceptionTracker } = await import(
      "@/features/ingestion/ExceptionTracker"
    );
    return render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route
            path="/audit-runner/:runId/exceptions"
            element={<ExceptionTracker />}
          />
        </Routes>
      </MemoryRouter>
    );
  }

  test("Export Error Report button calls generate endpoint (not shows 501 toast)", async () => {
    await renderExceptionTracker();
    await waitFor(() =>
      screen.getByTestId("exception-tracker__export-btn")
    );

    fireEvent.click(screen.getByTestId("exception-tracker__export-btn"));

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledTimes(1);
    });
  });

  test("generates report with report_type='exception_report' and run_id", async () => {
    await renderExceptionTracker();
    await waitFor(() =>
      screen.getByTestId("exception-tracker__export-btn")
    );

    fireEvent.click(screen.getByTestId("exception-tracker__export-btn"));

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledWith(
        expect.objectContaining({
          report_type: "exception_report",
          output_format: "excel",
          run_id: 42,
          carrier_id: 1,
        })
      );
    });
  });

  test("opens ReportStatusModal after clicking Export Error Report", async () => {
    await renderExceptionTracker();
    await waitFor(() =>
      screen.getByTestId("exception-tracker__export-btn")
    );

    fireEvent.click(screen.getByTestId("exception-tracker__export-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("report-status-modal")).toBeTruthy();
    });
  });

  test("Phase 4 stub toast is no longer shown", async () => {
    await renderExceptionTracker();
    await waitFor(() =>
      screen.getByTestId("exception-tracker__export-btn")
    );

    fireEvent.click(screen.getByTestId("exception-tracker__export-btn"));

    // Wait a tick
    await waitFor(() => expect(mockGenerateReport).toHaveBeenCalled());

    // The Phase 4 stub toast text must not be present
    expect(
      screen.queryByText("Report generation available in Phase 5.")
    ).toBeNull();

    // Also check the old toast container is gone
    expect(
      screen.queryByTestId("exception-tracker__export-toast")
    ).toBeNull();
  });
});
