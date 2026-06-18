/**
 * FieldMappingTab — Phase 4 (V9 S15.2 Tab 2).
 *
 * Pre-configured field-to-canonical column mappings per carrier.
 * These are used by AutoMappingService as Pass 1 (saved mapping = HIGH confidence).
 *
 * Features:
 *   - Load existing mappings for this carrier
 *   - Add new mapping row (source field → canonical column selector)
 *   - Delete individual mapping
 *   - Bulk save (PUT /api/v1/admin/field-maps/:carrierId)
 *
 * Only visible when user.role === TENANT_ADMIN.
 */

import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FieldMap {
  map_id: number;
  carrier_id: number;
  source_field: string;
  canonical_column: string;
  file_type: string | null;
  is_active: boolean;
  created_at: string;
}

// 7 transform types per V9 S15.2 Tab 2
const TRANSFORM_TYPES = ["as-is", "trim", "upper", "lower", "date-iso", "decimal", "integer"] as const;
type TransformType = typeof TRANSFORM_TYPES[number];

interface PendingMapping {
  id: string; // client-side key
  source_field: string;
  canonical_column: string;
  file_type: string;
  transform_fn: TransformType;
}

// Canonical columns that can be mapped to (full list per V9 S16.2).
const CANONICAL_COLUMNS: string[] = [
  "policy_number",
  "insured_name",
  "fein",
  "state_code",
  "effective_date",
  "expiration_date",
  "class_code",
  "wages",
  "exposure",
  "est_payroll",
  "actual_payroll_reported",
  "actual_payroll_classified",
  "est_premium_end",
  "actual_premium",
  "premium_written",
  "report_date",
  "reason_code",
  "payment_frequency",
  "expected_period_start",
  "expected_period_end",
  "days_overdue",
  "as_of_date",
];

// ---------------------------------------------------------------------------
// FieldMappingTab
// ---------------------------------------------------------------------------

interface FieldMappingTabProps {
  carrierId: number;
}

