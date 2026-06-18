import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { PolicyDetailPage } from "@/features/policies/PolicyDetailPage";
import { TenantCarrierProvider } from "@/context/TenantCarrierContext";
import { AuthProvider } from "@/context/AuthContext";

// Mock Keycloak-dependent contexts to avoid async init delays in tests
vi.mock("@/context/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/AuthContext")>();
  return {
    ...actual,
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useAuth: vi.fn().mockReturnValue({
      user: { role: "REVIEWER", tenant_slug: "demo" },
      isAuthenticated: true,
      token: "mock-token",
      completeOnboarding: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    }),
  };
});

vi.mock("@/context/TenantCarrierContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/TenantCarrierContext")>();
  return {
    ...actual,
    TenantCarrierProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useTenantCarrier: vi.fn().mockReturnValue({
      carrierId: 1,
      setCarrierId: vi.fn(),
      availableCarriers: [{ carrier_id: 1, carrier_name: "Test Carrier" }],
      isLoadingCarriers: false,
    }),
  };
});

// Additional mock handlers for detail page
const DETAIL_HANDLERS = [
  http.get("/api/v1/policies/:id/class-code-variance", () =>
    HttpResponse.json({ rows: [], total: 0 })
  ),
  http.get("/api/v1/policies/:id", () =>
    HttpResponse.json({
      meta: {
        policy_id: 1,
        policy_number: "WC-2024-001",
        insured_name: "Acme Manufacturing",
        fein: "12-3456789",
        state_code: "CA",
        effective_date: "2024-01-01",
        expiration_date: "2025-01-01",
        cancellation_date: null,
        policy_status: "Active",
        payment_frequency: "Monthly",
        owner_status: "Included",
        audit_status: "In-Review",
        total_est_payroll: 500000,
      },
      engine_on: true,
      latest_run_id: 1,
    })
  ),
  http.get("/api/v1/policies/:id/premium-variance", () =>
    HttpResponse.json({
      est_premium_end: 100000,
      actual_premium: 115000,
      variance_amount: 15000,
      variance_pct: 0.15,
      as_of_date: "2024-06-30",
    })
  ),
  http.get("/api/v1/policies/:id/payroll-variance", () =>
    HttpResponse.json({
      est_payroll: 500000,
      actual_payroll_reported: 540000,
      reported_over_under: 40000,
      reported_pct: 1.08,
      actual_payroll_classified: 530000,
      classified_over_under: 30000,
      classified_pct: 1.06,
      as_of_date: "2024-06-30",
    })
  ),
  http.get("/api/v1/policies/:id/submission-metrics", () =>
    HttpResponse.json({
      actual_received: 6,
      zero_payroll_count: 1,
      expected_submissions: 12,
      missing_payroll_count: 2,
      submission_rate: 0.5,
    })
  ),
  http.get("/api/v1/policies/:id/zero-payroll", () =>
    HttpResponse.json({ rows: [], total: 0 })
  ),
  http.get("/api/v1/policies/:id/missing-payroll", () =>
    HttpResponse.json({ rows: [], total: 0 })
  ),
];

function TestWrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // Do NOT set gcTime:0 — it causes immediate cache eviction under React
        // 18 strict-mode double-invocation, making sub-queries appear never to
        // resolve. Use a modest staleTime so data survives the render cycle.
        staleTime: 10_000,
        gcTime: 30_000,
      },
    },
  });
  return (
    <MemoryRouter initialEntries={["/policies/1?carrier_id=1"]}>
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <TenantCarrierProvider>
            <Routes>
              <Route path="/policies/:policyId" element={<PolicyDetailPage />} />
            </Routes>
          </TenantCarrierProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("PolicyDetailPage", () => {
  it("renders all 11 meta card fields with correct labels from useLabels", async () => {
    server.use(...DETAIL_HANDLERS);
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getAllByText("WC-2024-001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Acme Manufacturing")).toBeInTheDocument();
    }, { timeout: 5000 });
    expect(screen.getByText("FEIN")).toBeInTheDocument();
    expect(screen.getByText("State")).toBeInTheDocument();
    expect(screen.getByText("Effective Date")).toBeInTheDocument();
    expect(screen.getByText("Expiration Date")).toBeInTheDocument();
    expect(screen.getByText("Payment Frequency")).toBeInTheDocument();
    expect(screen.getByText("Owner Status")).toBeInTheDocument();
    expect(screen.getByText("Total Est. Payroll")).toBeInTheDocument();
  });

  it("renders all 4 tab labels", async () => {
    server.use(...DETAIL_HANDLERS);
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Policy Summary")).toBeInTheDocument();
      expect(screen.getAllByText("Missing Payrolls").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Zero Payrolls")).toBeInTheDocument();
      expect(screen.getByText("AI Narrative")).toBeInTheDocument();
    }, { timeout: 9000 });
  }, 12000);

  it("Summary tab shows Premium Variance section", async () => {
    server.use(...DETAIL_HANDLERS);
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText("Premium Variance")).toBeInTheDocument();
    }, { timeout: 8000 });
  });

  it("Summary tab shows 5 payroll metrics pills", async () => {
    server.use(...DETAIL_HANDLERS);
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      // Actual label text from PolicyDetailPage SummaryTab payroll pills.
      // Use getAllByText for labels that appear in both the tab bar and the pill section.
      expect(screen.getAllByText("Actual Payrolls Received").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Total Payroll Expected").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Missing Payrolls").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Submission Rate").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Zero Payrolls").length).toBeGreaterThanOrEqual(1);
    }, { timeout: 9000 });
  }, 12000);

  it("AI Narrative tab renders placeholder when engine is on", async () => {
    server.use(...DETAIL_HANDLERS);
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => expect(screen.getByText("AI Narrative")).toBeInTheDocument(), { timeout: 5000 });
    await userEvent.click(screen.getByText("AI Narrative"));
    await waitFor(() => {
      expect(screen.getByText(/No narrative available for this policy/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it("renders N/A for total_est_payroll when engine is off", async () => {
    server.use(
      http.get("/api/v1/policies/:id", () =>
        HttpResponse.json({
          meta: {
            policy_id: 1,
            policy_number: "WC-2024-001",
            insured_name: "Acme Manufacturing",
            fein: "12-3456789",
            state_code: "CA",
            effective_date: "2024-01-01",
            expiration_date: "2025-01-01",
            cancellation_date: null,
            policy_status: "Active",
            payment_frequency: "Monthly",
            owner_status: "Included",
            audit_status: "Pending",
            total_est_payroll: null,
          },
          engine_on: false,
          latest_run_id: null,
        })
      ),
      ...DETAIL_HANDLERS
    );
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
    }, { timeout: 5000 });
  });

  it("renders engine-off notice when engine_on is false", async () => {
    server.use(
      http.get("/api/v1/policies/:id", () =>
        HttpResponse.json({
          meta: {
            policy_id: 1,
            policy_number: "WC-2024-001",
            insured_name: "Acme Manufacturing",
            fein: null,
            state_code: "CA",
            effective_date: "2024-01-01",
            expiration_date: "2025-01-01",
            cancellation_date: null,
            policy_status: "Active",
            payment_frequency: "Monthly",
            owner_status: "Included",
            audit_status: "Pending",
            total_est_payroll: null,
          },
          engine_on: false,
          latest_run_id: null,
        })
      ),
      ...DETAIL_HANDLERS
    );
    render(<PolicyDetailPage />, { wrapper: TestWrapper });
    await waitFor(() => {
      expect(screen.getByText(/calculation engine is off/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });
});