/**
 * Phase 4 — Frontend integration test: Rollback flow.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";

vi.mock("axios");
vi.mock("@/hooks/useLabels", () => ({ useLabels: () => ({}) }));

const mockedAxios = vi.mocked(axios, true);

import { ExceptionTracker } from "@/features/ingestion/ExceptionTracker";

const makeRun = (status: string) => ({
  run_id: 42, status, rows_ingested: 18,
  rows_skipped: 2, rows_failed: 0,
  error_detail: null, started_at: "", completed_at: null,
});

function renderExceptionTracker(role: string) {
  vi.mock("@/context/AuthContext", () => ({
    useAuth: () => ({ user: { role } }),
  }));
  return render(
    <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
      <Routes>
        <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RollbackFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mock("@/context/AuthContext", () => ({
      useAuth: () => ({ user: { role: "TENANT_ADMIN" } }),
    }));
    mockedAxios.get = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/skipped")) return Promise.resolve({ data: [] });
      if (url.includes("/errors")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: makeRun("partial") });
    });
    mockedAxios.post = vi.fn().mockResolvedValue({ data: { rollback_id: 1, status: "COMPLETE", rows_removed: 18 } });
  });

  it("TENANT_ADMIN sees Rollback button for partial run", async () => {
    render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId("exception-tracker__rollback-btn")).toBeDefined();
    });
  });

  it("Rollback dialog opens when button clicked", async () => {
    render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    expect(screen.getByTestId("exception-tracker__rollback-dialog")).toBeDefined();
  });

  it("Rollback confirm button disabled until ROLLBACK typed", async () => {
    render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    const btn = screen.getByTestId("exception-tracker__rollback-confirm-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByTestId("exception-tracker__rollback-confirm-input"), {
      target: { value: "ROLLBACK" },
    });
    expect(btn.disabled).toBe(false);
  });

  it("Rollback submits POST when confirmed", async () => {
    render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-btn"));
    fireEvent.change(screen.getByTestId("exception-tracker__rollback-confirm-input"), {
      target: { value: "ROLLBACK" },
    });
    fireEvent.click(screen.getByTestId("exception-tracker__rollback-confirm-btn"));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/v1/ingestion/runs/42/rollback",
        undefined
      );
    });
  });

  it("AUDITOR does not see Rollback button", async () => {
    vi.doMock("@/context/AuthContext", () => ({
      useAuth: () => ({ user: { role: "AUDITOR" } }),
    }));
    render(
      <MemoryRouter initialEntries={["/audit-runner/42/exceptions"]}>
        <Routes>
          <Route path="/audit-runner/:runId/exceptions" element={<ExceptionTracker />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId("exception-tracker"));
    expect(screen.queryByTestId("exception-tracker__rollback-btn")).toBeNull();
  });
});
