# WC Premium Audit Platform

Workers Compensation Premium Audit Platform — Phases 1 & 2.

---

## Prerequisites

- Docker & Docker Compose v2+
- Node.js 20+, npm 10+
- Python 3.12+

---

## Phase 1 — Quick Start (no auth required)

```bash
# 1. Copy and configure environment
cp .env.example .env
# Set VITE_SKIP_AUTH=true and SKIP_JWT_VERIFICATION=true in .env

# 2. Start services (PostgreSQL + Redis only)
docker compose up db redis --build -d

# 3. Run backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
SKIP_JWT_VERIFICATION=true uvicorn app.main:app --reload

# 4. Run frontend
cd frontend
npm install
VITE_SKIP_AUTH=true npm run dev
```

---

## Phase 2 — Full Stack with Keycloak

```bash
# 1. Start all services including Keycloak
docker compose up --build -d

# 2. Wait for Keycloak health check (~30 s)
docker compose logs -f keycloak | grep "Keycloak.*started"

# 3. Realm is auto-imported from infra/keycloak/audit-platform-realm.json
#    Seed users created automatically:
#      superadmin@platform.local  / ChangeMe123!  (SUPER_ADMIN)
#      admin@demo.platform.local  / ChangeMe123!  (TENANT_ADMIN, tenant: demo)
#      auditor@demo.platform.local / ChangeMe123! (AUDITOR, tenant: demo)

# 4. Run frontend (Keycloak auth)
cd frontend
npm install
npm run dev
# Visit http://localhost:5173 — redirects to Keycloak login
```

---

## Running Tests

### Backend

```bash
cd backend

# Phase 1 regression (no Docker required)
SKIP_JWT_VERIFICATION=true pytest tests/unit/ -v

# Phase 2 new tests (requires running Keycloak + Postgres + Redis)
SKIP_JWT_VERIFICATION=false \
  KEYCLOAK_URL=http://localhost:8080 \
  pytest tests/ -v -k "phase2 or keycloak or provisioning or tenant_admin" \
  --cov=app --cov-report=term-missing

# Full suite with coverage
SKIP_JWT_VERIFICATION=false pytest tests/ --cov=app --cov-report=term-missing

# Multi-tenant isolation
pytest tests/integration/test_multi_tenant_isolation_phase2.py -v -s
```

### Frontend

```bash
cd frontend

# All tests
npm run test

# With coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

---

## Quality Gates

```bash
# No "AuditAI" or "SmartPay" naming violations
grep -ri "auditai\|smartpay" . \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules \
  && echo "FAIL: naming violation" || echo "PASS: naming clean"

# No LangGraph / LangChain
grep -r "langgraph\|langchain" backend/ \
  && echo "FAIL" || echo "PASS: no langgraph"

# No hardcoded hex in components or features
grep -rn "#[0-9a-fA-F]\{3,6\}" \
  frontend/src/components/ frontend/src/features/ \
  && echo "FAIL: hardcoded hex" || echo "PASS: CSS vars only"

# TypeScript strict check
cd frontend && npx tsc --noEmit
```

---

## Architecture Notes

### Multi-tenancy
- Each tenant gets an isolated PostgreSQL schema (`tenant_{slug}`).
- `TenantMiddleware` sets `search_path` per request using the JWT `tenant_slug` claim.
- SUPER_ADMIN `/platform/*` routes use `search_path = public`.

### JWT Claims (V9)
| Claim | Type | Value |
|---|---|---|
| `sub` | string | Keycloak user UUID |
| `email` | string | User email |
| `role` | string | Single role: `SUPER_ADMIN` / `TENANT_ADMIN` / `AUDITOR` / `REVIEWER` |
| `tenant_slug` | string or absent | Absent for `SUPER_ADMIN` |

### Phase 2 Key Services
- `KeycloakAdminService` — RS256 JWKS verification (Redis-cached), user provisioning.
- `TenantProvisioningService` — 6-step atomic: schema → Alembic → seed → Keycloak → ACTIVE.
- S3 atomicity: `tenant_branding.logo_url` is written only after S3 upload succeeds.
- Redis keys: `keycloak:jwks` (TTL 3600 s), `{schema}:dashboard:{carrier_id}` (TTL 60 s).

### CSS Architecture
All colour values flow exclusively through CSS custom properties defined in
`frontend/src/styles/tokens.css`. The only hardcoded hex values in the entire
codebase live in `frontend/src/hooks/useTheme.ts` (DEFAULT_DARK_TOKENS).
`tenant_branding.brand_color` overrides only `--brand`; all other 12 tokens
remain at Default Dark values until Phase 6.
