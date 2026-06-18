/**
 * CarrierManagementPanel.test.tsx — Phase 7A
 *
 * 12 test cases covering:
 *   - Renders assigned carrier list
 *   - Renders empty state when no carriers assigned
 *   - Renders available carriers in Add section
 *   - Add carrier calls POST /api/v1/tenant/carriers
 *   - Add carrier button disabled when nothing selected
 *   - Add carrier shows error on API failure
 *   - Remove carrier shows confirm inline
 *   - Remove carrier calls DELETE on confirm
 *   - Remove carrier cancels inline confirm
 *   - All assigned carriers shown in available after removal
 *   - Loading state renders gracefully
 *   - Add hint text is displayed
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { CarrierManagementPanel } from "@/features/administration/organization/CarrierManagementPanel";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const ASSIGNED_CARRIERS = [
  { carrier_id: 1, carrier_name: "Acme Insurance", carrier_slug: "acme", carrier_code: "acme", is_active: true },
  { carrier_id: 2, carrier_name: "Beta Mutual", carrier_slug: "beta", carrier_code: "beta", is_active: true },
];

const AVAILABLE_CARRIERS = [
  { carrier_id: 3, carrier_name: "Gamma Re", slug: "gamma" },
  { carrier_id: 4, carrier_name: "Delta Cover", slug: "delta" },
];

// ---------------------------------------------------------------------------
// MSW server
// ---------------------------------------------------------------------------

const server = setupServer(
  http.get("/api/v1/tenant/carriers", () => HttpResponse.json(ASSIGNED_CARRIERS)),
  http.get("/api/v1/tenant/carriers/available", () => HttpResponse.json(AVAILABLE_CARRIERS)),
  http.post("/api/v1/tenant/carriers", () =>
    HttpResponse.json({ carrier_id: 3, carrier_name: "Gamma Re", slug: "gamma", is_active: true, message: "Added." }, { status: 201 })
  ),
  http.delete("/api/v1/tenant/carriers/:id", () => new HttpResponse(null, { status: 204 })),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CarrierManagementPanel />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CarrierManagementPanel", () => {
  test("renders assigned carriers table with carrier names", async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText("Acme Insurance")).toBeInTheDocument();
      expect(screen.getByText("Beta Mutual")).toBeInTheDocument();
    });
  });

  test("renders empty state when no carriers assigned", async () => {
    server.use(
      http.get("/api/v1/tenant/carriers", () => HttpResponse.json([]))
    );
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText(/no carriers assigned yet/i)).toBeInTheDocument();
    });
  });

  test("renders available carriers in Add a Carrier section", async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText("Gamma Re")).toBeInTheDocument();
      expect(screen.getByText("Delta Cover")).toBeInTheDocument();
    });
  });

  test("Add Carrier button is disabled when nothing selected", async () => {
    renderPanel();
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /add carrier/i });
      expect(btn).toBeDisabled();
    });
  });

  test("selecting a carrier enables the Add Carrier button", async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText("Gamma Re")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "3" } });
    const btn = screen.getByRole("button", { name: /add carrier/i });
    expect(btn).not.toBeDisabled();
  });

  test("clicking Add Carrier calls POST /api/v1/tenant/carriers", async () => {
    let postCalled = false;
    server.use(
      http.post("/api/v1/tenant/carriers", () => {
        postCalled = true;
        return HttpResponse.json({ carrier_id: 3, is_active: true, message: "Added." }, { status: 201 });
      })
    );
    renderPanel();
    await waitFor(() => screen.getByText("Gamma Re"));
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /add carrier/i }));
    await waitFor(() => expect(postCalled).toBe(true));
  });

  test("shows error message on Add Carrier API failure", async () => {
    server.use(
      http.post("/api/v1/tenant/carriers", () =>
        HttpResponse.json({ detail: "Carrier not found." }, { status: 404 })
      )
    );
    renderPanel();
    await waitFor(() => screen.getByText("Gamma Re"));
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /add carrier/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
  });

  test("clicking Remove shows inline confirmation", async () => {
    renderPanel();
    await waitFor(() => screen.getByText("Acme Insurance"));
    const removeButtons = screen.getAllByRole("button", { name: /remove/i });
    fireEvent.click(removeButtons[0]);
    expect(screen.getByText(/remove this carrier\?/i)).toBeInTheDocument();
  });

  test("clicking Cancel hides inline confirmation", async () => {
    renderPanel();
    await waitFor(() => screen.getByText("Acme Insurance"));
    const removeButtons = screen.getAllByRole("button", { name: /remove/i });
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByText(/remove this carrier\?/i)).not.toBeInTheDocument();
  });

  test("clicking Confirm calls DELETE /api/v1/tenant/carriers/:id", async () => {
    let deleteCalled = false;
    server.use(
      http.delete("/api/v1/tenant/carriers/:id", () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    renderPanel();
    await waitFor(() => screen.getByText("Acme Insurance"));
    const removeButtons = screen.getAllByRole("button", { name: /remove/i });
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    await waitFor(() => expect(deleteCalled).toBe(true));
  });

  test("shows all assigned hint text", async () => {
    server.use(
      http.get("/api/v1/tenant/carriers/available", () => HttpResponse.json([]))
    );
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText(/all available platform carriers/i)).toBeInTheDocument();
    });
  });

  test("add hint text is rendered below add form", async () => {
    renderPanel();
    await waitFor(() => {
      expect(
        screen.getByText(/seeds default calculation rules/i)
      ).toBeInTheDocument();
    });
  });

  test("loading state renders without crashing", () => {
    server.use(
      http.get("/api/v1/tenant/carriers", () => new Promise(() => {})), // hang forever
      http.get("/api/v1/tenant/carriers/available", () => new Promise(() => {}))
    );
    renderPanel();
    expect(screen.getAllByText(/loading/i).length).toBeGreaterThan(0);
  });
});
