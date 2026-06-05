/**
 * IngestionProgress.test.tsx — Phase 3
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { IngestionProgress } from "@/features/ingestion/IngestionProgress";

// ---------------------------------------------------------------------------
// Mock the ENTIRE TenantCarrierContext module so useTenantCarrier() never
// touches the real context and never throws "must be used within Provider".
// Also mock useCarrierCalcConfig to avoid a real API call for engine config.
// ---------------------------------------------------------------------------
let mockEngineEnabled = true;

vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: () => ({ carrierId: 1, setCarrierId: vi.fn(), availableCarriers: [], isLoadingCarriers: false }),
  TenantCarrierProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/features/carrier-config/hooks/useCarrierCalcConfig", () => ({
  useCarrierCalcConfig: () => ({
    config: { use_calculation_engine: mockEngineEnabled },
    isLoading: false,
    toggle: vi.fn(),
    isSaving: false,
  }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestWrapper({ runId = "10" }: { runId?: string }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter initialEntries={[`/audit-runner/${runId}/progress`]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/audit-runner/:runId/progress" element={<IngestionProgress />} />
          <Route path="/policies" element={<div>policies</div>} />
          <Route path="/audit-runner" element={<div>upload</div>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

function makeRunStatusHandler(status: string, extra: Partial<object> = {}) {
  return http.get("/api/v1/ingestion/runs/10", () =>
    HttpResponse.json({
      run_id: 10,
      status,
      rows_ingested: status === "complete" ? 125 : status === "partial" ? 50 : 0,
      rows_skipped: status === "partial" ? 3 : 0,
      rows_failed: 0,
      error_detail: status === "failed" ? "Column mismatch on row 5." : null,
      started_at: "2026-06-01T09:00:00+00:00",
      completed_at: status === "complete" ? "2026-06-01T09:01:00+00:00" : null,
      ...extra,
    })
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("IngestionProgress", () => {
  beforeEach(() => {
    mockEngineEnabled = true;
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("shows 'Mapping approved' text for status=mapping_approved", async () => {
    server.use(makeRunStatusHandler("mapping_approved"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Mapping approved/i)).toBeDefined();
    }, { timeout: 5000 });
  });

  it("shows spinner for status=processing", async () => {
    server.use(makeRunStatusHandler("processing"));
    render(<TestWrapper />);
    await waitFor(() => {
      const spinner = document.querySelector(".ingestion-progress__spinner");
      expect(spinner).not.toBeNull();
    }, { timeout: 5000 });
  });

  it("shows success message and row count for status=complete", async () => {
    server.use(makeRunStatusHandler("complete"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Ingestion complete/i)).toBeDefined();
      expect(screen.getByText("125")).toBeDefined();
    }, { timeout: 5000 });
  });

  it("shows partial message and skipped count for status=partial", async () => {
    server.use(makeRunStatusHandler("partial"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/partially completed/i)).toBeDefined();
      expect(screen.getByText("3")).toBeDefined();
    }, { timeout: 5000 });
  });

  it("shows error detail for status=failed", async () => {
    server.use(makeRunStatusHandler("failed"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Ingestion failed/i)).toBeDefined();
      expect(screen.getByText(/Column mismatch/i)).toBeDefined();
    }, { timeout: 5000 });
  });

  it("shows Try Again button for status=failed", async () => {
    server.use(makeRunStatusHandler("failed"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Try Again/i)).toBeDefined();
    }, { timeout: 5000 });
  });

  it("shows Run Calculation Engine button after complete when engine is ON", async () => {
    mockEngineEnabled = true;
    server.use(makeRunStatusHandler("complete"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Run Calculation Engine/i)).toBeDefined();
    }, { timeout: 5000 });
  });

  it("Run Calculation Engine button absent when engine is OFF", async () => {
    mockEngineEnabled = false;
    server.use(makeRunStatusHandler("complete"));
    render(<TestWrapper />);
    await waitFor(() => {
      expect(screen.getByText(/Ingestion complete/i)).toBeDefined();
    }, { timeout: 5000 });
    expect(screen.queryByText(/Run Calculation Engine/i)).toBeNull();
  });

  it("polls every 2 seconds while status is processing", async () => {
    vi.useFakeTimers();
    let callCount = 0;
    server.use(
      http.get("/api/v1/ingestion/runs/10", () => {
        callCount++;
        return HttpResponse.json({
          run_id: 10, status: "processing",
          rows_ingested: null, rows_skipped: 0, rows_failed: 0,
          error_detail: null, started_at: "2026-06-01T09:00:00+00:00", completed_at: null,
        });
      })
    );

    render(<TestWrapper />);
    await act(async () => { await Promise.resolve(); });
    const initial = callCount;

    await act(async () => {
      vi.advanceTimersByTime(4_100);
      await Promise.resolve();
    });

    expect(callCount).toBeGreaterThan(initial);
    vi.useRealTimers();
  });

  it("stops polling when status reaches terminal state (complete)", async () => {
    vi.useFakeTimers();
    let callCount = 0;
    server.use(
      http.get("/api/v1/ingestion/runs/10", () => {
        callCount++;
        return HttpResponse.json({
          run_id: 10, status: "complete",
          rows_ingested: 50, rows_skipped: 0, rows_failed: 0,
          error_detail: null, started_at: "2026-06-01T09:00:00+00:00",
          completed_at: "2026-06-01T09:01:00+00:00",
        });
      })
    );

    render(<TestWrapper />);
    await act(async () => { await Promise.resolve(); });
    const afterFirst = callCount;

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
    });

    expect(callCount - afterFirst).toBeLessThanOrEqual(1);
    vi.useRealTimers();
  });
});