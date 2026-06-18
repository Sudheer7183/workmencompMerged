import { describe, it, expect } from "vitest";
import { fmtSignedPct, fmtDate, fmtCurrency, varianceClass } from "@/utils/format";

describe("fmtSignedPct", () => {
  it('returns "+12.3%" for positive number', () => {
    expect(fmtSignedPct(0.123)).toBe("+12.3%");
  });

  it('returns "-12.3%" for negative number', () => {
    expect(fmtSignedPct(-0.123)).toBe("-12.3%");
  });

  it('returns "0.0%" for zero', () => {
    expect(fmtSignedPct(0)).toBe("0.0%");
  });

  it('returns "N/A" for null', () => {
    expect(fmtSignedPct(null)).toBe("N/A");
  });

  it('returns "N/A" for undefined', () => {
    expect(fmtSignedPct(undefined)).toBe("N/A");
  });

  it("handles large percentages correctly", () => {
    const result = fmtSignedPct(1.5); // 150%
    expect(result).toContain("+");
    expect(result).toContain("150");
  });
});

describe("fmtDate", () => {
  it("formats ISO date string to human-readable", () => {
    const result = fmtDate("2024-01-01");
    expect(result).toContain("2024");
  });

  it("returns em dash for null", () => {
    expect(fmtDate(null)).toBe("—");
  });

  it("returns em dash for undefined", () => {
    expect(fmtDate(undefined)).toBe("—");
  });
});

describe("fmtCurrency", () => {
  it("includes dollar sign", () => {
    expect(fmtCurrency(15000)).toContain("$");
  });

  it("formats with commas", () => {
    expect(fmtCurrency(15000)).toContain(",");
  });
});

describe("varianceClass", () => {
  it('returns "pos-val" for positive amount', () => {
    expect(varianceClass(5000)).toBe("pos-val");
  });

  it('returns "neg-val" for negative amount', () => {
    expect(varianceClass(-5000)).toBe("neg-val");
  });

  it('returns "variance-neutral" for zero', () => {
    expect(varianceClass(0)).toBe("variance-neutral");
  });

  it('returns empty string for null', () => {
    expect(varianceClass(null)).toBe("");
  });
});
