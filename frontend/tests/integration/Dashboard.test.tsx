import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { DashboardPage } from "@/features/dashboard/DashboardPage";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(() => ({
    user: {
      sub: "test-sub-001",
      email: "tenant-admin@test.example.com",
      role: "TENANT_ADMIN",
      tenant_slug: "demo",
      onboarding_completed: true,
    },
    isAuthenticated: true,
    token: "mock-token",
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
    completeOnboarding: vi.fn(),
  })),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: vi.fn(() => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [{ carrier_id: 1, carrier_name: "Demo Carrier", carrier_code: "DEMO" }],
    isLoadingCarriers: false,
  })),
  TenantCarrierProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ---------------------------------------------------------------------------
// Wrapper with all required providers
// ---------------------------------------------------------------------------

function TestWrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return (
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        {children}
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardPage", () => {
  it("renders the page title", async () => {
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Audit Dashboard")).toBeInTheDocument();
    });
  });

  it("renders all 4 KPI card labels", async () => {
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Total Book Premium")).toBeInTheDocument();
      expect(screen.getByText("Est. Earned Premium")).toBeInTheDocument();
      expect(screen.getByText("Actual Earned Premium")).toBeInTheDocument();
      expect(screen.getByText("Total Variance")).toBeInTheDocument();
    });
  });

  it("renders Policy Status chart section", async () => {
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Policy Status")).toBeInTheDocument();
    });
  });

  it("renders Risk Distribution chart section", async () => {
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Risk Distribution")).toBeInTheDocument();
    });
  });

  it("renders target variance widget", async () => {
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(
        screen.getByText(/30% variance threshold/i)
      ).toBeInTheDocument();
    });
  });

  it("shows error banner when API fails", async () => {
    server.use(
      http.get("/api/v1/dashboard/summary", () =>
        HttpResponse.json({ detail: "Server Error" }, { status: 500 })
      )
    );
    render(<DashboardPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(
        screen.getByText(/something went wrong/i)
      ).toBeInTheDocument();
    });
  });
});