export function FieldMappingTab({ carrierId }: FieldMappingTabProps): React.JSX.Element {
  const label_calc_engine = useLabels("calc_engine");
  const label_field_mapping = useLabels("field_mapping");
  const label_shared = useLabels("shared");
  const { user } = useAuth();

  const [existingMaps, setExistingMaps] = useState<FieldMap[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Pending new mappings (not yet saved).
  const [pending, setPending] = useState<PendingMapping[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const fetchMaps = useCallback(async (): Promise<void> => {
    if (!carrierId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const res = await axios.get<FieldMap[]>(`/api/v1/admin/field-maps?carrier_id=${carrierId}`);
      setExistingMaps(res.data);
    } catch (e: unknown) {
      setLoadError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Failed to load field maps."
      );
    } finally {
      setLoading(false);
    }
  }, [carrierId]);

  useEffect(() => {
    void fetchMaps();
  }, [fetchMaps]);

  function addPendingRow(): void {
    setPending((prev) => [
      ...prev,
      {
        id: `pending-${Date.now()}`,
        source_field: "",
        canonical_column: CANONICAL_COLUMNS[0],
        file_type: "",
        transform_fn: "as-is",
      },
    ]);
    setSaveSuccess(false);
  }

  function updatePending(id: string, field: keyof PendingMapping, value: string): void {
    setPending((prev) =>
      prev.map((p) => (p.id === id ? { ...p, [field]: value } : p))
    );
  }

  function removePending(id: string): void {
    setPending((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleDeleteExisting(mapId: number): Promise<void> {
    try {
      await axios.delete(`/api/v1/admin/field-maps/${mapId}`);
      await fetchMaps();
    } catch (e: unknown) {
      alert(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Delete failed."
      );
    }
  }

  async function handleSave(): Promise<void> {
    const invalidRows = pending.filter(
      (p) => !p.source_field.trim() || !p.canonical_column
    );
    if (invalidRows.length > 0) {
      setSaveError("All rows must have a source field and canonical column.");
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const mappings = pending.map((p) => ({
      source_field: p.source_field.trim(),
      target_column: p.canonical_column,  // API uses target_column per V9 S11.9
      canonical_column: p.canonical_column,  // backward compat alias
      file_type: p.file_type.trim() || null,
      transform_fn: p.transform_fn,
    }));

    try {
      await axios.put(`/api/v1/admin/field-maps/${carrierId}`, { mappings });
      setPending([]);
      setSaveSuccess(true);
      await fetchMaps();
    } catch (e: unknown) {
      setSaveError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Save failed."
      );
    } finally {
      setSaving(false);
    }
  }

  if (user?.role !== "TENANT_ADMIN") {
    return (
      <div
        className="field-mapping-tab field-mapping-tab--no-access"
        data-testid="field-mapping-tab"
      >
        <p className="field-mapping-tab__access-note">
          {label_shared("admin_only_tab", "admin_only_tab") ?? "This tab requires Tenant Administrator access."}
        </p>
      </div>
    );
  }

  return (
    <div className="field-mapping-tab" data-testid="field-mapping-tab">
      <div className="field-mapping-tab__toolbar">
        <h2 className="field-mapping-tab__heading">
          {label_shared("field_mapping_heading", "field_mapping_heading") ?? "Pre-configured Field Mappings"}
        </h2>
        <p className="field-mapping-tab__description">
          {label_shared("field_mapping_description", "field_mapping_description") ??
            "Map source file column headers to canonical columns. These are used as Pass 1 (HIGH confidence) during auto-mapping."}
        </p>
        <button
          className="btn btn--secondary"
          onClick={addPendingRow}
          data-testid="field-mapping-tab__add-row-btn"
        >
          {label_shared("btn_add_mapping", "btn_add_mapping") ?? "+ Add Mapping"}
        </button>
      </div>

      {loadError && (
        <p className="field-mapping-tab__error" role="alert">
          {loadError}
        </p>
      )}

      {/* ── Existing mappings ──────────────────────────────────────────── */}
      <section
        className="field-mapping-tab__section"
        aria-label="Existing mappings"
      >
        <h3 className="field-mapping-tab__section-title">
          {label_shared("existing_mappings_heading", "existing_mappings_heading") ?? "Saved Mappings"}
          <span className="field-mapping-tab__count">({existingMaps.length})</span>
        </h3>

        {loading ? (
          <p className="field-mapping-tab__loading">{label_shared("loading", "Loading…") ?? "Loading…"}</p>
        ) : existingMaps.length === 0 ? (
          <p
            className="field-mapping-tab__empty"
            data-testid="field-mapping-tab__empty"
          >
            {label_shared("no_field_maps", "no_field_maps") ??
              "No pre-configured mappings yet. Add rows above and click Save & Activate."}
          </p>
        ) : (
          <table
            className="field-mapping-tab__table"
            data-testid="field-mapping-tab__existing-table"
          >
            <thead>
              <tr>
                <th>{label_field_mapping("col.source_field", "Source Field") ?? "Source Field"}</th>
                <th>{label_shared("col_canonical_column", "col_canonical_column") ?? "Canonical Column"}</th>
                <th>{label_shared("col_file_type", "col_file_type") ?? "File Type"}</th>
                <th>{label_calc_engine("col.actions", "Actions") ?? "Actions"}</th>
              </tr>
            </thead>
            <tbody>
              {existingMaps.map((m) => (
                <tr
                  key={m.map_id}
                  data-testid={`field-mapping-tab__row-${m.map_id}`}
                >
                  <td>
                    <code className="field-mapping-tab__source-field">{m.source_field}</code>
                  </td>
                  <td>
                    <code className="field-mapping-tab__canonical-col">{m.canonical_column}</code>
                  </td>
                  <td>{m.file_type ?? "—"}</td>
                  <td>
                    <button
                      className="btn btn--small btn--ghost btn--destructive"
                      onClick={() => void handleDeleteExisting(m.map_id)}
                      data-testid="field-mapping-tab__delete-btn"
                    >
                      {label_shared("btn_remove", "btn_remove") ?? "Remove"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ── Pending new mappings ─────────────────────────────────────────── */}
      {pending.length > 0 && (
        <section
          className="field-mapping-tab__section field-mapping-tab__section--pending"
          aria-label="New mappings to save"
          data-testid="field-mapping-tab__pending-section"
        >
          <h3 className="field-mapping-tab__section-title">
            {label_shared("new_mappings_heading", "new_mappings_heading") ?? "New Mappings (unsaved)"}
          </h3>

          <table className="field-mapping-tab__table" data-testid="field-mapping-tab__pending-table">
            <thead>
              <tr>
                <th>{label_field_mapping("col.source_field", "Source Field") ?? "Source Field"}</th>
                <th>{label_shared("col_canonical_column", "col_canonical_column") ?? "Canonical Column"}</th>
                <th>{label_shared("col_file_type", "col_file_type") ?? "File Type (optional)"}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pending.map((p) => (
                <tr key={p.id} data-testid={`field-mapping-tab__pending-row-${p.id}`}>
                  <td>
                    <input
                      type="text"
                      className="field-mapping-tab__input"
                      value={p.source_field}
                      onChange={(e) => updatePending(p.id, "source_field", e.target.value)}
                      placeholder="e.g. Policy Number"
                      data-testid="field-mapping-tab__source-field-input"
                    />
                  </td>
                  <td>
                    <select
                      className="field-mapping-tab__select"
                      value={p.canonical_column}
                      onChange={(e) => updatePending(p.id, "canonical_column", e.target.value)}
                      data-testid="field-mapping-tab__canonical-col-select"
                    >
                      {CANONICAL_COLUMNS.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="field-mapping-tab__select"
                      value={p.file_type}
                      onChange={(e) => updatePending(p.id, "file_type", e.target.value)}
                      data-testid="field-mapping-tab__file-type-select"
                    >
                      <option value="">All</option>
                      <option value="xlsx">XLSX</option>
                      <option value="csv">CSV</option>
                      <option value="xml">XML</option>
                    </select>
                  </td>
                  <td>
                    <select
                      className="field-mapping-tab__select"
                      value={p.transform_fn}
                      onChange={(e) => updatePending(p.id, "transform_fn", e.target.value)}
                      data-testid="field-mapping-tab__transform-select"
                    >
                      {TRANSFORM_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button
                      className="btn btn--small btn--ghost"
                      onClick={() => removePending(p.id)}
                      aria-label="Remove row"
                      data-testid="field-mapping-tab__remove-pending-btn"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {saveError && (
            <p className="field-mapping-tab__save-error" role="alert">
              {saveError}
            </p>
          )}

          <div className="field-mapping-tab__save-row">
            <button
              className="btn btn--primary"
              onClick={() => void handleSave()}
              disabled={saving}
              data-testid="field-mapping-tab__save-activate-btn"
            >
              {saving
                ? label_shared("saving", "saving") ?? "Saving…"
                : label_shared("btn_save_activate", "btn_save_activate") ?? "Save & Activate"}
            </button>
          </div>
        </section>
      )}

      {saveSuccess && (
        <p
          className="field-mapping-tab__save-success"
          role="status"
          data-testid="field-mapping-tab__save-success"
        >
          ✓ {label_shared("field_maps_saved", "field_maps_saved") ?? "Field mappings saved and activated."}
        </p>
      )}
    </div>
  );
}
