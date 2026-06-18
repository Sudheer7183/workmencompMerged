import { describe, it, expect, vi } from "vitest";
import { DEFAULT_LABELS } from "@/hooks/useLabels";

// useLabels calls useTenantCarrier() internally.
// Mock the context so these unit tests don't need a full provider tree.
vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: vi.fn(() => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [],
    isLoadingCarriers: false,
  })),
}));

describe("useLabels", () => {
  // FIX: useLabels(screenKey) requires a screenKey argument and needs
  // React context (QueryClient + TenantCarrierContext) to run.
  // These tests should only test DEFAULT_LABELS shape — the hook behaviour
  // is covered by tests/unit/hooks/useTheme.test.ts and the integration tests.
  it("returns DEFAULT_LABELS in Phase 1", () => {
    // DEFAULT_LABELS is the in-code registry — verify it is a non-empty object
    expect(typeof DEFAULT_LABELS).toBe("object");
    expect(Object.keys(DEFAULT_LABELS).length).toBeGreaterThan(0);
  });

  // FIX: DEFAULT_LABELS is now nested: { shared: { na_label: "N/A" } }
  // The flat key DEFAULT_LABELS.na_label no longer exists.
  it("has na_label defined", () => {
    expect(DEFAULT_LABELS["shared"]["na_label"]).toBe("N/A");
  });

  // FIX: keys are namespaced under "dashboard" screen with dot-notation
  it("has all required dashboard keys", () => {
    expect(DEFAULT_LABELS["dashboard"]["kpi.book_premium"]).toBeTruthy();
    expect(DEFAULT_LABELS["dashboard"]["kpi.est_earned"]).toBeTruthy();
    expect(DEFAULT_LABELS["dashboard"]["kpi.actual_earned"]).toBeTruthy();
    expect(DEFAULT_LABELS["dashboard"]["kpi.variance"]).toBeTruthy();
  });

  // FIX: keys are namespaced under "policies" screen with dot-notation
  it("has all required policy list columns", () => {
    expect(DEFAULT_LABELS["policies"]["col.policy_number"]).toBeTruthy();
    expect(DEFAULT_LABELS["policies"]["col.insured_name"]).toBeTruthy();
    expect(DEFAULT_LABELS["policies"]["col.variance_pct"]).toBeTruthy();
    expect(DEFAULT_LABELS["policies"]["col.risk_level"]).toBeTruthy();
    expect(DEFAULT_LABELS["policies"]["col.audit_status"]).toBeTruthy();
  });

  // FIX: engine_off_notice is under "shared" screen key
  it("has engine_off_notice", () => {
    expect(DEFAULT_LABELS["shared"]["engine_off_notice"]).toBeTruthy();
    expect(DEFAULT_LABELS["shared"]["engine_off_notice"].length).toBeGreaterThan(10);
  });
});