# PHASE6_CHANGES.md

## Phase 6 — Full Monthly Cycle, Labels, and Themes

**Root directory:** `phase5_v1/` (unchanged from Phase 5)

---

## New Files

### Backend

| File | Purpose |
|---|---|
| `backend/app/models/config.py` | 6 new ORM models: CarrierUiLabel, CarrierDisplayConfig, CarrierThemeConfig, TenantTheme, UserThemePref, CleanupRun |
| `backend/app/services/cleanup_service.py` | CleanupService — preview() + execute() with transaction safety and FAILED logging |
| `backend/app/api/v1/cleanup.py` | POST /preview, POST /execute (CONFIRM gate), GET /history |
| `backend/app/api/v1/labels.py` | 7 label endpoints + 2 display config endpoints; Redis cache TTL 300s |
| `backend/app/api/v1/themes.py` | 13 theme endpoints — resolution chain, CRUD, carrier config, user prefs |

### Frontend

| File | Purpose |
|---|---|
| `frontend/src/features/administration/database-cleanup/DatabaseCleanupPage.tsx` | Two-step cleanup page with preview table, CONFIRM gate, and history |
| `frontend/src/features/administration/database-cleanup/cleanupService.ts` | API service layer for cleanup feature |
| `frontend/src/features/administration/database-cleanup/index.ts` | Public entry point |
| `frontend/src/features/carrier-config/components/LabelsDisplayTab.tsx` | Tab 4: inline edit, bulk CSV, Preview Mode, Display Config sub-tab |
| `frontend/src/features/carrier-config/components/theme/ThemeTab.tsx` | Tab 6: system + custom theme grid, Set Default, Allow Override toggle |
| `frontend/src/features/carrier-config/components/theme/ThemeEditor.tsx` | 3-column editor: token pickers / live preview / metadata + WCAG indicator |
| `frontend/src/features/carrier-config/components/theme/ColorPickerInput.tsx` | Swatch + hex input + popover colour wheel + reset button |
| `frontend/src/features/carrier-config/components/theme/ThemePreviewPanel.tsx` | Miniaturised live preview of 6 UI sections |
| `frontend/src/features/carrier-config/components/theme/ThemeImportExport.tsx` | JSON import (preview → save) + JSON export |
| `frontend/src/components/ModeToggle.tsx` | Sun/moon nav bar toggle; hidden when allow_user_override=FALSE |
| `frontend/src/components/UserThemePicker.tsx` | Avatar dropdown theme picker with "Use Carrier Default" option |

### Tests

| File | Count |
|---|---|
| `tests-integrated/backend/unit/test_cleanup_service.py` | 12 tests |
| `tests-integrated/backend/unit/test_label_service.py` | 11 tests |
| `tests-integrated/backend/unit/test_theme_service.py` | 13 tests |
| `tests-integrated/backend/integration/test_cleanup_api.py` | 9 tests |
| `tests-integrated/backend/integration/test_labels_api.py` | 7 tests |
| `tests-integrated/backend/integration/test_theme_api.py` | 11 tests |
| `tests-integrated/frontend/unit/useLabels-dynamic.test.ts` | 7 tests |
| `tests-integrated/frontend/unit/useTheme-dynamic.test.ts` | 8 tests |
| `tests-integrated/frontend/unit/DatabaseCleanupPage.test.tsx` | 6 tests |
| `tests-integrated/frontend/unit/ColorPickerInput.test.tsx` | 5 tests |
| `tests-integrated/frontend/unit/ThemeEditor.test.tsx` | 5 tests |
| `tests-integrated/frontend/unit/ModeToggle.test.tsx` | 4 tests |
| `tests-integrated/e2e/tests/17-database-cleanup.spec.ts` | 8 specs |
| `tests-integrated/e2e/tests/18-labels-tab.spec.ts` | 9 specs |
| `tests-integrated/e2e/tests/19-theme-editor.spec.ts` | 7 specs |
| `tests-integrated/e2e/tests/20-user-theme-preference.spec.ts` | 5 specs |
| `tests-integrated/e2e/tests/21-monthly-cycle.spec.ts` | 6 specs |

---

## Modified Files

