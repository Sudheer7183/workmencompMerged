import { describe, it, expect } from "vitest";
import { DEFAULT_LABELS, useLabels } from "@/hooks/useLabels";

describe("useLabels", () => {
  it("returns DEFAULT_LABELS in Phase 1", () => {
    const labels = useLabels();
    expect(labels).toBe(DEFAULT_LABELS);
  });

  it("has na_label defined", () => {
    expect(DEFAULT_LABELS.na_label).toBe("N/A");
  });

  it("has all required dashboard keys", () => {
    expect(DEFAULT_LABELS.kpi_total_book_premium).toBeTruthy();
    expect(DEFAULT_LABELS.kpi_total_est_earned).toBeTruthy();
    expect(DEFAULT_LABELS.kpi_total_actual_earned).toBeTruthy();
    expect(DEFAULT_LABELS.kpi_total_variance).toBeTruthy();
  });

  it("has all required policy list columns", () => {
    expect(DEFAULT_LABELS.col_policy_number).toBeTruthy();
    expect(DEFAULT_LABELS.col_insured_name).toBeTruthy();
    expect(DEFAULT_LABELS.col_variance_pct).toBeTruthy();
    expect(DEFAULT_LABELS.col_risk_level).toBeTruthy();
    expect(DEFAULT_LABELS.col_audit_status).toBeTruthy();
  });

  it("has engine_off_notice", () => {
    expect(DEFAULT_LABELS.engine_off_notice).toBeTruthy();
    expect(DEFAULT_LABELS.engine_off_notice.length).toBeGreaterThan(10);
  });
});
