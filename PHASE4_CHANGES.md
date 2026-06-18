# Phase 4 — Changes & Implementation Notes

## Overview

Phase 4 delivers: Full exception tracking, rollback capability, CSV ingestion, and Data Sources / Field Mapping admin tabs.

---

## New Files

### Backend

| File | Purpose |
|------|---------|
| `backend/app/services/ingestion_error_codes.py` | 8 error codes enum (`IngestionErrorCode`) + `IngestionRowError` exception class (V9 S17.2) |
| `backend/app/services/rollback_service.py` | `RollbackService` — deletes fact rows for a run, writes `ingestion_rollbacks` record (V9 S17.5) |
| `backend/app/api/v1/data_sources.py` | Data Sources CRUD + Field Maps bulk upsert (V9 S15.2 Tabs 1+2) |
| `backend/alembic/versions/0006_phase4_field_maps_columns.py` | Adds `file_type` + `is_active` columns to `ingestion_field_maps` |
| `backend/tests/unit/test_ingestion_error_tracking.py` | 11 unit tests for error codes |
| `backend/tests/unit/test_rollback_service.py` | 12 unit tests for RollbackService |
| `backend/tests/unit/test_csv_ingestion.py` | 8 unit tests for CSV detection |
| `backend/tests/unit/test_orm_models_phase4.py` | 13 unit tests for new ORM models |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/features/ingestion/ExceptionTracker.tsx` | Full exception tracking screen (V9 S17.4, S26.2) |
| `frontend/src/features/carrier-config/components/DataSourcesTab.tsx` | Tab 1 — Data Sources CRUD (V9 S15.2) |
| `frontend/src/features/carrier-config/components/FieldMappingTab.tsx` | Tab 2 — Field Mapping pre-config (V9 S15.2) |
| `frontend/tests/unit/components/ExceptionTracker.test.tsx` | 14 unit tests |
| `frontend/tests/unit/components/DataSourcesTab.test.tsx` | 11 unit tests |

---

## Modified Files

### Backend

| File | Change |
|------|--------|
| `backend/app/models/ingestion.py` | Added `IngestionSkippedRow`, `IngestionRollback`, `IngestionFieldMap` ORM models |
| `backend/app/services/ingestion_service.py` | Appended `IngestionServiceV4` subclass: CSV support, skip_on_error tracking, `_record_skipped_row()` / `_record_error()` helpers |
| `backend/app/api/v1/ingestion.py` | Uses `IngestionServiceV4`; adds `skip_on_error` param to upload; adds CSV detection; appends exception tracking + rollback endpoints |
| `backend/app/main.py` | Registers `data_sources` router |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/features/carrier-config/components/CarrierConfigHub.tsx` | Tabs 1+2 now render `DataSourcesTab` / `FieldMappingTab` instead of `ComingSoonTab` |
| `frontend/src/features/ingestion/IngestionProgress.tsx` | "View Errors" link activated for partial status |
| `frontend/src/features/ingestion/AuditRunnerPage.tsx` | Added type3 (CSV) upload slot |
| `frontend/src/App.tsx` | Added `/audit-runner/:runId/exceptions` route |
| `frontend/src/styles/components.css` | Phase 4 CSS for ExceptionTracker, DataSourcesTab, FieldMappingTab |

---

## Architecture Decisions

### IngestionServiceV4 subclasses IngestionService
Rather than modifying the working Phase 3 class in-place (which risks regressions), Phase 4 uses Python subclassing. The API layer now imports `IngestionServiceV4 as IngestionService`. All Phase 3 parsing logic is inherited; Phase 4 overrides `run()` and `run_post_approval()` only.

### CSV rows collected before routing
CSV ingestion collects all rows into a `list[tuple]` first, then applies the same canonical routing logic as the XLSX `_process_sheet()`. This avoids duplicating the routing logic and allows clean per-row error tracking with row indices.

### Rollback preserves error records
`RollbackService` deletes only from the 5 fact tables. `ingestion_runs`, `ingestion_errors`, and `ingestion_skipped_rows` are intentionally kept as the audit trail. After rollback, `ingestion_runs.status = 'rolled_back'`.

### `ingestion_field_maps` schema extension
The original schema had `map_id`, `carrier_id`, `source_field`, `canonical_column`, `created_at`. Phase 4 migration 0006 adds `file_type` (nullable) and `is_active` (bool, default TRUE).

---

## Running Phase 4

```bash
# Start services
docker-compose up --build

# Run backend tests (includes all phases)
docker-compose exec backend pytest tests/ -v

# Run frontend tests
docker-compose exec frontend npm run test -- --run

# Apply Phase 4 migration (if running Alembic manually)
docker-compose exec backend alembic upgrade head
```

---

## Credential Reference (unchanged from Phase 3)

| User | Password | Role | Tenant |
|------|----------|------|--------|
| superadmin | admin123 | SUPER_ADMIN | (none) |
| demo-admin | admin123 | TENANT_ADMIN | demo |
| demo-auditor | auditor123 | AUDITOR | demo |
| demo-reviewer | reviewer123 | REVIEWER | demo |
