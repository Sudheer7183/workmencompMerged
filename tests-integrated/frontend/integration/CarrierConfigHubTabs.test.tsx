/**
 * Phase 4 — Frontend integration test: CarrierConfigHub Tabs 1 and 2.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";

vi.mock("axios");
vi.mock("@/hooks/useLabels", () => ({ useLabels: () => ({}) }));
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { role: "TENANT_ADMIN" } }),
}));
vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: () => ({ carrierId: 1 }),
}));
vi.mock("@/features/carrier-config/hooks/useCarrierCalcConfig", () => ({
  useCarrierCalcConfig: () => ({ data: { use_calculation_engine: true }, loading: false }),
}));

const mockedAxios = vi.mocked(axios, true);

import { CarrierConfigHub } from "@/features/carrier-config/components/CarrierConfigHub";

beforeEach(() => {
  vi.clearAllMocks();
  mockedAxios.get = vi.fn().mockResolvedValue({ data: [] });
  mockedAxios.post = vi.fn().mockResolvedValue({ data: {} });
  mockedAxios.put = vi.fn().mockResolvedValue({ data: [] });
  mockedAxios.delete = vi.fn().mockResolvedValue({ data: {} });
});

function renderHub() {
  return render(
    <MemoryRouter>
      <CarrierConfigHub carrierId={1} carrierName="Test Carrier" />
    </MemoryRouter>
  );
}

describe("CarrierConfigHub Phase 4 Tabs", () => {
  it("renders all 6 tabs", () => {
    renderHub();
    const tabs = screen.getAllByRole("button").filter(
      (b) => b.className.includes("carrier-config-hub__tab")
    );
    expect(tabs.length).toBe(6);
  });

  it("clicking Tab 1 renders DataSourcesTab", async () => {
    renderHub();
    const tab1 = screen.getByTestId("carrier-config-hub__tab-1");
    fireEvent.click(tab1);
    await waitFor(() => {
      expect(screen.getByTestId("data-sources-tab")).toBeDefined();
    });
  });

  it("clicking Tab 2 renders FieldMappingTab", async () => {
    renderHub();
    const tab2 = screen.getByTestId("carrier-config-hub__tab-2");
    fireEvent.click(tab2);
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab")).toBeDefined();
    });
  });

  it("Tab 3 (Calc Engine) is active by default", () => {
    renderHub();
    const tab3 = screen.getByTestId("carrier-config-hub__tab-3");
    expect(tab3.className).toContain("--active");
  });

  it("Tab 4 shows coming-soon placeholder", async () => {
    renderHub();
    fireEvent.click(screen.getByTestId("carrier-config-hub__tab-4"));
    await waitFor(() => {
      expect(screen.getByTestId("carrier-config-hub__coming-soon")).toBeDefined();
    });
  });

  it("Tab 1 Add Source button is visible for TENANT_ADMIN", async () => {
    renderHub();
    fireEvent.click(screen.getByTestId("carrier-config-hub__tab-1"));
    await waitFor(() => {
      expect(screen.getByTestId("data-sources-tab__add-btn")).toBeDefined();
    });
  });

  it("Tab 2 Add Mapping button is visible for TENANT_ADMIN", async () => {
    renderHub();
    fireEvent.click(screen.getByTestId("carrier-config-hub__tab-2"));
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__add-row-btn")).toBeDefined();
    });
  });
});
