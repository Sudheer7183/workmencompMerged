/**
 * Vitest test setup — Phase 2.
 *
 * Configures @testing-library/jest-dom matchers and MSW server.
 * Phase 2 adds handlers for:
 *   - tenant branding (GET /api/v1/tenant/branding)
 *   - platform tenants (GET, POST /platform/tenants, GET /platform/tenants/:slug)
 *   - platform carriers (GET, POST /platform/carriers)
 *   - tenant carriers (GET /api/v1/tenant/carriers)
 *   - tenant users (GET, POST /api/v1/tenant/users, GET /api/v1/tenant/users/me)
 *   - tenant contacts (GET, PUT /api/v1/tenant/contacts)
 *   - tenant profile (GET, PUT /api/v1/tenant/profile)
 */

import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

// ── jsdom polyfills ─────────────────────────────────────────────────────────
// recharts uses ResizeObserver; jsdom doesn't ship it — provide a no-op mock.
// This must be declared before any tests run.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// ---------------------------------------------------------------------------
// Shared fixture data
// ---------------------------------------------------------------------------

export const MOCK_BRANDING = {
  logo_url: null,
  logo_dark_url: null,
  brand_color: null,
};

export const MOCK_CARRIERS = [
  { carrier_id: 1, name: "State Farm", slug: "state-farm", ai_narrative_enabled: true },
  { carrier_id: 2, name: "Travelers",  slug: "travelers",  ai_narrative_enabled: false },
];

// /api/v1/tenant/carriers uses a different response shape (carrier_name, carrier_code)
// than /platform/carriers (name, slug). They map to different DB views/tables.
export const MOCK_TENANT_CARRIERS = [
  { carrier_id: 1, carrier_name: "State Farm", carrier_code: "SF",  is_configured: false },
  { carrier_id: 2, carrier_name: "Travelers",  carrier_code: "TRV", is_configured: false },
];

export const MOCK_TENANTS = [
  {
    slug: "demo",
    display_name: "Demo Tenant",
    schema_name: "tenant_demo",
    tenant_type: "STANDARD",
    status: "ACTIVE",
    carrier_count: 2,
    created_at: "2025-01-01T00:00:00Z",
  },
];

export const MOCK_USERS = [
  {
    user_id: 1,
    email: "admin@demo.example.com",
    first_name: "Demo",
    last_name: "Admin",
    role: "TENANT_ADMIN",
    onboarding_completed: true,
  },
  {
    user_id: 2,
    email: "auditor@demo.example.com",
    first_name: "Demo",
    last_name: "Auditor",
    role: "AUDITOR",
    onboarding_completed: true,
  },
];

export const MOCK_ME = {
  user_id: 1,
  email: "admin@demo.example.com",
  first_name: "Demo",
  last_name: "Admin",
  role: "TENANT_ADMIN",
  onboarding_completed: false,
};

// ---------------------------------------------------------------------------
// Phase 1 handlers
// ---------------------------------------------------------------------------

