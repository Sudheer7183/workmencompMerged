# Post-Phase 7BCD — Bug Fixes & Feature Completions

All fixes are additive and surgical. Nothing previously working has been
reorganised or broken. Fixes are independent of one another.

---

## Issue 1 — Dashboard Pie Chart Click-Through Filters Not Applied

**File:** `frontend/src/features/policies/PoliciesListPage.tsx`

**Root cause:** `useState` initialisers run only on first mount. When
`/policies` was already mounted and React Router navigated to it again
(with new `location.state`), the filter state was not updated.

**Fix:** Replaced the three `useState(initialFilters.xxx ?? "")` initialisers
with `useState("")` (always empty on first mount) plus a `useEffect` that
watches `location.state` and resets all three filters + resets page to 1
on every navigation event, including re-navigations to an already-mounted component.

---

## Issue 2 — Dashboard Bar Chart Click Does Nothing

**File:** `frontend/src/components/charts/Charts.tsx`

**Root cause:** The Recharts `Bar` `onClick` callback signature is
`(barData, index, event)` — the first argument is the row data object
containing `{ name, High, Medium, Low }`. The previous code passed the
third argument (the mouse event) as the payload, so `payload.activeLabel`
was always undefined and no navigation fired.

**Fix:** Updated `handleBarClick` to accept `barData: Record<string, unknown>`
as its first argument and extract `barData.name` (the state code). All three
`<Bar>` `onClick` handlers now pass `barData` correctly as the first argument.
Added `stacked-bar-chart__segment--clickable` CSS class (defined in
`components.css`) to bar segments that have an `onBarClick` handler —
no `cursor` inline style used.

---

## Issue 3 — "Policies Above Variance Threshold" Widget Always Shows Zero

**Files:**
- `backend/app/api/v1/dashboard.py`

**Root cause:** The threshold was hardcoded at `0.30` and the query used
`variance_amount / est_premium_end` instead of the engine-computed
`variance_pct` column.

**Fix:**
1. Before the target variance query in `_build_summary()`, the configured
   threshold is now read from `carrier_calc_rules` where
   `rule_key = 'risk_threshold_target'` (falls back to 30.0 if not configured).
2. The WHERE clause now uses a `CASE` expression that prefers `pv.variance_pct`
   when non-NULL, falls back to `pv.variance_amount / pv.est_premium_end`.
3. The configured `threshold_pct` is now returned in the `TargetVarianceMetrics`
   response so the frontend displays the correct threshold label.
4. `_cache_key()` now includes `threshold_pct` as a suffix so changing the
   carrier's threshold automatically invalidates the cached dashboard payload.
   A pre-flight query in the endpoint reads the threshold before the cache
   check to construct the correct scoped key.

---

## Issue 4 — Policy List State Filter Not Working

**File:** `backend/app/api/v1/policies.py`

**Root cause:** The `GET /api/v1/policies` endpoint only declared
`status_filter` and `risk_filter` as `Query(...)` parameters. The `state`
query param was silently ignored.

**Fix:** Added `state_filter: str | None = Query(None, alias="state")` to
`list_policies()`. When present, appends `p.state_code = :state` to the
WHERE clause (parameterised). Applied to both the `COUNT(*)` query and the
rows query via the shared `where_clause` / `params` variables.

---

## Issue 5 — AI Narrative Missing from Individual Policy Audit PDF

**Files:**
- `backend/app/services/report_generation_service.py`
- `backend/app/templates/reports/policy_audit.html`

**Root cause:** `"narrative": None` was hardcoded in the PDF context dict.

**Fix:**
- Added a query in `generate_policy_audit()` that joins `ingestion_runs`
  to `premium_variance` (via `ingestion_run_id`) to find the most recent
  completed run for this policy that has a non-NULL `narrative_text`.
  (`ingestion_runs` has no `policy_id` FK — the join via `premium_variance`
  is the correct access path.)
- Both `narrative_text` and `narrative_is_fallback` are passed into the
  PDF template context.
- Updated `policy_audit.html` to render a `⚠ template-generated` warning
  paragraph (amber, 8pt) before the narrative body when
  `narrative_is_fallback` is true.

---

## Issue 6 — Organization Settings Form Enhancements

**Files:**
- `frontend/src/features/administration/organization/ProfileTab.tsx`
- `frontend/src/features/administration/organization/ContactsTab.tsx`
- `frontend/src/features/administration/organization/BrandingTab.tsx`
- `frontend/src/styles/components.css`

**Changes (UX only — no API, model, or field-name changes):**

**ProfileTab:**
- `maxLength={100}` added to the `display_name` input.
- `<p className="org-settings__char-counter">` character counter
  (`{length}/100`) rendered below the input with `aria-live="polite"`.

**ContactsTab:**
- `ContactFields` component: `fieldset` uses `org-settings__field-group`
  card styling; `legend` uses `org-settings__field-group-label`.
- New `showEmailHelper?: boolean` prop — when `true` (Primary contact only),
  renders helper text below the email field via `org-settings__field-helper`.
- `type="email"` and `type="tel"` already present; confirmed correct.

**BrandingTab:**
- Logo section subtitle updated to show the full accepted-formats helper
  ("Accepted formats: PNG, JPG, SVG. Max size: 2MB…").
- Colour swatch element changed from `className="branding-tab__color-swatch"`
  to `className="org-settings__color-swatch"` (BEM-consistent) with the
  background colour driven by `--org-swatch-color` CSS custom property
  (set via `style={{ "--org-swatch-color": "#xxxxxx" }}`), not a direct
  `backgroundColor` inline style.

**components.css additions:**
- `.org-settings__char-counter` — right-aligned muted xs text.
- `.org-settings__field-helper` — muted xs helper text.
- `.org-settings__color-swatch` — 24×24px swatch using `--org-swatch-color`.
- `.org-settings__field-group` / `.org-settings__field-group-label` —
  bordered card for contact fieldset groups.
- `.stacked-bar-chart__segment--clickable` — CSS cursor: pointer class.
- `.expression-builder__fields-loading` / `__fields-skeleton` / `__fields-empty`
  — loading and empty states for the expression builder field panel.

---

## Issue 7 — Calc Engine Expression Builder: Available Fields Empty

**Files:**
- `frontend/src/features/carrier-config/components/ExpressionBuilder.tsx`
- `frontend/src/features/carrier-config/components/CalcRulesList.tsx`
- `frontend/src/styles/components.css` (shared with Issue 6 above)

**Root cause (confirmed already fixed in Phase 7D):**
The `SortableContext` collision and `useDraggable` / `useSortable` architectural
fix were already correctly applied in the uploaded codebase. The
`available-fields` route path (`/api/v1/admin/calc-rules/available-fields`)
is consistent with all other routes on the `carrier_config` router (which is
mounted without a prefix in `main.py`) and resolves correctly.

**Remaining fixes applied:**
1. `CalcRulesList`: `isLoading` extracted from the `available-fields`
   `useQuery` as `isFieldsLoading` and passed to `<ExpressionBuilder>`.
   Added a comment clarifying the `enabled: carrierId > 0` condition runs
   eagerly on mount (not deferred until a rule is opened).
2. `ExpressionBuilder`: New `isFieldsLoading?: boolean` prop. Field panel
   now renders a three-row skeleton (`expression-builder__fields-skeleton`)
   while loading, and `expression-builder__fields-empty` (not the canvas
   hint class) with label key `no_fields_available` when the API returns
   an empty list.
