import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { VarianceCard } from "@/components/ui/Badges";

describe("VarianceCard", () => {
  it("renders positive variance_amount with pos-val class", () => {
    const { container } = render(
      <VarianceCard label="Premium Variance" amount={15000} pct={0.15} engineOn={true} />
    );
    const valueEl = container.querySelector(".pos-val, .variance-positive");
    expect(valueEl).not.toBeNull();
  });

  it("renders negative variance_amount with neg-val class", () => {
    const { container } = render(
      <VarianceCard label="Premium Variance" amount={-8000} pct={-0.08} engineOn={true} />
    );
    const valueEl = container.querySelector(".neg-val, .variance-negative");
    expect(valueEl).not.toBeNull();
  });

  it("renders null amount gracefully without throwing", () => {
    expect(() =>
      render(<VarianceCard label="Test" amount={null} pct={null} engineOn={false} />)
    ).not.toThrow();
  });

  it("formats currency values with $ and commas", () => {
    render(<VarianceCard label="Test" amount={15000} pct={null} engineOn={false} />);
    expect(screen.getByText(/\$15,000/)).toBeInTheDocument();
  });

  it("shows N/A for pct when engine is off", () => {
    render(
      <VarianceCard label="Test" amount={10000} pct={0.10} engineOn={false} />
    );
    // The pct portion should show N/A when engineOn=false
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows formatted pct when engine is on and value is non-null", () => {
    render(
      <VarianceCard label="Test" amount={10000} pct={0.10} engineOn={true} />
    );
    expect(screen.getByText("10.0%")).toBeInTheDocument();
  });

  it("renders the label text", () => {
    render(<VarianceCard label="Premium Variance" amount={0} pct={null} engineOn={false} />);
    expect(screen.getByText("Premium Variance")).toBeInTheDocument();
  });
});
