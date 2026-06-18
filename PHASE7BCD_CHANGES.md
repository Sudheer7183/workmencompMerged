# Phase 7B, 7C & 7D — Implementation Summary

## Overview

This release implements three parallel workstreams on top of the Phase 7A codebase:

- **Phase 7B** — Screen redesigns (Platform Dashboard, Tenant Detail, Org Settings, Create User Modal)
- **Phase 7C** — AI Narrative restoration + carrier-scoped LLM configuration
- **Phase 7D** — Drag-and-drop expression builder for Calc Rules

---

## Phase 7B — Screen Redesigns

### `frontend/src/hooks/useLabels.ts`
- Added new ScreenKey types: `calc_rule_builder`, `narrative_panel`, `ai_config`, `tenant_detail`, `create_user`
- Added 96 new DEFAULT_LABELS keys across all new namespaces
- No existing keys modified

### `frontend/src/features/administration/platform-admin/PlatformDashboard.tsx`
- Redesigned with four KpiCard stat cards (Tenants, Carriers, Users, TC Pairs)
- Added client-side searchable + filterable tenant table
- Status filter dropdown; search input with real-time filtering
- BEM class `platform-admin` throughout; no inline style props

### `frontend/src/features/administration/platform-admin/TenantDetail.tsx`
- Complete rewrite: two-column Identity/Carriers grid using `detail-panel__top-grid`
- Carrier list is read-only with engine ON/OFF badges
- Danger Zone rendered as `danger-zone` BEM block with red left border
- No `style={{}}` props for visual styling

### `frontend/src/features/administration/user-management/CreateUserModal.tsx`
- Two grouped sections: Personal Details + Role & Permissions
- Side-by-side First/Last name layout (`modal__name-row`)
- Role options render with description text below role name
- Field-level inline error messages on blur using `form-field__error`

### `frontend/src/styles/components.css`
- Added CSS blocks: `detail-panel`, `danger-zone`, `carrier-engine-badge`, `carrier-read-only-list`
- Added: `platform-admin`, `org-settings`, `modal__section`, `modal__role-option`
- Added: `narrative-panel`, `ai-config-tab`, `expression-builder`

---

## Phase 7C — AI Narrative + LLM Configuration

### Backend

#### `backend/alembic/versions/0012_phase7c_llm_config.py`
- Creates `{schema}.carrier_llm_config` table (tenant schema)
- Adds `narrative_text`, `narrative_provider`, `narrative_generated_at`, `narrative_is_fallback` columns to `ingestion_runs`
- Seeds placeholder rows for existing tenant carriers

#### `backend/app/models/llm_config.py`
- `CarrierLLMConfig` ORM model (new)

#### `backend/app/services/llm_key_vault_service.py`
- `LLMKeyVaultService` with Fernet encrypt/decrypt/last4
- `api_key_enc` column NEVER returned in API responses
- Module-level singleton `llm_key_vault`

#### `backend/app/services/llm_client_factory.py`
- `BaseLLMClient` abstract interface
- Six provider implementations: Anthropic, OpenAI, AzureOpenAI, Google, Ollama, OpenAICompatible
- `LLMClientFactory.create()` factory method
- Self-hosted providers (Ollama, OpenAI-compatible) work with `api_key=None`

#### `backend/app/services/ai_narrative_service.py`
- Updated resolution chain: carrier config → platform Anthropic key → template fallback
- **`carriers.ai_narrative_enabled` is no longer referenced** (Phase 7C rule 12)
- Returns `NarrativeResult` dataclass with metadata

#### `backend/app/api/v1/carrier_config.py` (appended)
- `GET /api/v1/admin/llm-config` — returns current config (no api_key in response)
- `POST /api/v1/admin/llm-config` — upsert config (encrypts key server-side)
- `PUT /api/v1/admin/llm-config/{id}` — update (api_key omit = retain existing)
- `DELETE /api/v1/admin/llm-config/{id}` — soft-delete (is_active=FALSE)
- `POST /api/v1/admin/llm-config/test` — test connection
- `GET /api/v1/admin/calc-rules/available-fields` — Phase 7D field descriptors

#### `backend/app/core/config.py`
- Added `LLM_KEY_ENCRYPTION_SECRET: str = ""` setting

#### `backend/pyproject.toml`
- Added `openai>=1.0.0`, `google-generativeai>=0.8.0`, `cryptography>=44.0.0`

#### `backend/app/services/tenant_provisioning_service.py`
- `add_carrier_to_tenant()` now seeds a placeholder `carrier_llm_config` row

### Frontend

