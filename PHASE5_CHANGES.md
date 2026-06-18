# PHASE5_CHANGES.md

## WC Premium Audit Platform — Phase 5 Changes

This document describes every file added or modified in Phase 5 relative to the
Phase 4 codebase. Phase 6 implementers must read this file before writing any code.

---

## Infrastructure

### Modified Files

| File | Change |
|---|---|
| `backend/pyproject.toml` | Added `weasyprint==62.3` and `jinja2==3.1.4` to `dependencies`. Added `moto[s3]==5.0.21` to `dev` deps. |
| `backend/Dockerfile` | Added WeasyPrint GTK/Pango/Cairo/fonts system dependencies via `apt-get`. |
| `docker-compose.yml` | Added `minio` service (port 9000 S3 API, 9001 Console), `minio-init` service (creates bucket), `minio_data` volume. Added MinIO env vars to `backend` service. `backend` now `depends_on: minio`. |
| `.env.example` | Added S3/MinIO vars: `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`. |

---

## Backend

### New Files

| File | Purpose |
|---|---|
| `backend/app/models/reports.py` | `CarrierReportTemplate` and `ReportJob` ORM models. `run_id` on `ReportJob` is added by migration 0009. |
| `backend/app/services/s3_service.py` | `S3Service` — `upload_bytes()`, `presign_url()`, `key_exists()`. MinIO-compatible via `S3_ENDPOINT_URL`. |
| `backend/app/services/report_generation_service.py` | `ReportGenerationService` — all 5 report type generators. PDF via WeasyPrint+Jinja2. Excel via openpyxl. `validate_report_request()` for type/format checks. |
| `backend/app/services/report_job_service.py` | `ReportJobService` — `create_job()` (with 24h idempotency), `run_job()` (background, S3 atomicity), `get_status()` (with carrier scope). |
| `backend/app/api/v1/reports.py` | Reports API router: `POST /api/v1/reports/generate`, `GET /api/v1/reports/{job_id}/status`, `GET/PUT /api/v1/admin/report-template/{carrier_id}`, `POST /api/v1/tenant/branding/report-logo/{carrier_id}`. |
| `backend/app/templates/reports/base.html` | WeasyPrint Jinja2 base template — header, footer, table styles. Explicit hex colours only (no CSS vars). |
| `backend/app/templates/reports/policy_audit.html` | Policy Audit Report template — extends base. |
| `backend/app/templates/reports/book_summary.html` | Policy Book Summary template — extends base. |
| `backend/alembic/versions/0009_report_jobs_run_id.py` | Adds `run_id` column to `report_jobs` in all tenant schemas. |

### Modified Files

| File | Change |
|---|---|
| `backend/app/models/__init__.py` | Added `CarrierReportTemplate`, `ReportJob` imports. |
| `backend/app/main.py` | Registered `reports.router` at `/api/v1`. Updated phase string to "5". |

---

## Frontend

### New Files

| File | Purpose |
|---|---|
| `frontend/src/features/reports/services/reportsApi.ts` | All axios API calls for reports: `generateReport`, `getReportStatus`, `getReportTemplate`, `putReportTemplate`, `uploadReportLogo`. Also exports `isExcelOnly()`. |
| `frontend/src/features/reports/ReportJobPoller.tsx` | Render-less component. Polls `GET /reports/{jobId}/status` every 3s. Max 5 minutes. Calls `onComplete(fileUrl)` or `onError(detail)`. |
| `frontend/src/features/reports/ReportDownloadLink.tsx` | Button that opens the pre-signed S3 URL in a new tab. |
| `frontend/src/features/reports/ReportStatusModal.tsx` | Modal wrapping `ReportJobPoller` + `ReportDownloadLink`. Three states: GENERATING / COMPLETE / FAILED. |
| `frontend/src/features/reports/RequestReportButton.tsx` | Format-selector button + `ReportStatusModal` trigger. Single button for Excel-only types; dropdown for PDF+Excel types. |
| `frontend/src/features/reports/index.ts` | Public surface exports for the reports feature. |
| `frontend/src/features/carrier-config/components/ReportTemplateTab.tsx` | Tab 5 of `CarrierConfigHub`. Logo upload, colour pickers, contact block, PDF preview, save. |

### Modified Files

