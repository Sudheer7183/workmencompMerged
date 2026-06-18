/**
 * ReportStatusModal.test.tsx — Phase 5 unit tests.
 *
 * Tests for the ReportStatusModal component: three visual states
 * (GENERATING / COMPLETE / FAILED), polling lifecycle, and user actions.
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { ReportStatusModal } from "@/features/reports/ReportStatusModal";
import * as reportsApi from "@/features/reports/services/reportsApi";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useLabels", () => ({
  useLabels: () => ({
    report_generating: "Generating your report…",
    report_generating_detail: "This may take a few moments.",
    report_ready: "Report ready!",
    report_failed: "Report generation failed",
    report_download_now: "Download Now",
    retry: "Retry",
    close: "Close",
  }),
}));

vi.mock("@/features/reports/services/reportsApi", () => ({
  getReportStatus: vi.fn(),
}));

// ReportDownloadLink is a simple button — use real component
vi.mock("@/features/reports/ReportDownloadLink", () => ({
  ReportDownloadLink: ({ fileUrl }: { fileUrl: string }) => (
    <button data-testid="report-download-btn" onClick={() => window.open(fileUrl)}>
      Download Now
    </button>
  ),
}));

const mockGetReportStatus = vi.mocked(reportsApi.getReportStatus);

function makeProps(overrides = {}) {
  return {
    jobId: "test-job-id",
    reportType: "policy_audit" as const,
    outputFormat: "pdf" as const,
    onClose: vi.fn(),
    onRetry: vi.fn(),
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("ReportStatusModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders spinner and GENERATING text when status is QUEUED", async () => {
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "QUEUED",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    render(<ReportStatusModal {...makeProps()} />);
    expect(screen.getByTestId("report-status-generating")).toBeTruthy();
    expect(screen.getByText("Generating your report…")).toBeTruthy();
  });

  test("renders spinner when status is PROCESSING", () => {
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "PROCESSING",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    render(<ReportStatusModal {...makeProps()} />);
    expect(screen.getByTestId("report-status-generating")).toBeTruthy();
  });

  test("renders checkmark and Download Now button when status is COMPLETE", async () => {
    const fileUrl = "https://minio/bucket/report.pdf?expires=123";
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "COMPLETE",
      file_url: fileUrl,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    render(<ReportStatusModal {...makeProps()} />);

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    await waitFor(() => {
      expect(screen.getByTestId("report-status-complete")).toBeTruthy();
      expect(screen.getByTestId("report-download-btn")).toBeTruthy();
    });
  });

  test("Download Now button opens file_url in new tab", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const fileUrl = "https://minio/bucket/report.pdf";

    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "COMPLETE",
      file_url: fileUrl,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    render(<ReportStatusModal {...makeProps()} />);
    await act(async () => { await vi.runAllTimersAsync(); });

    await waitFor(() => screen.getByTestId("report-download-btn"));
    fireEvent.click(screen.getByTestId("report-download-btn"));

    expect(openSpy).toHaveBeenCalledWith(fileUrl);
  });

  test("renders error icon and detail when status is FAILED", async () => {
    const errorDetail = "Database connection failed during generation";
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "FAILED",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: errorDetail,
    });

    render(<ReportStatusModal {...makeProps()} />);
    await act(async () => { await vi.runAllTimersAsync(); });

    await waitFor(() => {
      expect(screen.getByTestId("report-status-failed")).toBeTruthy();
      expect(screen.getByText(errorDetail)).toBeTruthy();
    });
  });

  test("Retry button is visible on FAILED status", async () => {
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "FAILED",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: "Failed",
    });

    render(<ReportStatusModal {...makeProps()} />);
    await act(async () => { await vi.runAllTimersAsync(); });

    await waitFor(() => {
      expect(screen.getByTestId("report-retry-btn")).toBeTruthy();
    });
  });

  test("Retry button calls onRetry prop", async () => {
    const onRetry = vi.fn();
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "FAILED",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: "Failed",
    });

    render(<ReportStatusModal {...makeProps({ onRetry })} />);
    await act(async () => { await vi.runAllTimersAsync(); });

    await waitFor(() => screen.getByTestId("report-retry-btn"));
    fireEvent.click(screen.getByTestId("report-retry-btn"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  test("modal closes when X button clicked", () => {
    const onClose = vi.fn();
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id",
      status: "QUEUED",
      file_url: null,
      report_type: "policy_audit",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    render(<ReportStatusModal {...makeProps({ onClose })} />);
    fireEvent.click(screen.getByTestId("report-modal-close-btn"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  test("polling stops when status reaches COMPLETE", async () => {
    const fileUrl = "https://minio/bucket/report.pdf";
    let callCount = 0;
    mockGetReportStatus.mockImplementation(async () => {
      callCount++;
      if (callCount >= 2) {
        return {
          job_id: "test-job-id", status: "COMPLETE" as const,
          file_url: fileUrl, report_type: "policy_audit" as const,
          output_format: "pdf" as const,
          requested_at: null, completed_at: null, error_detail: null,
        };
      }
      return {
        job_id: "test-job-id", status: "PROCESSING" as const,
        file_url: null, report_type: "policy_audit" as const,
        output_format: "pdf" as const,
        requested_at: null, completed_at: null, error_detail: null,
      };
    });

    render(<ReportStatusModal {...makeProps()} />);
    await act(async () => { await vi.runAllTimersAsync(); });

    const countAtComplete = callCount;
    // After reaching COMPLETE, no more poll calls should happen
    await act(async () => { await vi.runAllTimersAsync(); });
    expect(callCount).toBe(countAtComplete);
  });

  test("polling stops when status reaches FAILED", async () => {
    let callCount = 0;
    mockGetReportStatus.mockImplementation(async () => {
      callCount++;
      return {
        job_id: "test-job-id", status: "FAILED" as const,
        file_url: null, report_type: "policy_audit" as const,
        output_format: "pdf" as const,
        requested_at: null, completed_at: null, error_detail: "Error",
      };
    });

    render(<ReportStatusModal {...makeProps()} />);
    await act(async () => { await vi.runAllTimersAsync(); });
    const countAtFailed = callCount;
    await act(async () => { await vi.runAllTimersAsync(); });
    expect(callCount).toBe(countAtFailed);
  });

  test("shows error after 5 minutes of polling without completion", async () => {
    mockGetReportStatus.mockResolvedValue({
      job_id: "test-job-id", status: "PROCESSING" as const,
      file_url: null, report_type: "policy_audit" as const,
      output_format: "pdf" as const,
      requested_at: null, completed_at: null, error_detail: null,
    });

    render(<ReportStatusModal {...makeProps()} />);

    // Fast-forward 5+ minutes
    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000 + 3000);
      await vi.runAllTimersAsync();
    });

    await waitFor(() => {
      expect(screen.getByTestId("report-status-failed")).toBeTruthy();
    });
  });
});
