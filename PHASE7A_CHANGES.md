# Phase 7A — Carrier Decoupling Changes

**Status:** Complete  
**Risk Level:** HIGH (architectural change)  
**Completion Gate:** All existing Phase 1–6 tests pass + new Phase 7A tests pass

---

## Summary

Phase 7A removes the mandatory "minimum one carrier" gate from the tenant
provisioning wizard. Carrier assignment is now an optional post-provisioning
step performed by TENANT_ADMIN from their Administration panel.

---

## Backend Changes

### `backend/app/services/tenant_provisioning_service.py`

**Changed:**
- `provision_tenant()` now accepts `carrier_ids: list[int]` with an empty default
  instead of requiring at least one carrier. The parameter is retained for
  backward-compatibility (existing callers that pass carrier IDs still work).
- `_seed_tenant_schema()` no longer loops over carrier IDs. It only seeds
  `tenant_calc_config`. Carrier seeding moved to `add_carrier_to_tenant()`.

**New method:**
- `add_carrier_to_tenant(*, schema_name, carrier_id, db)` — extracted from the
  old provisioning loop. This is the single authoritative implementation of
  carrier seeding. It is:
  - **Idempotent**: re-calling for an existing active carrier is a no-op.
  - **Re-activating**: calling for a soft-deleted carrier sets is_active=TRUE.
  - **Non-destructive**: all inserts use ON CONFLICT DO NOTHING — existing
    rule edits and theme configs are preserved.

### `backend/app/api/v1/tenant_admin.py`

**New endpoints (TENANT_ADMIN role required):**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tenant/carriers/available` | Lists platform carriers not yet assigned to this tenant |
| `POST` | `/api/v1/tenant/carriers` | Adds a carrier; calls `add_carrier_to_tenant()` |
| `DELETE` | `/api/v1/tenant/carriers/{carrier_id}` | Soft-removes (is_active=FALSE); data preserved |

### `backend/alembic/versions/0012_phase7a_carrier_decoupling.py`

No-op migration placeholder documenting the Phase 7A boundary. No schema
changes were required — the schema already supported zero-carrier tenants.

---

## Frontend Changes

### `src/features/administration/platform-admin/TenantCreationWizard/Step3CarrierAssign.tsx`

- Renamed step title to "Carrier Assignment (Optional)"
- Removed minimum-1 validation
- "Next" button is always enabled regardless of carrier selection
- Shows informational banner when zero carriers are selected
- Shows hint explaining that carriers can be added post-activation

### `src/features/administration/platform-admin/TenantCreationWizard/Step4ReviewActivate.tsx`

- "Activate" button is always enabled (was previously blocked by zero carriers)
- Zero-carrier state shows informational note instead of blocking message

### `src/features/administration/organization/CarrierManagementPanel.tsx` *(NEW)*

Full carrier management panel for TENANT_ADMIN. Features:
- **Assigned Carriers** table with per-row Remove (inline confirm) action
- **Add a Carrier** section with select dropdown + Add button
- Calls `GET /api/v1/tenant/carriers/available` for the add dropdown
- Calls `POST /api/v1/tenant/carriers` to add
- Calls `DELETE /api/v1/tenant/carriers/{id}` to remove
- Invalidates TenantCarrierContext cache on add/remove so hub updates live

### `src/features/administration/organization/OrganizationSettings.tsx`

- Added "Carriers" tab (visible to TENANT_ADMIN role only)
- Tab renders `CarrierManagementPanel`

### `src/hooks/useLabels.ts`

New label keys added (existing keys untouched):

**`org_settings` namespace — new keys:**
- `tab.carriers`, `carriers.assigned_title`, `carriers.add_title`
- `carriers.btn.add`, `carriers.btn.adding`, `carriers.btn.remove`
- `carriers.btn.confirm`, `carriers.btn.cancel`, `carriers.confirm_remove`
- `carriers.col.name`, `carriers.col.slug`, `carriers.col.actions`
- `carriers.none_assigned`, `carriers.all_assigned`
- `carriers.select_label`, `carriers.select_placeholder`
- `carriers.add_hint`

**`platform_admin` namespace — new keys:**
- `step3.title` (value changed to include "(Optional)")
- `step3.optional_hint`, `step3.zero_carriers_notice`
- `step4.no_carriers_note`, `step4.section.*`, `step4.title`
- `btn.activating`

### `src/styles/components.css`

New BEM blocks added (no existing classes modified):
- `.carrier-mgmt` — panel container
- `.carrier-mgmt__section`, `__section-title`, `__table`, `__row`, `__cell`
- `.carrier-mgmt__confirm`, `__confirm-text`
- `.carrier-mgmt__add-form`, `__add-row`, `__add-label`, `__select`
- `.carrier-mgmt__error`, `__loading`, `__empty`, `__all-assigned`, `__add-hint`
- `.wizard-step__hint`, `__info-banner`, `__info-icon`, `__loading`, `__empty`
- `.wizard-review`, `__section`, `__section-title`, `__dl`, `__no-carriers`
- `.wizard-review__carrier-list`, `__carrier-item`
- `.btn--danger` (utility)

All token values use `var(--token)` — no hardcoded hex.

---

## What Did NOT Change

- All existing Phase 1–6 endpoints and their response shapes
- `verify_carrier_scope()` in audit_calculation_service.py — unchanged
- Carrier Configuration Hub (6-tab hub) — continues to work for all assigned carriers
- All ingestion, calculation, and reporting — carrier-scoped queries unaffected
- Tenants provisioned during Phase 1–6 with carriers already assigned — fully preserved
- `DEFAULT_DARK_TOKENS` — no changes
- No existing `DEFAULT_LABELS` key values modified

---

## Backward Compatibility

- `TenantCreateRequest.carrier_ids` field is retained as optional (default=[])
- Existing tests that pass `carrier_ids=[1,2,3]` continue to work unchanged
- The provisioning path for carrier_ids still calls `add_carrier_to_tenant()` per carrier
- All existing `GET /api/v1/tenant/carriers` reads are unchanged

---

## Test Coverage (Phase 7A)

| File | Cases | Type |
|------|-------|------|
| `tests/integration/test_tenant_carrier_management.py` | 12 | Backend unit + integration |
| `tests-integrated/frontend/unit/CarrierManagementPanel.test.tsx` | 12 | Frontend component |
| `tests-integrated/e2e/tests/22-tenant-carrier-management.spec.ts` | 10 | Playwright E2E |
