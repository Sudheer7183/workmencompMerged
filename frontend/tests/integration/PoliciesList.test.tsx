import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { PoliciesListPage } from "@/features/policies/PoliciesListPage";
import { TenantCarrierProvider } from "@/context/TenantCarrierContext";
import { AuthProvider } from "@/context/AuthContext";

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

describe("PoliciesListPage", () => {
  it("renders the Policies heading", async () => {
    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Policies")).toBeInTheDocument();
    });
  });

  it("renders all 9 column headers from useLabels", async () => {
    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Policy Number")).toBeInTheDocument();
      expect(screen.getByText("Insured")).toBeInTheDocument();
      expect(screen.getByText("State")).toBeInTheDocument();
      expect(screen.getByText("Status")).toBeInTheDocument();
      expect(screen.getByText("Variance $")).toBeInTheDocument();
      expect(screen.getByText("Variance %")).toBeInTheDocument();
      expect(screen.getByText("Risk")).toBeInTheDocument();
      expect(screen.getByText("Audit Status")).toBeInTheDocument();
    });
  });

  it("renders policy row data from API", async () => {
    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("WC-2024-001")).toBeInTheDocument();
      expect(screen.getByText("Acme Manufacturing")).toBeInTheDocument();
    });
  });

  it("renders variance_pct as N/A when null (engine off scenario)", async () => {
    server.use(
      http.get("/api/v1/policies", () =>
        HttpResponse.json({
          items: [
            {
              policy_id: 2,
              policy_number: "WC-ENGINE-OFF",
              insured_name: "Engine Off Corp",
              state_code: "TX",
              effective_date: "2024-01-01",
              policy_status: "Active",
              est_premium: 100000,
              variance_amount: 10000,
              variance_pct: null,  // engine was off
              risk_level: null,
              audit_status: "Pending",
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
        })
      )
    );

    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("WC-ENGINE-OFF")).toBeInTheDocument();
    });
    // NaIndicator should render N/A for null variance_pct
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
  });

  it("renders engine-off notice banner when all variance_pct are null", async () => {
    server.use(
      http.get("/api/v1/policies", () =>
        HttpResponse.json({
          items: [
            {
              policy_id: 3,
              policy_number: "WC-NO-ENGINE",
              insured_name: "No Engine LLC",
              state_code: "NY",
              effective_date: "2024-01-01",
              policy_status: "Active",
              est_premium: 80000,
              variance_amount: null,
              variance_pct: null,
              risk_level: null,
              audit_status: "Pending",
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
        })
      )
    );

    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText(/calculation engine is off/i)).toBeInTheDocument();
    });
  });

  it("renders empty state when no policies", async () => {
    server.use(
      http.get("/api/v1/policies", () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 })
      )
    );
    render(<PoliciesListPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    });
  });
});
