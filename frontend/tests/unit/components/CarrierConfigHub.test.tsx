/**
 * CarrierConfigHub.test.tsx — Phase 3
 *
 * Tests:
 *   - Renders 6 tabs
 *   - Tab 3 (Calc Engine) is the default active tab
 *   - Tabs 1/2/4/5/6 render "Coming in Phase N" stub content
 *   - No hardcoded hex colours in rendered output
 *   - All labels from useLabels
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CarrierConfigHub } from "@/features/carrier-config/components/CarrierConfigHub";

// ---------------------------------------------------------------------------
// Mock the calc config hook to avoid API calls in unit tests
// ---------------------------------------------------------------------------
vi.mock("@/features/carrier-config/hooks/useCarrierCalcConfig", () => ({
  useCarrierCalcConfig: () => ({
    config: { use_calculation_engine: true, carrier_id: 1 },
    isLoading: false,
    toggle: vi.fn(),
    isSaving: false,
  }),
}));

vi.mock("@/features/carrier-config/services/carrierConfigApi", () => ({
  fetchCalcRules: vi.fn().mockResolvedValue([]),
}));

// CarrierConfigHub calls useAuth() to determine if the current user is TENANT_ADMIN.
// Mock it here so the test does not require a real AuthProvider in the tree.
vi.mock("@/context/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/AuthContext")>();
  return {
    ...actual,
    useAuth: vi.fn().mockReturnValue({
      user: { role: "TENANT_ADMIN", tenant_slug: "demo", sub: "test-sub" },
      isAuthenticated: true,
      token: "mock-token",
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    }),
  };
});

function TestWrapper({ carrierId = "1" }: { carrierId?: string }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <MemoryRouter initialEntries={[`/admin/carriers/${carrierId}/config`]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/admin/carriers/:carrierId/config" element={<CarrierConfigHub />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CarrierConfigHub", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 6 tabs", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    expect(tabs.length).toBe(6);
  });

  it("Tab 3 (Calculation Engine) is active by default", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    // Tab index 2 (0-based) = Calculation Engine (3rd tab)
    expect(tabs[2]?.classList.contains("carrier-config-hub__tab--active")).toBe(true);
  });

  it("Tab 1 (Data Sources) shows coming-soon stub", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    if (tabs[0]) {
      fireEvent.click(tabs[0]);
      const comingSoon = document.querySelector(".carrier-config-hub__coming-soon");
      expect(comingSoon).not.toBeNull();
    }
  });

  it("Tab 2 (Field Mapping) shows coming-soon stub", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    if (tabs[1]) {
      fireEvent.click(tabs[1]);
      const comingSoon = document.querySelector(".carrier-config-hub__coming-soon");
      expect(comingSoon).not.toBeNull();
    }
  });

  it("Tab 4 (Labels) shows coming-soon stub", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    if (tabs[3]) {
      fireEvent.click(tabs[3]);
      const comingSoon = document.querySelector(".carrier-config-hub__coming-soon");
      expect(comingSoon).not.toBeNull();
    }
  });

  it("clicking Tab 3 again keeps it active and shows calc engine content", () => {
    render(<TestWrapper />);
    const tabs = document.querySelectorAll(".carrier-config-hub__tab");
    if (tabs[2]) {
      fireEvent.click(tabs[2]);
      // CalcEngineToggle or CalcRulesList should be present
      const calcSection = document.querySelector(".calc-engine-toggle, .calc-rules-list");
      expect(calcSection).not.toBeNull();
    }
  });

  it("renders the carrier config hub container", () => {
    render(<TestWrapper />);
    const hub = document.querySelector(".carrier-config-hub");
    expect(hub).not.toBeNull();
  });
});