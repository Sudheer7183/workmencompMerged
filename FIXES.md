# Phase 2 — Bug Fixes Applied

## Summary of Issues Fixed

---

### Bug 1 — Login broken: Keycloak realm JSON used wrong protocol mapper type

**File:** `infra/keycloak/audit-platform-realm.json`

**Root cause:**
The `role-string-mapper` used `oidc-usermodel-realm-role-mapper` — a mapper that reads
Keycloak **realm roles** (an array) and maps them to a claim. This emitted an *array* into
the `role` claim, but the backend and frontend both expected a **single string**.

**Fix:**
Changed both `role-string-mapper` and `tenant-slug-mapper` to use
`oidc-usermodel-attribute-mapper` — this reads a **user attribute** (single string) set
directly on the Keycloak user object and maps it to the JWT claim.

User attributes added to each user in the realm JSON:
- `superadmin`   → `role: SUPER_ADMIN`
- `demo-admin`   → `role: TENANT_ADMIN`, `tenant_slug: demo`
- `demo-auditor` → `role: AUDITOR`, `tenant_slug: demo`
- `demo-reviewer`→ `role: REVIEWER`, `tenant_slug: demo`

Also added a `demo-admin` user (TENANT_ADMIN) which was missing from the original realm.

---

### Bug 2 — Dashboard (and Policies) API calls hit wrong URL / missing auth headers

**Files:**
- `frontend/src/features/dashboard/DashboardPage.tsx`
- `frontend/src/features/policies/PoliciesListPage.tsx`
- `frontend/src/features/policies/PolicyDetailPage.tsx`

**Root cause:**
All three pages used raw `fetch()` with a hardcoded `"X-Tenant-Slug": "demo"` header.
This meant:
1. No `Authorization: Bearer <jwt>` header was sent → backend returned 401.
2. The tenant slug was hardcoded to "demo" rather than using the authenticated user's tenant.
3. Raw `fetch` bypasses the axios interceptors where auth headers are centralised.

**Fix:**
Replaced all `fetch()` calls with `axios.get()`. Because `AuthContext` sets
`axios.defaults.headers.common["Authorization"]` and `axios.defaults.headers.common["X-Tenant-Slug"]`
immediately after Keycloak authentication, every `axios` call automatically carries
the correct headers without any per-call configuration.

---

### Bug 3 — API calls resolving to frontend origin instead of backend

**File:** `frontend/vite.config.ts`

**Root cause:**
The proxy target was hardcoded to `http://backend:8000` — the internal Docker Compose
DNS name. When running `npm run dev` outside Docker (e.g. bare `npm run dev` on the
host machine), the name `backend` cannot be resolved, so `/api/*` requests fell back
to the frontend origin (port 5173) and returned 404 / HTML responses.

**Fix:**
Made the proxy target environment-aware via a new `VITE_BACKEND_URL` env variable:
- Docker Compose sets `VITE_BACKEND_URL=http://backend:8000` (internal DNS)
- Local dev outside Docker defaults to `http://localhost:8000`

---

### Bug 4 — TenantMiddleware blocked SUPER_ADMIN /platform/* requests

**File:** `backend/app/tenancy/middleware.py`

**Root cause:**
The `_EXEMPT_PATH_PREFIXES` set listed individual paths (`/platform/tenants`,
`/platform/carriers`, ...) but not a single `/platform` prefix. Any future
`/platform/*` path (or a typo in the list) would be subject to tenant resolution,
causing a 400/404 for SUPER_ADMIN users who have no tenant slug.

**Fix:**
Replaced the four individual `/platform/...` entries with a single `/platform` prefix.
`str.startswith()` makes this cover every current and future `/platform/*` path.

---

### Bug 5 — AuthContext set axios headers AFTER fetching onboarding status

**File:** `frontend/src/context/AuthContext.tsx`

**Root cause:**
The original code fetched `onboarding_completed` (via `fetchOnboardingCompleted`)
*before* setting `axios.defaults.headers.common["Authorization"]` and
`axios.defaults.headers.common["X-Tenant-Slug"]`. The API call went out without
auth headers and the backend returned 401, causing `fetchOnboardingCompleted` to
silently return `false` for every user.

**Fix:**
Moved the `axios.defaults.headers.common` assignments to *before* the
`fetchOnboardingCompleted()` call so the request carries the correct headers.

---

### Bug 6 — `.env` DB credentials didn't match docker-compose defaults

**File:** `.env`

**Root cause:**
`.env` had `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/audit_platform`
but `docker-compose.yml` defaults to `POSTGRES_USER=auditplatform` /
`POSTGRES_PASSWORD=auditplatform_dev` / `POSTGRES_DB=auditplatform`. The backend
would fail to connect to the database.

**Fix:**
Updated `.env` to use `auditplatform:auditplatform_dev@db:5432/auditplatform`,
matching the docker-compose defaults.

---

## Credential Reference (dev)

| User | Password | Role | Tenant |
|------|----------|------|--------|
| superadmin | admin123 | SUPER_ADMIN | (none) |
| demo-admin | admin123 | TENANT_ADMIN | demo |
| demo-auditor | auditor123 | AUDITOR | demo |
| demo-reviewer | reviewer123 | REVIEWER | demo |

---

## Running the Application

### Option A — Full Docker Compose (with Keycloak)

```bash
# Ensure .env has SKIP_JWT_VERIFICATION=false  (default)
docker-compose up --build
```

Services start in order. Keycloak takes ~90 seconds to fully initialise.
Access at: http://localhost:5173

### Option B — Dev bypass (no Keycloak required)

Set both flags in `.env`:
```
SKIP_JWT_VERIFICATION=true
VITE_SKIP_AUTH=true
```

Then:
```bash
docker-compose up --build
# or locally:
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

The dev-mock AUDITOR user (tenant: demo) is used automatically — no login needed.
