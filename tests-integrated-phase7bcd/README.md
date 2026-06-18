# Phase 7B–7D + Integrated Test Package

## Overview

This test package covers Phases 7B (Screen Redesigns), 7C (AI Narrative + LLM Config),
and 7D (Drag-and-Drop Field Builder). It also provides integrated regression coverage
for the full Phase 1–7A codebase.

## Prerequisites

- Phase 7A codebase running with all Phase 7A tests passing
- All Phase 7B–7D code implemented
- Python 3.12+, Node.js 18+
- PostgreSQL with test database
- Redis instance
- `LLM_KEY_ENCRYPTION_SECRET` set to a valid Fernet key
- `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities` installed
- Playwright browsers installed: `npx playwright install`

## Generate Fernet Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Environment Variables Required

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb
REDIS_URL=redis://localhost:6379/1
LLM_KEY_ENCRYPTION_SECRET=<generated Fernet key>
ANTHROPIC_API_KEY=<optional — used for live LLM tests>
SKIP_JWT_VERIFICATION=true
```

## Running Tests

### Backend unit tests
```bash
cd backend
SKIP_JWT_VERIFICATION=true pytest tests-integrated-phase7bcd/backend/unit/ -v
```

### Backend integration tests
```bash
SKIP_JWT_VERIFICATION=true pytest tests-integrated-phase7bcd/backend/integration/ -v
```

### All backend tests (regression + new)
```bash
SKIP_JWT_VERIFICATION=true pytest tests/ tests-integrated-phase7bcd/backend/ -v --tb=short
```

### Frontend unit tests
```bash
cd frontend
npx jest tests-integrated-phase7bcd/frontend/unit/ --coverage
```

### Frontend render tests
```bash
npx jest tests-integrated-phase7bcd/frontend/render/
```

### All Playwright E2E tests (specs 01–25)
```bash
npx playwright test
```

### New E2E specs only (23–25)
```bash
npx playwright test tests-integrated-phase7bcd/e2e/
```

## Test Coverage Targets

| Layer | Target |
|---|---|
| Backend unit | 90%+ for new services |
| Backend integration | All CRUD paths + error cases |
| Frontend unit | All component states + edge cases |
| E2E | All user flows for 7B, 7C, 7D features |

## Notes

- Tests 01–22 (existing Playwright specs) must continue passing — any regression is a blocker.
- LLM tests that make real API calls are tagged `@live` and are skipped in CI by default.
  Set `RUN_LIVE_LLM_TESTS=true` to enable them.
- Drag-and-drop E2E tests use Playwright's `dragTo()` API.
  Ensure the test browser supports HTML5 drag-and-drop (Chromium recommended).
- Run the Alembic migration `0012_phase7c_llm_config` before integration tests.
