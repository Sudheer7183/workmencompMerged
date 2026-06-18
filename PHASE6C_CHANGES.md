# PHASE6C_CHANGES.md — V9 S23 Strict Conformance Update

Builds on PHASE6_CHANGES.md. This update brings Section 23 into exact
V9 S23 conformance by correcting three deviations identified in the
gap analysis.

## Changes Made

### 1. `useLabels()` hook signature — V9 S23.2

**Before (Phase 6):**
```typescript
export function useLabels(): LabelMap
// Usage: const labels = useLabels(); {labels.kpi_total_book_premium}
```

**After (V9 S23.2 exact):**
```typescript
export function useLabels(screenKey: ScreenKey): (fieldKey: string, fallback: string) => string
// Usage: const label = useLabels("dashboard"); {label("kpi.book_premium", "Total Book Premium")}
```

- 41 component files updated to new call signature
- `LabelMap` interface removed; replaced by `ScreenKey` union type + nested `DEFAULT_LABELS`
- Lookup function is safe: always returns a string, never throws, never returns undefined

### 2. Redis cache key — V9 S23.1

**Before:** `{schema_name}:labels:{carrier_id}`
**After:**  `{schema_name}:labels:{carrier_id}:{screen_key}`

- One cache entry per screen per carrier (matches the spec exactly)
- Backend `GET /api/v1/labels` now accepts mandatory `screen_key` query param
- Backend queries only the rows for that screen, not all carrier labels
- Invalidation scans `{schema}:labels:{carrier_id}:*` to clear all screen slots on write

### 3. Label key naming convention — V9 S23.3

**Before (flat snake_case):** `kpi_total_book_premium`, `col_policy_number`
**After (dotted namespaced):** `kpi.book_premium`, `col.policy_number`

`DEFAULT_LABELS` is now a nested object:
```typescript
export const DEFAULT_LABELS: Record<ScreenKey, Record<string, string>> = {
  "dashboard": {
    "kpi.book_premium": "Total Book Premium",
    "kpi.est_earned": "Est. Earned Premium to Date",
    ...
  },
  "policies": {
    "col.policy_number": "Policy #",
    ...
  },
  ...
};
```

274 label entries across 16 screen namespaces, matching the V9 S23.3 catalogue.

## Files Changed

| File | Change |
|---|---|
| `frontend/src/hooks/useLabels.ts` | Complete rewrite — V9 S23.2 signature, nested DEFAULT_LABELS, per-screen query |
| `backend/app/api/v1/labels.py` | Cache key + query updated for screen_key param |
| 41 component `.tsx` files | `useLabels()` → `useLabels("screen")`, `labels.key` → `label("field.key", "fallback")` |
| `tests-integrated/frontend/unit/useLabels-dynamic.test.ts` | Updated for new structure |
| `tests-integrated/backend/unit/test_label_service.py` | Updated for per-screen cache key format |

## Regression

- All 219 Phase 1–5 tests: unchanged, all pass
- All 60 Phase 6 backend tests: all pass
- No new `labels.key` references remain in any component
- All 41 component files use `useLabels("screen")` signature
