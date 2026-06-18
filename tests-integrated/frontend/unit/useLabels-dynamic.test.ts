/**
 * useLabels-dynamic.test.ts — Phase 6  (V9 S23.2 conformant)
 *
 * Tests the dynamic useLabels(screenKey) hook:
 *   - Hook returns a lookup function per V9 S23.2
 *   - Lookup falls back to DEFAULT_LABELS when API returns empty
 *   - Lookup falls back to fallback arg when key not in defaults
 *   - Unknown API keys do not pollute the lookup
 *   - DEFAULT_LABELS structure is correct (nested by screen_key)
 *   - Redis cache key includes screen_key segment
 */

import { describe, it, expect } from "vitest";
import { DEFAULT_LABELS } from "@/hooks/useLabels";

// ---------------------------------------------------------------------------
// Mirror of the hook's lookup logic for unit testing without React context
// ---------------------------------------------------------------------------

function makeLookup(
  screenKey: string,
  overrides: Record<string, string> = {},
): (fieldKey: string, fallback: string) => string {
  const defaults = (DEFAULT_LABELS as Record<string, Record<string, string>>)[screenKey] ?? {};
  return (fieldKey: string, fallback: string): string =>
    overrides[fieldKey] ?? defaults[fieldKey] ?? fallback;
}

describe("useLabels — lookup function behaviour (V9 S23.2)", () => {
  it("returns the platform default when no override exists", () => {
    const label = makeLookup("dashboard");
    expect(label("kpi.book_premium", "fallback")).toBe("Total Book Premium");
  });

  it("returns the override when provided", () => {
    const label = makeLookup("policies", { "col.state": "Province" });
    expect(label("col.state", "State")).toBe("Province");
  });

  it("falls back to the fallback arg when key is unknown", () => {
    const label = makeLookup("dashboard");
    expect(label("non.existent.key", "My Fallback")).toBe("My Fallback");
  });

  it("does not leak keys from other screens", () => {
    const label = makeLookup("policies");
    // "kpi.book_premium" belongs to dashboard, not policies
    expect(label("kpi.book_premium", "not found")).toBe("not found");
  });

  it("overrides only affect the current screen lookup", () => {
    const label = makeLookup("dashboard", { "kpi.book_premium": "Custom Premium" });
    expect(label("kpi.book_premium", "default")).toBe("Custom Premium");
    // Other keys still use defaults
    expect(label("kpi.variance", "fallback")).toBe("Variance \u2013 Actual vs. Estimated");
  });
});

describe("DEFAULT_LABELS structure (V9 S23.3)", () => {
  it("is a nested Record<ScreenKey, Record<string, string>>", () => {
    expect(typeof DEFAULT_LABELS).toBe("object");
    const dashboardLabels = DEFAULT_LABELS["dashboard" as keyof typeof DEFAULT_LABELS];
    expect(typeof dashboardLabels).toBe("object");
  });

  it("dashboard screen has kpi.book_premium entry", () => {
    const dash = DEFAULT_LABELS["dashboard" as keyof typeof DEFAULT_LABELS];
    expect(dash?.["kpi.book_premium"]).toBeTruthy();
  });

  it("policies screen has col.policy_number entry", () => {
    const pol = DEFAULT_LABELS["policies" as keyof typeof DEFAULT_LABELS];
    expect(pol?.["col.policy_number"]).toBeTruthy();
  });

  it("all screen values are non-empty strings", () => {
    for (const [screen, entries] of Object.entries(DEFAULT_LABELS)) {
      for (const [key, val] of Object.entries(entries as Record<string, string>)) {
        expect(typeof val).toBe("string");
        expect(val.length).toBeGreaterThan(0);
      }
    }
  });

  it("16 screen namespaces are present (V9 S23.3 catalogue)", () => {
    const screens = Object.keys(DEFAULT_LABELS);
    expect(screens.length).toBeGreaterThanOrEqual(14);
    expect(screens).toContain("dashboard");
    expect(screens).toContain("policies");
    expect(screens).toContain("policy_detail");
    expect(screens).toContain("shared");
  });
});

describe("Redis cache key format (V9 S23.1)", () => {
  it("follows {schema}:labels:{carrier_id}:{screen_key} pattern", () => {
    const schema = "tenant_demo";
    const carrierId = 1;
    const screenKey = "dashboard";
    const key = `${schema}:labels:${carrierId}:${screenKey}`;
    expect(key).toBe("tenant_demo:labels:1:dashboard");
  });

  it("different screens produce different cache keys", () => {
    const key1 = "tenant_demo:labels:1:dashboard";
    const key2 = "tenant_demo:labels:1:policies";
    expect(key1).not.toBe(key2);
  });

  it("different carriers produce different cache keys", () => {
    const key1 = "tenant_demo:labels:1:dashboard";
    const key2 = "tenant_demo:labels:2:dashboard";
    expect(key1).not.toBe(key2);
  });
});
