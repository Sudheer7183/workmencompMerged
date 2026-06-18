/**
 * UserManagement integration tests — 5 cases (Phase 2, V9 S13.2)
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import "@testing-library/jest-dom";
import { UsersList } from "@/features/administration/user-management/UsersList";

// ---------------------------------------------------------------------------
// Mock factory — call makeAuthMock(role) to get a fresh mock per test
// ---------------------------------------------------------------------------

function makeAuthMock(role: string = "TENANT_ADMIN") {
  return {
    user: {
      sub: "test-sub",
      email: role === "REVIEWER" ? "reviewer@demo.example.com" : "admin@demo.example.com",
      role,
      tenant_slug: "demo",
      onboarding_completed: true,
    },
    isAuthenticated: true,
    token: "test-token",
    login: vi.fn(),
    logout: vi.fn(),
    isLoading: false,
    completeOnboarding: vi.fn(),
  };
}

// Module-level mutable ref so the factory can swap role per-test
let _currentAuthMock = makeAuthMock("TENANT_ADMIN");

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(() => _currentAuthMock),
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
// Helpers
// ---------------------------------------------------------------------------

function renderList(role: string = "TENANT_ADMIN") {
  // Update the mutable ref before rendering — all useAuth() calls in this
  // render tree will pick up the new value immediately.
  _currentAuthMock = makeAuthMock(role);

  // Fresh QueryClient per render so cached data doesn't bleed between tests.
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <UsersList />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UserManagement", () => {

  beforeEach(() => {
    // Ensure each test starts with default TENANT_ADMIN auth
    _currentAuthMock = makeAuthMock("TENANT_ADMIN");
  });

  it("renders user list with role badges", async () => {
    renderList();
    await waitFor(() => {
      expect(screen.getByText("admin@demo.example.com")).toBeInTheDocument();
      expect(screen.getByText("auditor@demo.example.com")).toBeInTheDocument();
    });
    // Component maps: TENANT_ADMIN → "Admin", AUDITOR → "Auditor"
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Auditor")).toBeInTheDocument();
  });

  it("TENANT_ADMIN can open create user modal", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /invite user/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /invite user/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("create user modal has role selector limited to AUDITOR and REVIEWER", async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /invite user/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /invite user/i }));

    // CreateUserModal uses radio buttons with data-testid, not a <select>
    await waitFor(() =>
      expect(screen.getByTestId("role-option-auditor")).toBeInTheDocument()
    );
    expect(screen.getByTestId("role-option-reviewer")).toBeInTheDocument();
    expect(screen.queryByTestId("role-option-tenant_admin")).not.toBeInTheDocument();
    expect(screen.queryByTestId("role-option-super_admin")).not.toBeInTheDocument();
  });

  it("REVIEWER cannot see Invite User button", async () => {
    // Render as REVIEWER — _currentAuthMock is updated inside renderList()
    renderList("REVIEWER");
    await waitFor(() =>
      expect(screen.getByText("auditor@demo.example.com")).toBeInTheDocument()
    );
    // REVIEWER has no canCreateUsers — Invite User button must be absent
    expect(screen.queryByRole("button", { name: /invite user/i })).not.toBeInTheDocument();
  });

  it("deactivate user shows confirmation dialog", async () => {
    const user = userEvent.setup();
    renderList();
    // Edit button renders text "Edit" with no aria-label
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /^edit$/i }).length).toBeGreaterThan(0)
    );
    const editBtns = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editBtns[0]);

    await waitFor(() =>
      expect(screen.getByRole("dialog")).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /deactivate/i }));
    expect(await screen.findByText(/are you sure/i)).toBeInTheDocument();
  });
});