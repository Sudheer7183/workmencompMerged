import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { RiskBadge, StatusBadge, AuditStatusBadge } from "@/components/ui/Badges";

describe("RiskBadge", () => {
  it("renders High with red class", () => {
    const { container } = render(<RiskBadge risk="High" />);
    const badge = container.querySelector(".badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("High");
    expect(badge!.className).toContain("badge-red");
  });

  it("renders Medium with amber class", () => {
    const { container } = render(<RiskBadge risk="Medium" />);
    expect(container.querySelector(".badge-amber")).not.toBeNull();
  });

  it("renders Low with green class", () => {
    const { container } = render(<RiskBadge risk="Low" />);
    expect(container.querySelector(".badge-green")).not.toBeNull();
  });

  it("renders dash for null risk", () => {
    render(<RiskBadge risk={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders Active with green class", () => {
    const { container } = render(<StatusBadge status="Active" />);
    expect(container.querySelector(".badge-green")).not.toBeNull();
  });

  it("renders Cancelled with red class", () => {
    const { container } = render(<StatusBadge status="Cancelled" />);
    expect(container.querySelector(".badge-red")).not.toBeNull();
  });
});

describe("AuditStatusBadge", () => {
  it("renders Pending with muted class", () => {
    const { container } = render(<AuditStatusBadge status="Pending" />);
    expect(container.querySelector(".badge-muted")).not.toBeNull();
  });

  it("renders In-Review with amber class", () => {
    const { container } = render(<AuditStatusBadge status="In-Review" />);
    expect(container.querySelector(".badge-amber")).not.toBeNull();
  });

  it("renders Complete with green class", () => {
    const { container } = render(<AuditStatusBadge status="Complete" />);
    expect(container.querySelector(".badge-green")).not.toBeNull();
  });
});
