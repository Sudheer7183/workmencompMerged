/**
 * AuditRunnerPage.test.tsx — Phase 3
 *
 * Tests:
 *   - Upload File button / dropzone is present
 *   - File type indicators show XLSX enabled, CSV/XML as disabled
 *   - Submitting without a file shows an error
 *   - XLSX file accepted; non-XLSX rejected with error message
 *   - Navigates to /audit-runner/{runId}/mapping on successful upload
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuditRunnerPage } from "@/features/ingestion/AuditRunnerPage";

// ---------------------------------------------------------------------------
// Mock TenantCarrierContext — avoids real provider requirement
// ---------------------------------------------------------------------------
vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: () => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [],
    isLoadingCarriers: false,
  }),
  TenantCarrierProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ---------------------------------------------------------------------------
// Mock ingestionApi — bypass all HTTP/MSW overhead for deterministic tests.
// The component's responsibility is: select file → call uploadFile → navigate.
// Network-layer correctness is covered by backend integration tests.
// ---------------------------------------------------------------------------
const mockUploadFile = vi.fn();

vi.mock("@/features/ingestion/services/ingestionApi", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("@/features/ingestion/services/ingestionApi")
  >();
  return {
    ...actual,
    uploadFile: (...args: unknown[]) => mockUploadFile(...args),
  };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter initialEntries={["/audit-runner"]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/audit-runner" element={<AuditRunnerPage />} />
          <Route
            path="/audit-runner/:runId/mapping"
            element={<div data-testid="mapping-page">mapping</div>}
          />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

function makeXlsxFile(name = "data.xlsx"): File {
  const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04]);
  return new File([bytes], name, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

function getSubmitBtn(): HTMLElement {
  return document.querySelector(".audit-runner__submit") as HTMLElement;
}

function getFileInput(): HTMLInputElement {
  return document.querySelector("input[type='file']") as HTMLInputElement;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AuditRunnerPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: upload resolves successfully
    mockUploadFile.mockResolvedValue({
      run_id: 10,
      status: "awaiting_mapping",
      session_id: 1,
      rows_ingested: null,
      rows_skipped: 0,
      rows_failed: 0,
      error_detail: null,
    });
  });

  it("renders the Audit Runner heading", () => {
    render(<TestWrapper />);
    expect(screen.getByText(/Audit Runner/i)).toBeDefined();
  });

  it("renders Upload & Map Fields button", () => {
    render(<TestWrapper />);
    expect(screen.getByText(/Upload & Map Fields/i)).toBeDefined();
  });

  it("shows .xlsx as enabled format badge", () => {
    render(<TestWrapper />);
    const activeBadge = document.querySelector(".audit-runner__format-badge--active");
    expect(activeBadge?.textContent).toMatch(/\.xlsx/i);
  });

  it("shows .csv and .xml as disabled (coming in Phase 4)", () => {
    render(<TestWrapper />);
    const disabled = document.querySelectorAll(".audit-runner__format-badge--disabled");
    expect(disabled.length).toBe(2);
    const texts = Array.from(disabled).map((el) => el.textContent ?? "");
    expect(texts.some((t) => t.includes(".csv"))).toBe(true);
    expect(texts.some((t) => t.includes(".xml"))).toBe(true);
  });

  it("shows error when submitting with no file selected", async () => {
    render(<TestWrapper />);
    await act(async () => { fireEvent.click(getSubmitBtn()); });
    await waitFor(() => {
      expect(screen.getByText(/Please select a file/i)).toBeDefined();
    });
  });

  it("shows error for non-XLSX file type", async () => {
    render(<TestWrapper />);
    const input = getFileInput();
    const csvFile = new File(["a,b,c"], "data.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [csvFile], configurable: true });
    await act(async () => { fireEvent.change(input); });
    await act(async () => { fireEvent.click(getSubmitBtn()); });
    await waitFor(() => {
      expect(document.querySelector(".audit-runner__error")).not.toBeNull();
    });
  });

  it("navigates to /audit-runner/{runId}/mapping on successful upload", async () => {
    render(<TestWrapper />);
    const input = getFileInput();
    const file = makeXlsxFile();
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    await act(async () => { fireEvent.change(input); });
    await act(async () => { fireEvent.click(getSubmitBtn()); });
    await waitFor(() => {
      expect(screen.queryByTestId("mapping-page")).not.toBeNull();
    });
    expect(mockUploadFile).toHaveBeenCalledOnce();
  });

  it("dropzone has correct ARIA label", () => {
    render(<TestWrapper />);
    const dropzone = document.querySelector("[role='button']");
    expect((dropzone?.getAttribute("aria-label") ?? "").length).toBeGreaterThan(0);
  });

  it("no hardcoded hex colours in rendered output", () => {
    const { container } = render(<TestWrapper />);
    container.querySelectorAll("[style]").forEach((el) => {
      expect(/#[0-9a-fA-F]{3,6}/.test(el.getAttribute("style") ?? "")).toBe(false);
    });
  });
});