import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { KpiCard } from "@/components/ui/KpiCard";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Total Book Premium" value="$5.0M" />);
    expect(screen.getByText("Total Book Premium")).toBeInTheDocument();
    expect(screen.getByText("$5.0M")).toBeInTheDocument();
  });

  it("shows subtext when provided", () => {
    render(<KpiCard label="Variance" value="$150K" subtext="+3.1%" />);
    expect(screen.getByText("+3.1%")).toBeInTheDocument();
  });

  it("renders skeleton when loading", () => {
  const { container } = render(<KpiCard label="KPI" value="" loading />);
  expect(container.querySelector(".skeleton")).not.toBeNull();
  // ✅ Don't query empty string — just confirm the value span is absent
  expect(container.querySelector(".font-mono")).toBeNull();
});

  it("applies accent color via inline style", () => {
    const { container } = render(
      <KpiCard label="Test" value="$0" accentColor="var(--brand)" />
    );
    const card = container.querySelector(".card") as HTMLElement;
    expect(card.style.borderTop).toContain("var(--brand)");
  });
});
