import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { NaIndicator } from "@/components/ui/NaIndicator";

// ---------------------------------------------------------------------------
// Mock useLabels so tests don't need full context tree
// ---------------------------------------------------------------------------
vi.mock("@/hooks/useLabels", () => ({
  // FIX: useLabels returns a function (key, fallback) => fallback, not an object.
  // NaIndicator calls label("na_label", "N/A") — the mock must be callable.
  useLabels: () => (_key: string, fallback: string) => fallback,
}));

describe("NaIndicator", () => {
  it("shows N/A when engine is off, even with a non-null value", () => {
    render(<NaIndicator engineOn={false} value={0.15} format="pct" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows N/A when engine is on but value is null", () => {
    render(<NaIndicator engineOn={true} value={null} format="pct" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows N/A when engine is on but value is undefined", () => {
    render(<NaIndicator engineOn={true} value={undefined} format="pct" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("renders formatted value when engine is on and value is non-null", () => {
    render(<NaIndicator engineOn={true} value={0.15} format="pct" />);
    // 0.15 as percent = 15.0%
    expect(screen.getByText("15.0%")).toBeInTheDocument();
    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
  });

  it("renders currency format correctly", () => {
    render(<NaIndicator engineOn={true} value={15000} format="currency" />);
    expect(screen.getByText(/\$15,000\.00/)).toBeInTheDocument();
  });

  it("renders number format correctly", () => {
    render(<NaIndicator engineOn={true} value={1234} format="number" />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });

  it("renders raw format as-is", () => {
    render(<NaIndicator engineOn={true} value="hello" format="raw" />);
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("uses custom naLabel when provided", () => {
    render(<NaIndicator engineOn={false} value={100} naLabel="Engine Off" />);
    expect(screen.getByText("Engine Off")).toBeInTheDocument();
  });

  it("applies na-value CSS class on N/A", () => {
    const { container } = render(<NaIndicator engineOn={false} value={100} />);
    const el = container.querySelector(".na-value");
    expect(el).not.toBeNull();
  });

  it("zero is a valid value and should not show N/A", () => {
    render(<NaIndicator engineOn={true} value={0} format="number" />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
  });
});