const phase1Handlers = [
  http.get("/api/v1/dashboard/summary", () =>
    HttpResponse.json({
      carrier_id: 1,
      kpi: {
        total_book_premium: 5000000,
        total_est_earned_premium: 4800000,
        total_actual_earned_premium: 4950000,
        total_variance_amount: 150000,
      },
      policy_status: { active_count: 85, cancelled_count: 15 },
      risk_distribution: { high_count: 12, medium_count: 28, low_count: 45, unassigned_count: 15 },
      state_risk_profiles: [
        { state_code: "CA", high_count: 5, medium_count: 10, low_count: 20 },
      ],
      target_variance: { policies_above_threshold: 12, total_variance_above_threshold: 120000, threshold_pct: 30 },
    })
  ),

  http.get("/api/v1/policies", () =>
    HttpResponse.json({
      items: [
        {
          policy_id: 1,
          policy_number: "WC-2024-001",
          insured_name: "Acme Manufacturing",
          state_code: "CA",
          effective_date: "2024-01-01",
          policy_status: "Active",
          est_premium: 120000,
          variance_amount: 15000,
          variance_pct: 0.125,
          risk_level: "Medium",
          audit_status: "In-Review",
        },
      ],
      total: 1,
      page: 1,
      page_size: 25,
    })
  ),

  // Sub-resource handlers MUST be registered before the /:id wildcard to
  // guarantee they are matched first in every test environment.
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

  http.get("/api/v1/policies/:id", ({ params }) =>
    HttpResponse.json({
      meta: {
        policy_id: Number(params["id"]),
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
];

// ---------------------------------------------------------------------------
// Phase 2 handlers
// ---------------------------------------------------------------------------

const phase2Handlers = [
  // Branding
  http.get("/api/v1/tenant/branding", () => HttpResponse.json(MOCK_BRANDING)),
  http.put("/api/v1/tenant/branding", () => HttpResponse.json({ ...MOCK_BRANDING })),
  http.post("/api/v1/tenant/branding/logo", () =>
    HttpResponse.json({ logo_url: "https://cdn.example.com/logo.png" })
  ),

  // Tenant carriers — returns { carrier_id, carrier_name, carrier_code, is_configured }
  http.get("/api/v1/tenant/carriers", () => HttpResponse.json(MOCK_TENANT_CARRIERS)),

  // Tenant profile
  http.get("/api/v1/tenant/profile", () =>
    HttpResponse.json({
      display_name: "Demo Tenant",
      legal_name: "Demo Tenant LLC",
      address_line1: "123 Main St",
      address_line2: null,
      city: "San Francisco",
      state_code: "CA",
      zip_code: "94102",
    })
  ),
  http.put("/api/v1/tenant/profile", () => HttpResponse.json({ display_name: "Demo Tenant" })),

  // Tenant contacts
  http.get("/api/v1/tenant/contacts", () =>
    HttpResponse.json([
      { contact_type: "PRIMARY", contact_name: "Alice Smith", contact_email: "alice@demo.example.com", contact_phone: null },
      { contact_type: "SECONDARY", contact_name: "Bob Jones", contact_email: "bob@demo.example.com", contact_phone: null },
    ])
  ),
  http.put("/api/v1/tenant/contacts", () => HttpResponse.json([])),

  // Tenant users
  http.get("/api/v1/tenant/users", () => HttpResponse.json(MOCK_USERS)),
  http.post("/api/v1/tenant/users", () =>
    HttpResponse.json({ user_id: 99, email: "new@demo.example.com", role: "AUDITOR" }, { status: 201 })
  ),
  http.get("/api/v1/tenant/users/me", () => HttpResponse.json(MOCK_ME)),
  http.patch("/api/v1/tenant/users/:id", () => HttpResponse.json({ user_id: 1, role: "REVIEWER" })),
  http.delete("/api/v1/tenant/users/:id", () => new HttpResponse(null, { status: 204 })),
  http.patch("/api/v1/tenant/users/me", () => HttpResponse.json({ ...MOCK_ME, onboarding_completed: true })),

  // Platform tenants
  http.get("/platform/tenants", () => HttpResponse.json(MOCK_TENANTS)),
  http.post("/platform/tenants", () =>
    HttpResponse.json({ slug: "new-tenant", status: "ACTIVE" }, { status: 201 })
  ),
  http.get("/platform/tenants/:slug", ({ params }) => {
    const tenant = MOCK_TENANTS.find((t) => t.slug === params["slug"]);
    if (!tenant) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(tenant);
  }),
  http.post("/platform/tenants/:slug/activate", ({ params }) =>
    HttpResponse.json({ slug: params["slug"], status: "ACTIVE" })
  ),

  // Platform carriers
  http.get("/platform/carriers", () => HttpResponse.json(MOCK_CARRIERS)),
  http.post("/platform/carriers", () =>
    HttpResponse.json({ carrier_id: 99, name: "New Carrier", slug: "new-carrier", ai_narrative_enabled: false }, { status: 201 })
  ),
];

export const handlers = [...phase1Handlers, ...phase2Handlers];
export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());