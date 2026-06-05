/**
 * UserManagement integration tests — 5 cases (Phase 2, V9 S13.2)
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import "@testing-library/jest-dom";
import { http, HttpResponse } from "msw";
import { server, MOCK_USERS } from "../setup";
import { UsersList } from "@/features/administration/user-management/UsersList";

// Provide a mock AuthContext so useAuth() returns the required role
vi.mock("@/context/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/context/AuthContext")>();
  return {
    ...actual,
    useAuth: vi.fn(() => ({
      user: {
        sub: "test-sub",
        email: "admin@demo.example.com",
        role: "TENANT_ADMIN",
        tenant_slug: "demo",
        onboarding_completed: true,
      },
      isAuthenticated: true,
      token: "test-token",
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    })),
  };
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    React.createElement(
      QueryClientProvider,
      { client: qc },
      React.createElement(MemoryRouter, null, ui)
    )
  );
}

describe("UserManagement", () => {
  it("renders user list with role badges", async () => {
    wrap(<UsersList />);
    await waitFor(() => {
      expect(screen.getByText("admin@demo.example.com")).toBeInTheDocument();
      expect(screen.getByText("auditor@demo.example.com")).toBeInTheDocument();
    });
    expect(screen.getByText("TENANT_ADMIN")).toBeInTheDocument();
    expect(screen.getByText("AUDITOR")).toBeInTheDocument();
  });

  it("TENANT_ADMIN can open create user modal", async () => {
    const user = userEvent.setup();
    wrap(<UsersList />);
    await waitFor(() => expect(screen.getByRole("button", { name: /create user/i })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /create user/i }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // Modal title is an h2 inside the dialog
    expect(dialog.querySelector("h2")).toHaveTextContent("Create User");
  });

  it("create user modal has role selector limited to AUDITOR and REVIEWER", async () => {
    const user = userEvent.setup();
    wrap(<UsersList />);
    await waitFor(() => expect(screen.getByRole("button", { name: /create user/i })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /create user/i }));

    const roleSelect = screen.getByLabelText(/Role/i) as HTMLSelectElement;
    const options = Array.from(roleSelect.options).map((o) => o.value);
    expect(options).toContain("AUDITOR");
    expect(options).toContain("REVIEWER");
    expect(options).not.toContain("TENANT_ADMIN");
    expect(options).not.toContain("SUPER_ADMIN");
  });

  it("REVIEWER cannot see Create User button", async () => {
    // Override the mock to return REVIEWER role for this test, then restore
    const { useAuth } = await import("@/context/AuthContext");
    const reviewerAuth = {
      user: {
        sub: "test-sub",
        email: "reviewer@demo.example.com",
        role: "REVIEWER",
        tenant_slug: "demo",
        onboarding_completed: true,
      },
      isAuthenticated: true,
      token: "test-token",
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    };
    vi.mocked(useAuth).mockReturnValue(reviewerAuth);

    wrap(<UsersList />);
    await waitFor(() => expect(screen.getByText("auditor@demo.example.com")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /create user/i })).not.toBeInTheDocument();

    // Restore default mock
    vi.mocked(useAuth).mockReturnValue({
      user: {
        sub: "test-sub",
        email: "admin@demo.example.com",
        role: "TENANT_ADMIN",
        tenant_slug: "demo",
        onboarding_completed: true,
      },
      isAuthenticated: true,
      token: "test-token",
      login: vi.fn(),
      logout: vi.fn(),
      isLoading: false,
    });
  });

  it("deactivate user shows confirmation dialog", async () => {
    const user = userEvent.setup();
    wrap(<UsersList />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /edit user/i }).length).toBeGreaterThan(0));
    const editBtns = screen.getAllByRole("button", { name: /edit user/i });
    await user.click(editBtns[0]);

    // Modal open — click deactivate
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /deactivate/i }));

    // Confirmation text appears
    expect(await screen.findByText(/are you sure/i)).toBeInTheDocument();
  });
});
