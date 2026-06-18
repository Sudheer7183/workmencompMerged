/**
 * Phase 4 — Frontend integration test: Full ingestion flow.
 * Tests happy path XLSX → partial with errors → ExceptionTracker navigation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";

vi.mock("axios");
vi.mock("@/hooks/useLabels", () => ({ useLabels: () => ({}) }));
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { role: "AUDITOR", email: "auditor@demo.com" } }),
}));
vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: () => ({ carrierId: 1, tenantSlug: "demo" }),
}));
vi.mock("@/features/carrier-config/hooks/useCarrierCalcConfig", () => ({
  useCarrierCalcConfig: () => ({ data: { use_calculation_engine: true }, loading: false }),
}));

const mockedAxios = vi.mocked(axios, true);

import { IngestionProgress } from "@/features/ingestion/IngestionProgress";
import { ExceptionTracker } from "@/features/ingestion/ExceptionTracker";

function renderProgress(runId: number) {
  return render(
    <MemoryRouter initialEntries={[`/audit-runner/${runId}/progress`]}>
      <Routes>
        <Route path="/audit-runner/:runId/progress" element={<IngestionProgress />} />
        <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("IngestionFlowFull", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows complete status with row count after polling resolves", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 1,
        status: "complete",
        rows_ingested: 25,
        rows_skipped: 0,
        rows_failed: 0,
        error_detail: null,
        started_at: "2026-06-01T10:00:00Z",
        completed_at: "2026-06-01T10:01:00Z",
      },
    });
    renderProgress(1);
    await waitFor(() => {
      expect(screen.getByText(/25/)).toBeDefined();
    });
  });

  it("shows partial status with skipped count", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 2,
        status: "partial",
        rows_ingested: 18,
        rows_skipped: 2,
        rows_failed: 0,
        error_detail: null,
        started_at: "2026-06-01T10:00:00Z",
        completed_at: "2026-06-01T10:01:00Z",
      },
    });
    renderProgress(2);
    await waitFor(() => {
      expect(screen.getByText(/2/)).toBeDefined();
    });
  });

  it("View Errors button appears for partial status", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 3, status: "partial", rows_ingested: 10,
        rows_skipped: 1, rows_failed: 0, error_detail: null,
        started_at: "", completed_at: null,
      },
    });
    renderProgress(3);
    await waitFor(() => {
      expect(screen.getByTestId("ingestion-progress__view-errors-btn")).toBeDefined();
    });
  });

  it("shows Run Calculation Engine button after complete when engine ON", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 4, status: "complete", rows_ingested: 20,
        rows_skipped: 0, rows_failed: 0, error_detail: null,
        started_at: "", completed_at: "2026-06-01T10:01:00Z",
      },
    });
    renderProgress(4);
    await waitFor(() => {
      expect(screen.getByText(/Run Calculation Engine/i)).toBeDefined();
    });
  });

  it("shows error detail for failed status", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 5, status: "failed", rows_ingested: 0,
        rows_skipped: 0, rows_failed: 0,
        error_detail: "XML parse error at line 12",
        started_at: "", completed_at: null,
      },
    });
    renderProgress(5);
    await waitFor(() => {
      expect(screen.getByText(/XML parse error at line 12/i)).toBeDefined();
    });
  });

  it("CSV upload: shows same progress states as XLSX", async () => {
    // CSV ingestion uses the same run-status polling — no UI difference
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: {
        run_id: 6, status: "complete", rows_ingested: 8,
        rows_skipped: 0, rows_failed: 0, error_detail: null,
        started_at: "", completed_at: "2026-06-01T10:02:00Z",
      },
    });
    renderProgress(6);
    await waitFor(() => {
      expect(screen.getByText(/8/)).toBeDefined();
    });
  });

  it("ExceptionTracker renders when navigated to", async () => {
    mockedAxios.get = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/skipped")) return Promise.resolve({ data: [] });
      if (url.includes("/errors")) return Promise.resolve({ data: [] });
      return Promise.resolve({
        data: {
          run_id: 7, status: "partial", rows_ingested: 5,
          rows_skipped: 1, rows_failed: 0, error_detail: null,
          started_at: "", completed_at: null,
        },
      });
    });

    render(
      <MemoryRouter initialEntries={["/audit-runner/7/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker")).toBeDefined();
    });
  });
});
