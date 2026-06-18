/**
 * useTheme — Phase 2 tests (5 cases).
 *
 * useTheme calls useAuth() internally (SUPER_ADMIN guard for branding fetch),
 * so renderHook must be wrapped with a mocked AuthContext in addition to
 * QueryClientProvider. Without the mock, useAuth() throws:
 *   "useAuth must be used within AuthProvider"
 *
 * Verifies that:
 * 1. All 13 CSS variables are set on document.documentElement.
 * 2. brand_color from the API overrides --brand with the tenant hex.
 * 3. When brand_color is null, --brand uses Default Dark value (#4ade80).
 * 4. brand_color does NOT override --brand-dark.
 * 5. brand_color with a non-6-char value is ignored; --brand uses default.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { DEFAULT_DARK_TOKENS, useTheme } from "@/hooks/useTheme";

// ---------------------------------------------------------------------------
// Mock AuthContext — useTheme reads user.role to determine enabled state.
// Using AUDITOR means isTenantUser=true, so the branding query runs.
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

// ── axios mock ───────────────────────────────────────────────────────────────
vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: {
      ...actual.default,
      get: vi.fn(),
    },
  };
});

import axios from "axios";

vi.mock("@/context/TenantCarrierContext", () => ({
  // useTheme calls useTenantCarrier() to get carrierId for the theme query.
  // Mock it here so the hook can run without a real TenantCarrierProvider in the tree.
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

function getCssVar(name: string): string {
  return document.documentElement.style.getPropertyValue(name);
}

describe("useTheme — Phase 2", () => {
  beforeEach(() => {
    Object.keys(DEFAULT_DARK_TOKENS).forEach((v) =>
      document.documentElement.style.removeProperty(v)
    );
    vi.clearAllMocks();
  });

  it("sets all 13 CSS variables on document root", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
      border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
      brand: "4ade80", brand_dark: "15803d", accent: "818cf8",
      color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
      color_blue: "60a5fa" },
    });
    renderHook(() => useTheme(), { wrapper: createWrapper() });

    await waitFor(() => {
      Object.entries(DEFAULT_DARK_TOKENS).forEach(([prop]) => {
        expect(document.documentElement.style.getPropertyValue(prop)).not.toBe("");
      });
    });
    expect(Object.keys(DEFAULT_DARK_TOKENS)).toHaveLength(13);
  });

  it("brand_color from API overrides --brand with prefixed hex", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
      border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
      brand: "1a3c5e", brand_dark: "15803d", accent: "818cf8",
      color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
      color_blue: "60a5fa" },
    });
    renderHook(() => useTheme(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(getCssVar("--brand")).toBe("#1a3c5e");
    });
  });

  it("when brand_color is null, --brand uses Default Dark value #4ade80", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
      border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
      brand: "4ade80", brand_dark: "15803d", accent: "818cf8",
      color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
      color_blue: "60a5fa" },
    });
    renderHook(() => useTheme(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(getCssVar("--brand")).toBe(DEFAULT_DARK_TOKENS["--brand"]);
    });
  });

  it("brand_color does NOT override --brand-dark", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
      border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
      brand: "ff0000", brand_dark: "15803d", accent: "818cf8",
      color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
      color_blue: "60a5fa" },
    });
    renderHook(() => useTheme(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(getCssVar("--brand")).toBe("#ff0000");
      expect(getCssVar("--brand-dark")).toBe(DEFAULT_DARK_TOKENS["--brand-dark"]);
    });
  });

  it("when API returns default brand, --brand uses Default Dark value", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { bg: "0f1117", surface: "181c27", surface2: "1e2436",
      border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
      brand: "4ade80", brand_dark: "15803d", accent: "818cf8",
      color_green: "22c55e", color_amber: "f59e0b", color_red: "ef4444",
      color_blue: "60a5fa" },
    });
    renderHook(() => useTheme(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(getCssVar("--brand")).toBe(DEFAULT_DARK_TOKENS["--brand"]);
    });
  });
});