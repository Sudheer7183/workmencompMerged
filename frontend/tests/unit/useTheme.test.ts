/**
 * useTheme — Phase 1 tests (preserved, updated for Phase 2 requirements).
 *
 * useTheme calls useAuth() internally (Phase 2 SUPER_ADMIN guard), so
 * renderHook must be wrapped with both QueryClientProvider AND an AuthContext
 * mock that returns a non-null user. Without the AuthContext mock,
 * useAuth() throws "useAuth must be used within AuthProvider".
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DEFAULT_DARK_TOKENS, useTheme } from "@/hooks/useTheme";

// ---------------------------------------------------------------------------
// Mock AuthContext — useTheme reads user.role to decide whether to fetch.
// Return a standard AUDITOR so the branding fetch IS attempted (enabled=true).
// ---------------------------------------------------------------------------
vi.mock("@/context/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/AuthContext")>();
  return {
    ...actual,
    useAuth: vi.fn().mockReturnValue({
      user: { role: "AUDITOR", tenant_slug: "demo", email: "test@demo.com",
               sub: "test-sub", onboarding_completed: true },
      isAuthenticated: true,
      token: "mock-token",
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    }),
  };
});

// Silence the branding fetch in these baseline tests
vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: {
      ...actual.default,
      get: vi.fn().mockResolvedValue({
        data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
          border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
          brand: "4ade80", brand_dark: "15803d", accent: "818cf8",
          color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
          color_blue: "60a5fa" },
      }),
    },
  };
});

vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: vi.fn(() => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [],
    isLoadingCarriers: false,
  })),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useTheme", () => {
  beforeEach(() => {
    const root = document.documentElement;
    Object.keys(DEFAULT_DARK_TOKENS).forEach((prop) => {
      root.style.removeProperty(prop);
    });
    vi.clearAllMocks();
  });

  it("applies all 13 Default Dark tokens to :root", async () => {
    renderHook(() => useTheme(), { wrapper: createWrapper() });
    await waitFor(() => {
      Object.entries(DEFAULT_DARK_TOKENS).forEach(([prop]) => {
        expect(document.documentElement.style.getPropertyValue(prop)).not.toBe("");
      });
    });
  });

  it("has exactly 13 token keys", () => {
    expect(Object.keys(DEFAULT_DARK_TOKENS)).toHaveLength(13);
  });

  it("has correct --bg token", () => {
    expect(DEFAULT_DARK_TOKENS["--bg"]).toBe("#0f1117");
  });

  it("has correct --brand token (green accent)", () => {
    expect(DEFAULT_DARK_TOKENS["--brand"]).toBe("#4ade80");
  });
});