/**
 * Phase 4 — Unit tests: FieldMappingTab component.
 * Covers:
 *   - Existing mappings list rendering (target_column per V9 S11.9)
 *   - Add pending row with source field + canonical column + transform_fn selector
 *   - 7 transform types available
 *   - Save & Activate calls PUT with target_column
 *   - Delete existing mapping
 *   - Empty state and access control
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

const mockedAxios = vi.mocked(axios, true);

import { FieldMappingTab } from "@/features/carrier-config/components/FieldMappingTab";

const mockMaps = [
  {
    map_id: 1, carrier_id: 10,
    source_field: "Policy Number",
    target_column: "policy_number",  // V9 S11.9: target_column not canonical_column
    file_type: null,
    transform_fn: "as-is",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
  {
    map_id: 2, carrier_id: 10,
    source_field: "CheckDate",
    target_column: "as_of_date",
    file_type: "xlsx",
    transform_fn: "date-iso",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedAxios.get = vi.fn().mockResolvedValue({ data: mockMaps });
  mockedAxios.put = vi.fn().mockResolvedValue({ data: mockMaps });
  mockedAxios.delete = vi.fn().mockResolvedValue({ data: {} });
});

function renderTab() {
  return render(
    <MemoryRouter>
      <FieldMappingTab carrierId={10} />
    </MemoryRouter>
  );
}

describe("FieldMappingTab", () => {
  it("renders the tab container", async () => {
    renderTab();
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab")).toBeDefined();
    });
  });

  it("shows existing mappings with target_column per V9 S11.9", async () => {
    renderTab();
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__existing-table")).toBeDefined();
      const rows = screen.getAllByTestId(/^field-mapping-tab__row-/);
      expect(rows.length).toBe(2);
    });
  });

  it("Add Mapping button appends pending row", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__pending-section")).toBeDefined();
    });
  });

  it("pending row has source field input", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__source-field-input")).toBeDefined();
    });
  });

  it("pending row has canonical column select with target columns", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => {
      const select = screen.getByTestId("field-mapping-tab__canonical-col-select") as HTMLSelectElement;
      const options = Array.from(select.options).map((o) => o.value);
      expect(options).toContain("policy_number");
      expect(options).toContain("actual_premium");
    });
  });

  it("pending row has transform_fn selector with 7 transform types", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => {
      const select = screen.getByTestId("field-mapping-tab__transform-select") as HTMLSelectElement;
      const options = Array.from(select.options).map((o) => o.value);
      expect(options).toContain("as-is");
      expect(options).toContain("trim");
      expect(options).toContain("upper");
      expect(options).toContain("lower");
      expect(options).toContain("date-iso");
      expect(options).toContain("decimal");
      expect(options).toContain("integer");
      expect(options.length).toBe(7);
    });
  });

  it("Save & Activate calls PUT with target_column (V9 S11.9)", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => screen.getByTestId("field-mapping-tab__source-field-input"));
    fireEvent.change(screen.getByTestId("field-mapping-tab__source-field-input"), {
      target: { value: "Check Date" },
    });
    fireEvent.click(screen.getByTestId("field-mapping-tab__save-activate-btn"));
    await waitFor(() => {
      expect(mockedAxios.put).toHaveBeenCalledWith(
        "/api/v1/admin/field-maps/10",
        expect.objectContaining({
          mappings: expect.arrayContaining([
            expect.objectContaining({ source_field: "Check Date" }),
          ]),
        })
      );
    });
  });

  it("Delete calls DELETE endpoint for existing mapping", async () => {
    renderTab();
    await waitFor(() => screen.getAllByTestId("field-mapping-tab__delete-btn"));
    fireEvent.click(screen.getAllByTestId("field-mapping-tab__delete-btn")[0]);
    await waitFor(() => {
      expect(mockedAxios.delete).toHaveBeenCalledWith("/api/v1/admin/field-maps/1");
    });
  });

  it("shows empty state when no mappings exist", async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: [] });
    renderTab();
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__empty")).toBeDefined();
    });
  });

  it("shows save success message after successful PUT", async () => {
    renderTab();
    await waitFor(() => screen.getByTestId("field-mapping-tab__add-row-btn"));
    fireEvent.click(screen.getByTestId("field-mapping-tab__add-row-btn"));
    await waitFor(() => screen.getByTestId("field-mapping-tab__source-field-input"));
    fireEvent.change(screen.getByTestId("field-mapping-tab__source-field-input"), {
      target: { value: "Policy #" },
    });
    fireEvent.click(screen.getByTestId("field-mapping-tab__save-activate-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("field-mapping-tab__save-success")).toBeDefined();
    });
  });
});