| File | Change |
|---|---|
| `backend/app/models/__init__.py` | Added 6 new Phase 6 model imports |
| `backend/app/main.py` | Registered cleanup, labels, themes routers |
| `frontend/src/hooks/useTheme.ts` | Replaced useTheme() body with dynamic Phase 6 implementation; DEFAULT_DARK_TOKENS unchanged |
| `frontend/src/hooks/useLabels.ts` | Added axios/useQuery/useTenantCarrier imports; replaced useLabels() body with dynamic Phase 6 implementation; DEFAULT_LABELS unchanged |
| `frontend/src/features/carrier-config/components/CarrierConfigHub.tsx` | Wired Tab 4 → LabelsDisplayTab, Tab 6 → ThemeTab |
| `frontend/src/App.tsx` | Added DatabaseCleanupPage import+route+nav link; added ModeToggle and UserThemePicker to nav bar |
| `frontend/src/styles/components.css` | Appended Phase 6 BEM component styles (db-cleanup, labels-tab, theme-tab, theme-card, theme-editor, color-picker-input, mode-toggle, user-theme-picker) |

---

## Key Architecture Points

- **CleanupService** uses a two-commit pattern: INSERT cleanup_run first (committed), then DELETE in transaction, then UPDATE. On failure, the second commit updates status to FAILED even after rollback.
- **CONFIRM gate** is enforced at Pydantic validator level (`field_validator`) AND in the endpoint body — defence in depth.
- **Theme resolution chain**: user_theme_prefs → carrier_theme_config → Default Dark (theme_id=1). brand_color overlay applied last, server-side.
- **Redis cache keys**: `{schema}:labels:{carrier_id}` TTL 300s; `{schema}:theme:{carrier_id}:{user_keycloak_id}` TTL 300s.
- **useTheme fallback**: `placeholderData: null` + `?? DEFAULT_DARK_TOKENS` in useEffect — never crashes, always produces 13 tokens.
- **useLabels fallback**: `placeholderData: {}` — empty dict → pure DEFAULT_LABELS; unknown API keys silently ignored.
- **WCAG check**: text_primary/surface contrast ratio computed with WCAG 2.1 formula; amber warning at <4.5:1, non-blocking.

---

## Running Tests

```bash
# Phase 1–5 regression (must stay green)
cd phase5_v1/backend
SKIP_JWT_VERIFICATION=true pytest tests/ -q
# Expected: 219 passed

# Phase 6 unit + schema integration tests
cd phase5_v1
PYTHONPATH=backend python -m pytest \
  tests-integrated/backend/unit/test_cleanup_service.py \
  tests-integrated/backend/unit/test_label_service.py \
  tests-integrated/backend/unit/test_theme_service.py \
  tests-integrated/backend/integration/test_cleanup_api.py::TestCleanupSchemas \
  tests-integrated/backend/integration/test_labels_api.py::TestLabelsApiSchema \
  tests-integrated/backend/integration/test_theme_api.py \
  --noconftest -q
# Expected: 58 passed

# Full E2E (requires docker compose up)
cd tests-integrated/e2e
BASE_URL=http://localhost:5173 npx playwright test \
  tests/17-database-cleanup.spec.ts \
  tests/18-labels-tab.spec.ts \
  tests/19-theme-editor.spec.ts \
  tests/20-user-theme-preference.spec.ts \
  tests/21-monthly-cycle.spec.ts
```

---

## DB Migration

No new migration needed — all 6 Phase 6 tables (`carrier_ui_labels`,
`carrier_display_config`, `carrier_theme_config`, `tenant_themes`,
`user_theme_prefs`, `cleanup_runs`) were already created by
`0001_initial_schema.py` in Phase 1. Phase 6 only adds ORM models and
API endpoints that use these tables.

The `carrier_ui_labels` table has a unique constraint on
`(carrier_id, screen_key, field_key)` that enables `ON CONFLICT DO UPDATE`
upserts. The `carrier_display_config` table was created without this
constraint — if you need upserts on display config, a manual migration to
add `UNIQUE (carrier_id, screen_key, field_key)` on that table is required
before the display config PUT endpoint works correctly in production.

Add this migration if needed:
```sql
ALTER TABLE {schema}.carrier_display_config
  ADD CONSTRAINT uq_display_config_{schema}
  UNIQUE (carrier_id, screen_key, field_key);
```