| File | Change |
|---|---|
| `frontend/src/features/carrier-config/components/CarrierConfigHub.tsx` | Replaced `case 5: ComingSoonTab` with live `ReportTemplateTab` (TENANT_ADMIN only). Added `ReportTemplateTab` import. |
| `frontend/src/features/policies/PolicyDetailPage.tsx` | Added `RequestReportButton` import. Added "Generate Audit Report" button in the policy meta card header. |
| `frontend/src/features/policies/PoliciesListPage.tsx` | Added `RequestReportButton` import. Added "Policy Book Summary" button in page header. |
| `frontend/src/features/ingestion/ExceptionTracker.tsx` | Activated real report generation. Replaced Phase 4 `exportToast` stub with `activeJobId` state + `ReportStatusModal`. Calls `generateReport()` from `reportsApi`. Added `useTenantCarrier` for `carrierId`. |
| `frontend/src/styles/components.css` | Added BEM CSS for `.report-template-tab`, `.request-report-btn`, `.report-status-modal`. |

---

## Tests

### New Test Files

| File | Tests |
|---|---|
| `tests-integrated/backend/unit/test_report_generation_service.py` | 17 tests: branding resolution (3-level chain), all 5 generators, NULL→N/A in PDF+Excel, Excel header colour, Jinja2 filters, format validation. |
| `tests-integrated/backend/unit/test_s3_service.py` | 7 tests: upload, pre-signed URL, key_exists, MinIO path-style — all via moto mock. |
| `tests-integrated/backend/unit/test_report_job_service.py` | 9 tests: create_job idempotency, run_job status transitions, S3 atomicity (file_url not set on failure), carrier scope. |
| `tests-integrated/backend/integration/test_reports_api.py` | 14 tests: 202 responses, 422 validations, status polling, template CRUD. |
| `tests-integrated/frontend/unit/RequestReportButton.test.tsx` | 10 tests: Excel-only single button, dropdown for dual-format, API calls, modal opening, disabled state, no hardcoded hex, labels. |
| `tests-integrated/frontend/unit/ReportStatusModal.test.tsx` | 11 tests: three states, polling stops on terminal, timeout handling, onClose/onRetry, Download opens file_url. |
| `tests-integrated/e2e/tests/13-report-policy-audit.spec.ts` | 4 E2E specs: PDF + Excel generation, REVIEWER can't generate, dropdown closes. |
| `tests-integrated/e2e/tests/14-report-book-summary.spec.ts` | 2 E2E specs: PDF + Excel from PoliciesListPage. |
| `tests-integrated/e2e/tests/15-report-exception-report.spec.ts` | 2 E2E specs: modal appears (not stub toast), run_id in payload. |
| `tests-integrated/e2e/tests/16-report-template-tab.spec.ts` | 6 E2E specs: TENANT_ADMIN access, save, hex validation, PDF preview, AUDITOR denied, no hardcoded hex. |

---

## Key Phase 5 Architectural Decisions

### S3 Atomicity
`report_jobs.file_url` is written ONLY after `S3Service.upload_bytes()` returns
without exception. Steps in `run_job()`: 1=PROCESSING, 2=generate, 3=upload,
4=presign, 5=write file_url+COMPLETE. A failure in steps 2–4 writes FAILED
without touching file_url.

### WeasyPrint/Docker Constraint
WeasyPrint requires GTK/Pango system libraries. The `backend/Dockerfile` installs
them via `apt-get`. Verify with: `python -c "from weasyprint import HTML; print('OK')"`
inside the container.

### PDF Colour Rule
Report PDFs always use explicit 6-char hex colours from `carrier_report_templates`
injected via Jinja2 context — NEVER CSS custom properties. WeasyPrint has no DOM
and cannot resolve CSS variables.

### Idempotency Window
`ReportJobService.create_job()` returns an existing COMPLETE job_id if the same
request (carrier_id + policy_id + report_type + output_format + run_id) was made
within the last 24 hours. This matches the pre-signed URL TTL (24h).

### Phase 6 Entry Points
- `CarrierConfigHub.tsx` Tab 4 renders `<ComingSoonTab phase={6} />` — Labels & Display tab
- `CarrierConfigHub.tsx` Tab 6 renders `<ComingSoonTab phase={6} />` — Theme tab
- `useLabels()` hook returns static defaults — Phase 6 makes it a live API call
- `useTheme()` hook reads CSS vars from static config — Phase 6 serves from DB
