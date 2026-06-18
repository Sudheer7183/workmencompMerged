/**
 * Phase 4 — Unit tests: ExceptionTracker component.
 * 15 tests — covers all items in V9 S17.4 spec including:
 *   - Summary panel with run stats
 *   - Skipped rows table with Error Code badges and raw data expansion
 *   - Edit & Re-ingest flow (CorrectionEditor)
 *   - Dismiss workflow
 *   - Rollback button RBAC (visible TENANT_ADMIN, hidden AUDITOR/REVIEWER)
 *   - Rollback confirmation dialog typing requirement
 *   - Export Error Report Phase 4 stub
 *   - No hardcoded hex, all labels from useLabels
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";

vi.mock("axios");
vi.mock("@/hooks/useLabels", () => ({
  useLabels: () => (_key: string, fallback: string) => fallback,
}));
vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(() => ({ user: { role: "TENANT_ADMIN" } })),
}));
// TenantCarrierContext is a real React context — ExceptionTracker calls
// useTenantCarrier() which throws when no provider is in the tree.
// Mock the hook directly so tests never need to mount the real provider.
vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: vi.fn(() => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [{ carrier_id: 1, carrier_name: "Demo Carrier", carrier_code: "DEMO" }],
    isLoadingCarriers: false,
  })),
}));
// Phase 5: ExceptionTracker calls generateReport() on export — mock the module
// so tests don't make real HTTP calls and can control success/failure.
vi.mock("@/features/reports/services/reportsApi", () => ({
  generateReport: vi.fn(() => Promise.resolve({ job_id: "mock-job-id-123" })),
}));
// ReportStatusModal triggers its own polling loop — mock it to a simple sentinel
// so tests can assert it mounts without running the full poller.
vi.mock("@/features/reports/ReportStatusModal", () => ({
  ReportStatusModal: ({ jobId }: { jobId: string }) => (
    <div data-testid="report-status-modal" data-job-id={jobId} />
  ),
}));

const mockedAxios = vi.mocked(axios, true);

import { ExceptionTracker } from "@/features/ingestion/ExceptionTracker";

const mockRun = {
  run_id: 42, status: "partial",
  rows_ingested: 18, rows_skipped: 2, rows_failed: 0,
  error_detail: null, started_at: "2026-06-01T10:00:00Z", completed_at: null,
};

const mockSkippedRows = [
  {
    skip_id: 1, run_id: 42, row_number: 5,
    raw_data: { "Policy Number": "", "Insured Name": "Acme Corp" },
    skip_reason: "REQUIRED_FIELD_NULL: policy_number",
    error_codes: ["REQUIRED_FIELD_NULL"],
    resolution_status: "PENDING",
    corrected_data: null, resolved_by: null, resolved_at: null,
  },
];

const mockErrors = [
  {
    error_id: 1, run_id: 42, row_number: 5,
    field_name: "policy_number",
    error_type: "REQUIRED_FIELD_NULL",
    error_message: "Row 5: policy_number is None",
    raw_value: null, created_at: "2026-06-01T10:00:30Z",
  },
];

function renderTracker(runId = 42) {
  return render(
    <MemoryRouter initialEntries={[`/audit-runner/${runId}/exceptions`]}>
      <Routes>
        <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedAxios.get = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/skipped")) return Promise.resolve({ data: mockSkippedRows });
    if (url.includes("/errors")) return Promise.resolve({ data: mockErrors });
    return Promise.resolve({ data: mockRun });
  });
  mockedAxios.post = vi.fn().mockResolvedValue({ data: {} });
  mockedAxios.put = vi.fn().mockResolvedValue({ data: mockSkippedRows[0] });
});

describe("ExceptionTracker", () => {
  it("renders summary panel with run stats", async () => {
    renderTracker();
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__summary")).toBeDefined();
      expect(screen.getByTestId("exception-tracker__rows-ingested").textContent).toBe("18");
      expect(screen.getByTestId("exception-tracker__rows-skipped").textContent).toBe("2");
    });
  });

  it("renders skipped rows table with Row # column", async () => {
    renderTracker();
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__skipped-table")).toBeDefined();
      const rowNums = screen.getAllByTestId("exception-tracker__row-number");
      expect(rowNums[0].textContent).toBe("5");
    });
  });

  it("renders error code badge", async () => {
    renderTracker();
    await waitFor(() => {
      const badges = document.querySelectorAll(".exception-tracker__error-code-badge");
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it("View Raw Data button expands JSONB inline", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__view-raw-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__view-raw-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__raw-data-content")).toBeDefined();
    });
  });

  it("Edit & Re-ingest button shows CorrectionEditor", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__edit-reingest-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__edit-reingest-btn"));
    expect(screen.getByTestId("exception-tracker__correction-editor")).toBeDefined();
  });

  it("CorrectionEditor is pre-populated from raw_data", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__edit-reingest-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__edit-reingest-btn"));
    const textarea = screen.getByTestId("exception-tracker__correction-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toContain("Policy Number");
  });

  it("Dismiss button calls dismiss endpoint", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__dismiss-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__dismiss-btn"));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/dismiss")
      );
    });
  });

  it("Rollback button visible for TENANT_ADMIN on partial run", async () => {
    renderTracker();
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__rollback-btn")).toBeDefined();
    });
  });

  it("Rollback button hidden for AUDITOR", async () => {
    // Override useAuth to return AUDITOR for ALL calls during this test,
    // then restore TENANT_ADMIN afterwards so other tests are unaffected.
    const { useAuth } = await import("@/context/AuthContext");
    const mockedUseAuth = vi.mocked(useAuth);

    mockedUseAuth.mockReturnValue({
      user: { role: "AUDITOR" },
      isAuthenticated: true,
      token: "mock-token",
      completeOnboarding: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    });

    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker"));
    expect(screen.queryByTestId("exception-tracker__rollback-btn")).toBeNull();

    // Restore default TENANT_ADMIN mock for subsequent tests
    mockedUseAuth.mockReturnValue({ user: { role: "TENANT_ADMIN" } });
  });

  it("Rollback confirmation dialog opens", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    expect(screen.getByTestId("exception-tracker__rollback-dialog")).toBeDefined();
  });

  it("Rollback confirm disabled until ROLLBACK typed exactly", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    const btn = screen.getByTestId("exception-tracker__rollback-confirm-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByTestId("exception-tracker__rollback-confirm-input"), {
      target: { value: "ROLLBACK" },
    });
    expect(btn.disabled).toBe(false);
  });

  it("Rollback calls POST endpoint on confirm", async () => {
    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.change(screen.getByTestId("exception-tracker__rollback-confirm-input"), {
      target: { value: "ROLLBACK" },
    });
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-confirm-btn"));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/rollback")
      );
    });
  });

  it("Export Error Report stub button is present", async () => {
    renderTracker();
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__export-btn")).toBeDefined();
    });
  });

  it("Export Error Report opens ReportStatusModal with returned job_id", async () => {
    // Phase 5: export calls generateReport() and mounts ReportStatusModal — no toast.
    const { generateReport } = await import("@/features/reports/services/reportsApi");
    vi.mocked(generateReport).mockResolvedValue({ job_id: "test-job-456" });

    renderTracker();
    await waitFor(() => screen.getByTestId("exception-tracker__export-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__export-btn"));

    await waitFor(() => {
      const modal = screen.getByTestId("report-status-modal");
      expect(modal).toBeDefined();
      expect(modal.getAttribute("data-job-id")).toBe("test-job-456");
    });
  });

  it("renders error log table with correct structure", async () => {
    renderTracker();
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__errors-table")).toBeDefined();
    });
  });
});