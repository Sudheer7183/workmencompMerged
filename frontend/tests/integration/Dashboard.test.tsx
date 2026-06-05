import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { TenantCarrierProvider } from "@/context/TenantCarrierContext";
import { AuthProvider } from "@/context/AuthContext";

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
        <AuthProvider>
          <TenantCarrierProvider>
            {children}
          </TenantCarrierProvider>
        </AuthProvider>
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