#### `frontend/src/features/policies/components/NarrativePanel.tsx` (new)
- Five display states: loading, fallback (amber notice), engine_not_run, not_attempted, normal
- Collapse/expand toggle; copy-to-clipboard button
- Provider badge displayed when provider is known
- BEM: `narrative-panel`, `narrative-panel__notice--amber`, `narrative-panel__provider-badge`

#### `frontend/src/features/carrier-config/components/AIConfigTab.tsx` (new)
- Tab 7 of CarrierConfigHub
- `PROVIDER_OPTIONS` constant with all 6 providers and model lists
- api_key field is type=password; shows `api_key_last4` after save
- Test Connection button returns latency and error
- No `style={{}}` props

#### `frontend/src/features/carrier-config/components/CarrierConfigHub.tsx`
- Added Tab 7: AI Configuration → `AIConfigTab`

---

## Phase 7D — Drag-and-Drop Expression Builder

### Backend

#### `backend/app/rules/field_descriptors.py` (new)
- `FieldDescriptor` Pydantic model
- `FIELD_DESCRIPTORS` list: one entry per SAFE_NAMES user-facing key (18 entries)
- `get_all_descriptors()` returns sorted by category then name

### Frontend

#### `frontend/src/utils/expressionTokenizer.ts` (new)
- `tokenize(expression, knownFields)` → `ExpressionToken[]`
- `detokenize(tokens)` → raw expression string (round-trip safe)
- `hasUnknownTokens(tokens)` → shows complexity notice
- `isComplexExpression(expression)` → detects function calls

#### `frontend/src/features/carrier-config/components/ExpressionBuilder.tsx` (new)
- Left panel: draggable field pills, grouped by category, searchable
- Canvas: `@dnd-kit/sortable` horizontal sortable tokens
- Drop zone accepts fields dragged from left panel
- Operator buttons append to canvas
- Raw expression read-only display kept in sync
- Toggle to switch between builder / raw textarea
- Complex expression notice when `hasUnknownTokens` is true
- BEM: `expression-builder__*`

#### `frontend/src/features/carrier-config/components/CalcRulesList.tsx`
- Imports `ExpressionBuilder` and `FieldDescriptor`
- Fetches `GET /api/v1/admin/calc-rules/available-fields` on mount
- New `builderMode` state (default: "builder")
- `ExpressionBuilder` renders instead of textarea when in builder mode
- Raw textarea shown only when `builderMode === "raw"`
- AI suggest re-enters builder mode to show suggestion visually

#### `frontend/package.json`
- Added `@dnd-kit/core: ^6.0.0`, `@dnd-kit/sortable: ^8.0.0`, `@dnd-kit/utilities: ^3.0.0`

---

## Test Package

Location: `tests-integrated-phase7bcd/`

| File | Coverage |
|---|---|
| `backend/unit/test_llm_key_vault_service.py` | encrypt/decrypt/last4/no-key edge cases |
| `backend/unit/test_llm_client_factory.py` | all 6 providers, invalid provider, missing params |
| `backend/unit/test_field_descriptors.py` | SAFE_NAMES cross-check, required fields |
| `backend/integration/test_llm_config_api.py` | CRUD cycle, api_key never returned, soft-delete |
| `frontend/unit/expressionTokenizer.test.ts` | tokenize, detokenize, round-trip, unknown tokens |
| `e2e/23-ai-narrative-display.spec.ts` | NarrativePanel render, toggle, no inline styles |
| `e2e/24-llm-config.spec.ts` | AI Config Tab, provider/model select, api_key type=password |
| `e2e/25-field-builder.spec.ts` | Builder render, mode toggle, complex notice, operator buttons |

---

## Migration Checklist

1. Run `alembic upgrade head` to apply migration `0012_phase7c_llm_config`
2. Set `LLM_KEY_ENCRYPTION_SECRET` environment variable (generate with Fernet)
3. Run `npm install` in `frontend/` to install `@dnd-kit` packages
4. Verify label seeding picks up all 96 new DEFAULT_LABELS keys (seeded dynamically at carrier creation)

## Standing Rules Compliance

- ✅ No "AuditAI" / "SmartPay" references
- ✅ No hardcoded hex colours in components
- ✅ No `style={{}}` props for visual styling
- ✅ All user-visible strings through `useLabels()`
- ✅ No raw `fetch()` — all API calls via axios
- ✅ `carriers.ai_narrative_enabled` NOT referenced in AInarrativeService
- ✅ `api_key` / `api_key_enc` structurally absent from all response schemas
- ✅ Self-hosted providers (`api_key=None`) handled gracefully
- ✅ BEM throughout, no deeply nested selectors
- ✅ No LangChain / LangGraph
