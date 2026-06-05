/**
 * TenantLogo — 6 test cases (Phase 2, V9 S14.2)
 *
 * TenantLogo calls useAuth() internally to check for SUPER_ADMIN.
 * All renders must be wrapped with AuthProvider (or a mock that satisfies
 * the AuthContext) in addition to QueryClientProvider.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Mock AuthContext so useAuth() returns a non-null AUDITOR user.
// TenantLogo only reads user.role — a minimal mock is sufficient.
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

// Mock axios for branding fetch
vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: { ...actual.default, get: vi.fn() },
  };
});

import axios from "axios";
import { TenantLogo } from "@/components/TenantLogo";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(React.createElement(QueryClientProvider, { client: qc }, ui));
}

describe("TenantLogo", () => {
  it("renders img element when logo_url is set", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { logo_url: "https://cdn.example.com/logo.png", logo_dark_url: null, brand_color: null },
    });
    wrap(<TenantLogo />);
    const img = await screen.findByRole("img", { name: /organisation logo/i });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://cdn.example.com/logo.png");
  });

  it("renders text fallback 'the Audit Platform' when logo_url is null", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { logo_url: null, logo_dark_url: null, brand_color: null },
    });
    wrap(<TenantLogo />);
    expect(await screen.findByText("the Audit Platform")).toBeInTheDocument();
  });

  it("uses logo_dark_url for dark variant when set", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: {
        logo_url: "https://cdn.example.com/logo-light.png",
        logo_dark_url: "https://cdn.example.com/logo-dark.png",
        brand_color: null,
      },
    });
    wrap(<TenantLogo variant="dark" />);
    const img = await screen.findByRole("img");
    expect(img).toHaveAttribute("src", "https://cdn.example.com/logo-dark.png");
  });

  it("falls back to logo_url for dark variant when logo_dark_url is null", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: {
        logo_url: "https://cdn.example.com/logo.png",
        logo_dark_url: null,
        brand_color: null,
      },
    });
    wrap(<TenantLogo variant="dark" />);
    const img = await screen.findByRole("img");
    expect(img).toHaveAttribute("src", "https://cdn.example.com/logo.png");
  });

  it("applies BEM class tenant-logo__text to text fallback", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { logo_url: null, logo_dark_url: null, brand_color: null },
    });
    wrap(<TenantLogo />);
    const textEl = await screen.findByText("the Audit Platform");
    expect(textEl).toHaveClass("tenant-logo__text");
  });

  it("applies BEM class tenant-logo__img to image element", async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: { logo_url: "https://cdn.example.com/logo.png", logo_dark_url: null, brand_color: null },
    });
    wrap(<TenantLogo />);
    const img = await screen.findByRole("img");
    expect(img).toHaveClass("tenant-logo__img");
  });
});
