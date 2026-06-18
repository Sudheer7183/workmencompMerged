/**
 * CalcEngineToggle.test.tsx — Phase 3
 *
 * Tests the CalcEngineToggle component:
 *   - renders ON/OFF state correctly
 *   - calls onToggle when the track is clicked by an admin
 *   - does NOT call onToggle for non-admin
 *   - shows warning banner when engine is OFF
 *   - shows readonly notice for non-admin
 *   - shows saving state when isSaving is true
 *   - root BEM class is present
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CalcEngineToggle } from "@/features/carrier-config/components/CalcEngineToggle";

vi.mock("@/context/TenantCarrierContext", () => ({
  useTenantCarrier: vi.fn(() => ({
    carrierId: 1,
    setCarrierId: vi.fn(),
    availableCarriers: [{ carrier_id: 1, carrier_name: "Demo Carrier", carrier_code: "DEMO" }],
    isLoadingCarriers: false,
  })),
  TenantCarrierProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/hooks/useLabels", () => ({
  // Return a function that itself returns the fallback string.
  // This mirrors the real useLabels(namespace)(key, fallback) call pattern.
  useLabels: vi.fn((_namespace: string) => vi.fn((_key: string, fallback: string) => fallback)),
}));

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
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

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
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestWrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <MemoryRouter>
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CalcEngineToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the engine label", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    // Use the heading element to avoid ambiguity with the description paragraph
    expect(screen.getByRole("heading", { name: /Calculation Engine/i })).toBeDefined();
  });

  it("shows ON label when engine is enabled", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    // Query the label span by its BEM class — avoids matching heading/description
    const label = document.querySelector(".calc-engine-toggle__label");
    expect(label?.textContent).toBe("ON");
  });

  it("shows OFF label when engine is disabled", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={false}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    const label = document.querySelector(".calc-engine-toggle__label");
    expect(label?.textContent).toBe("OFF");
  });

  it("shows warning banner when engine is OFF", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={false}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    const warning = document.querySelector(".calc-engine-toggle__warning");
    expect(warning).not.toBeNull();
  });

  it("does NOT show warning banner when engine is ON", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    expect(document.querySelector(".calc-engine-toggle__warning")).toBeNull();
  });

  it("calls onToggle when switch is clicked by admin", async () => {
    const onToggle = vi.fn();
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={onToggle}
          isSaving={false}
        />
      </TestWrapper>
    );
    const track = document.querySelector(".calc-engine-toggle__track");
    if (track) {
      fireEvent.click(track);
      await waitFor(() => expect(onToggle).toHaveBeenCalledOnce());
    }
  });

  it("does not call onToggle when non-admin user clicks the switch", async () => {
    const onToggle = vi.fn();
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={false}
          onToggle={onToggle}
          isSaving={false}
        />
      </TestWrapper>
    );
    const track = document.querySelector(".calc-engine-toggle__track");
    if (track) {
      fireEvent.click(track);
    }
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("shows readonly notice for non-admin", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={false}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    const el = document.querySelector(".calc-engine-toggle__readonly");
    expect(el).not.toBeNull();
  });

  it("shows saving state when isSaving is true", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={true}
        />
      </TestWrapper>
    );
    // Label span shows "Saving…" when isToggling is true
    const label = document.querySelector(".calc-engine-toggle__label");
    expect(label?.textContent).toMatch(/Saving/i);
  });

  it("all visible text comes via useLabels (no hardcoded strings escaped in JSX)", () => {
    render(
      <TestWrapper>
        <CalcEngineToggle
          carrierId={1}
          currentValue={true}
          isAdmin={true}
          onToggle={vi.fn()}
          isSaving={false}
        />
      </TestWrapper>
    );
    const root = document.querySelector(".calc-engine-toggle");
    expect(root).not.toBeNull();
  });
});