/**
 * RequestReportButton.test.tsx — Phase 5 unit tests.
 *
 * Tests for the RequestReportButton component: format dropdown,
 * single-button Excel-only mode, API calls, modal opening, and
 * coding standards compliance (no hardcoded hex, labels from useLabels).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { RequestReportButton } from "@/features/reports/RequestReportButton";
import * as reportsApi from "@/features/reports/services/reportsApi";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useLabels", () => ({
  useLabels: () => ({
    report_generate: "Generate Report",
    report_format_pdf: "PDF Report",
    report_format_excel: "Excel Report",
    report_export_excel: "Export Excel",
    loading: "Loading…",
    report_select_policy_first: "Select a policy first",
  }),
}));

vi.mock("@/features/reports/ReportStatusModal", () => ({
  ReportStatusModal: ({ jobId }: { jobId: string }) => (
    <div data-testid="report-status-modal" data-job-id={jobId} />
  ),
}));

vi.mock("@/features/reports/services/reportsApi", () => ({
  generateReport: vi.fn(),
  isExcelOnly: vi.fn((type: string) =>
    ["class_code_variance", "ingestion_audit_trail", "exception_report"].includes(type)
  ),
}));

const mockGenerateReport = vi.mocked(reportsApi.generateReport);

// ── Tests ──────────────────────────────────────────────────────────────────

describe("RequestReportButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGenerateReport.mockResolvedValue({ job_id: "test-job-uuid" });
  });

  test("renders single button for Excel-only report types", () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="exception_report"
        runId={42}
      />
    );
    const button = screen.getByTestId("generate-report-btn");
    expect(button).toBeTruthy();
    // No dropdown arrow for excel-only
    expect(button.textContent).not.toContain("▾");
  });

  test("renders dropdown with PDF and Excel options for policy_audit", async () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="policy_audit"
        policyId={10}
      />
    );
    const button = screen.getByTestId("generate-report-btn");
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId("report-format-dropdown")).toBeTruthy();
      expect(screen.getByTestId("format-pdf-option")).toBeTruthy();
      expect(screen.getByTestId("format-excel-option")).toBeTruthy();
    });
  });

  test("renders dropdown with PDF and Excel options for book_summary", async () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="book_summary"
      />
    );
    const button = screen.getByTestId("generate-report-btn");
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId("report-format-dropdown")).toBeTruthy();
    });
  });

  test("clicking PDF option calls generate endpoint with output_format='pdf'", async () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="policy_audit"
        policyId={10}
      />
    );
    fireEvent.click(screen.getByTestId("generate-report-btn"));

    await waitFor(() => screen.getByTestId("format-pdf-option"));
    fireEvent.click(screen.getByTestId("format-pdf-option"));

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledWith(
        expect.objectContaining({ output_format: "pdf" })
      );
    });
  });

  test("clicking Excel option calls generate endpoint with output_format='excel'", async () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="policy_audit"
        policyId={10}
      />
    );
    fireEvent.click(screen.getByTestId("generate-report-btn"));
    await waitFor(() => screen.getByTestId("format-excel-option"));
    fireEvent.click(screen.getByTestId("format-excel-option"));

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledWith(
        expect.objectContaining({ output_format: "excel" })
      );
    });
  });

  test("on successful response: opens ReportStatusModal", async () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="exception_report"
        runId={42}
      />
    );
    fireEvent.click(screen.getByTestId("generate-report-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("report-status-modal")).toBeTruthy();
    });
  });

  test("button disabled while request is in flight", async () => {
    let resolvePromise: (value: { job_id: string }) => void;
    mockGenerateReport.mockImplementation(
      () => new Promise((resolve) => { resolvePromise = resolve; })
    );

    render(
      <RequestReportButton
        carrierId={1}
        reportType="exception_report"
        runId={42}
      />
    );
    const button = screen.getByTestId("generate-report-btn");
    fireEvent.click(button);

    // Button should be disabled while loading
    expect(button).toBeDisabled();

    // Cleanup
    resolvePromise!({ job_id: "uuid" });
  });

  test("policy_audit without policyId prop — component renders disabled with tooltip", () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="policy_audit"
        // policyId intentionally omitted
      />
    );
    const button = screen.getByTestId("generate-report-btn");
    expect(button).toBeDisabled();
    expect(button.getAttribute("title")).toContain("policy");
  });

  test("no hardcoded hex colours in rendered output", () => {
    const { container } = render(
      <RequestReportButton
        carrierId={1}
        reportType="book_summary"
      />
    );
    const html = container.innerHTML;
    // Check for inline style with hardcoded hex — should not be present
    expect(html).not.toMatch(/style="[^"]*#[0-9a-fA-F]{3,6}/);
  });

  test("all labels from useLabels", () => {
    render(
      <RequestReportButton
        carrierId={1}
        reportType="book_summary"
        label={undefined}
      />
    );
    // Default label should come from useLabels
    const button = screen.getByTestId("generate-report-btn");
    expect(button.textContent).toContain("Generate Report");
  });
});
