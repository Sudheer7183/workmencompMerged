# Phase 7A — Integrated Test Package

This package contains all test artifacts for Phase 7A (Carrier Decoupling).

## Structure

```
phase7a/
├── README.md                          — This file
├── backend/
│   └── unit/
│       └── test_tenant_carrier_management.py   — 12 backend unit + integration cases
├── frontend/
│   └── unit/
│       └── CarrierManagementPanel.test.tsx     — 12 frontend component cases
└── e2e/
    └── 22-tenant-carrier-management.spec.ts    — 10 Playwright E2E cases
```

## Running Tests

### Backend Unit Tests (no DB required)
```bash
cd backend
pytest tests/integration/test_tenant_carrier_management.py -k "not integration" -v
```

### Backend Integration Tests (requires running Postgres + full schema)
```bash
cd backend
pytest tests/integration/test_tenant_carrier_management.py -m integration -v
```

### Frontend Unit Tests
```bash
cd frontend
npx vitest run tests-integrated/frontend/unit/CarrierManagementPanel.test.tsx
```

### Playwright E2E Tests (requires full stack running)
```bash
cd tests-integrated/e2e
npx playwright test 22-tenant-carrier-management.spec.ts --headed
```

### All Phase 7A Tests Together
```bash
# Backend
cd backend && pytest tests/integration/test_tenant_carrier_management.py -v

# Frontend  
cd frontend && npx vitest run

# E2E
cd tests-integrated/e2e && npx playwright test 22-tenant-carrier-management.spec.ts
```

## Phase 7A Completion Gate

All of the following must pass before Phase 7B begins:

- [ ] All 21 existing Playwright E2E specs (01–21) still pass unchanged
- [ ] `test_tenant_carrier_management.py` — all non-integration tests pass
- [ ] `CarrierManagementPanel.test.tsx` — all 12 tests pass
- [ ] `22-tenant-carrier-management.spec.ts` — all relevant tests pass
- [ ] Manual smoke test: SUPER_ADMIN provisions a zero-carrier tenant, it activates
- [ ] Manual smoke test: TENANT_ADMIN adds a carrier, it appears in Carrier Config Hub
