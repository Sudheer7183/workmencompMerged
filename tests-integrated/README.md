# Integrated Test Suite — All Five Phases

Three independent layers. Run in any order. Layer 3 requires running Docker services (including MinIO).

## Layer 1 — Backend pytest (140+ tests)

```bash
# From the project root
cd phase5_v1/backend

# Run full Phase 1–5 suite
SKIP_JWT_VERIFICATION=true pytest tests/ -v --tb=short \
  --cov=app --cov-report=term-missing --cov-report=html:coverage-report

# Run Phase 5 integrated unit tests (report generation, S3, job service)
cd ../tests-integrated
SKIP_JWT_VERIFICATION=true pytest backend/unit/ -v --tb=short
SKIP_JWT_VERIFICATION=true pytest backend/integration/ -v --tb=short
```

Expected: 140+ tests green. New Phase 5 tests: 17 + 7 + 9 (unit) + 14 + 7 (integration).

## Layer 2 — Frontend Vitest (100+ tests)

```bash
# From the project root
cd phase5_v1/frontend
npm run test -- --run --reporter=verbose

# Run Phase 5 integrated frontend tests
cd ../tests-integrated/frontend
npm run test -- --run
```

Expected: 100+ tests green. New Phase 5 tests: 10 + 11 + 11 (unit) + 7 + 4 (integration).

## Layer 3 — E2E Playwright (specs 01–16, requires running services)

```bash
# Step 1: Start all services (includes MinIO from Phase 5)
docker compose up --build -d

# Wait ~90s for Keycloak, ~15s for MinIO
# Verify MinIO console: http://localhost:9001 (minioadmin / minioadmin)
# Verify bucket created: http://localhost:9000/audit-platform-uploads

# Step 2: Run all E2E specs
cd tests-integrated/e2e
npm install
npx playwright install chromium
BASE_URL=http://localhost:5173 npx playwright test --reporter=html
npx playwright show-report

# Run only Phase 5 specs (report generation):
npx playwright test \
  tests/13-report-policy-audit.spec.ts \
  tests/14-report-book-summary.spec.ts \
  tests/15-report-exception-report.spec.ts \
  tests/16-report-template-tab.spec.ts

# Run full suite:
BASE_URL=http://localhost:5173 npx playwright test
```

## Phase 5 — What's New

### Infrastructure
- **MinIO** added to `docker-compose.yml` — local S3-compatible storage for reports
- Console at `http://localhost:9001` (minioadmin/minioadmin)
- Bucket `audit-platform-uploads` created automatically on startup

### WeasyPrint verification
```bash
docker compose exec backend python -c "from weasyprint import HTML; print('WeasyPrint OK')"
```

### Report generation manual test
```bash
# With services running:
curl -s -X POST http://localhost:8000/api/v1/reports/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(./get-token.sh demo-auditor)" \
  -H "X-Tenant-Slug: demo" \
  -d '{"carrier_id":1,"report_type":"book_summary","output_format":"pdf"}' | jq .

# Poll status with returned job_id:
curl -s http://localhost:8000/api/v1/reports/{job_id}/status \
  -H "Authorization: Bearer ..." \
  -H "X-Tenant-Slug: demo" | jq .
```

## Security & Quality Checks

```bash
# Naming — must return PASS
grep -ri "auditai\|smartpay" phase5_v1/ \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules --exclude-dir=.git \
  && echo "FAIL: naming violation" || echo "PASS: naming clean"

# No LangGraph
grep -r "langgraph\|langchain" phase5_v1/backend/ \
  && echo "FAIL" || echo "PASS: no langgraph"

# No hardcoded hex in components/features (except useTheme.ts and report CSS vars)
grep -rn "#[0-9a-fA-F]\{3,6\}" \
  phase5_v1/frontend/src/components/ \
  phase5_v1/frontend/src/features/ \
  && echo "WARN: check manually" || echo "PASS: CSS vars only"

# No raw fetch calls
grep -r "= await fetch\|= fetch(" \
  phase5_v1/frontend/src/ \
  && echo "FAIL: raw fetch found" || echo "PASS: axios only"

# Type checks
cd phase5_v1/backend && python -m mypy app --strict
cd phase5_v1/frontend && npx tsc --noEmit

# data-testid audit (Phase 5 report components)
grep -r "data-testid" phase5_v1/frontend/src/features/reports/ | wc -l
# Expected: 12+
```

## Test count by phase

| Phase | Backend unit | Backend integration | Frontend unit | Frontend integration | E2E specs |
|---|---|---|---|---|---|
| 1 | ~25 | ~15 | ~20 | ~5 | 2 |
| 2 | ~25 | ~15 | ~25 | ~8 | 4 |
| 3 | ~30 | ~15 | ~20 | ~6 | 4 |
| 4 | ~15 | ~15 | ~14 | ~5 | 4 |
| **5** | **33** | **21** | **32** | **11** | **4** |
| **Total** | **128+** | **81+** | **111+** | **35+** | **20** |
