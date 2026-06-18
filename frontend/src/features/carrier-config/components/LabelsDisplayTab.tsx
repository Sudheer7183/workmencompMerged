/**
 * LabelsDisplayTab — CarrierConfigHub Tab 4.
 *
 * Two sub-tabs per V9 S23 and S26:
 *   A — Labels: inline edit, bulk CSV import/export, Preview Mode
 *   B — Display Config: column visibility + ordering
 *
 * Phase 6. TENANT_ADMIN only.
 *
 * Fixes applied:
 *  1. buildLabelRows() referenced `overrideMap` which was never defined.
 *     Fixed by building the Map inside the function before using it.
 *
 *  2. LabelsSubTab JSX used `overridesFlat` in <LabelPreviewPanel> but the
 *     variable was never defined inside LabelsSubTab.
 *     Fixed by deriving overridesFlat from the `overrides` query data.
 *
 *  3. LabelRowEdit key={row.field_key} — field_key is not unique across screens
 *     (e.g. "title" exists on both dashboard and policies screens).
 *     Fixed to key={`${row.screen_key}|${row.field_key}`}.
 */

import React, { useState, useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { DEFAULT_LABELS, type ScreenKey } from "@/hooks/useLabels";

type SubTab = "label" | "display";

// ─── Types ────────────────────────────────────────────────────────────────────

interface LabelRow {
  label_id: number;
  carrier_id: number;
  screen_key: string;
  field_key: string;
  label_text: string;
}

interface ConditionalFormatRule {
  /** Field to evaluate (e.g. "variance_pct") */
  field: string;
  /** Operator: gt | lt | eq | gte | lte */
  operator: "gt" | "lt" | "eq" | "gte" | "lte";
  /** Threshold value */
  value: number;
  /** CSS colour to apply (CSS variable reference e.g. "var(--color-red)") */
  color: string;
}

interface DisplayConfigRow {
  config_id?: number;
  carrier_id: number;
  screen_key: string;
  field_key: string;
  is_visible: boolean;
  display_order: number | null;
  conditional_format_rule: ConditionalFormatRule | null;
}

// ─── API helpers ──────────────────────────────────────────────────────────────

async function fetchLabelOverrides(carrierId: number): Promise<LabelRow[]> {
  const { data } = await axios.get<LabelRow[]>(
    `/api/v1/admin/ui-labels/${carrierId}`
  );
  return data;
}

async function saveLabelOverride(
  carrierId: number,
  item: { screen_key: string; field_key: string; label_text: string }
): Promise<LabelRow[]> {
  const { data } = await axios.put<LabelRow[]>(
    `/api/v1/admin/ui-labels/${carrierId}`,
    { labels: [item] }
  );
  return data;
}

async function deleteLabelOverride(carrierId: number, labelId: number): Promise<void> {
  await axios.delete(`/api/v1/admin/ui-labels/${carrierId}/${labelId}`);
}

async function fetchDisplayConfig(carrierId: number): Promise<DisplayConfigRow[]> {
  const { data } = await axios.get<DisplayConfigRow[]>(
    `/api/v1/admin/display-config/${carrierId}`
  );
  return data;
}

async function saveDisplayConfig(
  carrierId: number,
  configs: Array<{
    screen_key: string;
    field_key: string;
    is_visible: boolean;
    display_order: number | null;
  }>
): Promise<DisplayConfigRow[]> {
  const { data } = await axios.put<DisplayConfigRow[]>(
    `/api/v1/admin/display-config/${carrierId}`,
    { configs }
  );
  return data;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

type LabelTableRow = {
  screen_key: string;
  field_key: string;
  default_text: string;
  override: LabelRow | null;
};

/**
 * Builds the full label table from DEFAULT_LABELS merged with DB overrides.
 *
 * FIX: `overrideMap` was referenced but never constructed. It is now built
 * inside this function from the `overrides` argument before use.
 */
function buildLabelRows(overrides: LabelRow[]): LabelTableRow[] {
  // FIX: build the Map here — it was missing entirely in the original
  const overrideMap = new Map<string, LabelRow>();
  for (const override of overrides) {
    overrideMap.set(`${override.screen_key}|${override.field_key}`, override);
  }

  const rows: LabelTableRow[] = [];

  for (const [screenKey, fieldMap] of Object.entries(DEFAULT_LABELS)) {
    for (const [fieldKey, defaultText] of Object.entries(
      fieldMap as Record<string, string>
    )) {
      const mapKey = `${screenKey}|${fieldKey}`;
      rows.push({
        screen_key: screenKey,
        field_key: fieldKey,
        default_text: defaultText,
        override: overrideMap.get(mapKey) ?? null,
      });
    }
  }
  return rows;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface LabelRowEditProps {
  row: LabelTableRow;
  carrierId: number;
  onSaved: () => void;
}

function LabelRowEdit({ row, carrierId, onSaved }: LabelRowEditProps): React.JSX.Element {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(
    row.override?.label_text ?? row.default_text
  );

  const saveMutation = useMutation({
    mutationFn: () =>
      saveLabelOverride(carrierId, {
        screen_key: row.screen_key,
        field_key: row.field_key,
        label_text: draftText,
      }),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["admin-label", carrierId] });
      void queryClient.invalidateQueries({ queryKey: ["label", carrierId] });
      onSaved();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteLabelOverride(carrierId, row.override!.label_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-label", carrierId] });
      void queryClient.invalidateQueries({ queryKey: ["label", carrierId] });
      onSaved();
    },
  });

  const currentText = row.override?.label_text ?? row.default_text;
  const hasOverride = row.override !== null;

  return (
    <tr className="label-tab__row">
      <td className="label-tab__td">
        <span className="label-tab__screen-badge">{row.screen_key}</span>
      </td>
      <td className="label-tab__td">
        <code style={{ fontSize: "0.8em", color: "var(--text-muted)" }}>
          {row.field_key}
        </code>
      </td>
      <td className="label-tab__td" style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
        {row.default_text}
      </td>
      <td className="label-tab__td">
        {editing ? (
          <div className="label-tab__inline-edit">
            <input
              type="text"
              className="label-tab__inline-input"
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveMutation.mutate();
                if (e.key === "Escape") setEditing(false);
              }}
              autoFocus
            />
            <button
              type="button"
              className="label-tab__icon-btn label-tab__icon-btn--save"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
              title="Save"
            >
              ✓
            </button>
            <button
              type="button"
              className="label-tab__icon-btn"
              onClick={() => setEditing(false)}
              title="Cancel"
            >
              ✕
            </button>
          </div>
        ) : (
          <span style={{ fontSize: "var(--text-sm)" }}>
            {hasOverride ? (
              currentText
            ) : (
              <span className="label-tab__default-badge">default</span>
            )}
          </span>
        )}
      </td>
      <td className="label-tab__td">
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <button
            type="button"
            className="label-tab__icon-btn"
            onClick={() => {
              setDraftText(currentText);
              setEditing(true);
            }}
            title="Edit"
          >
            ✎
          </button>
          {hasOverride && (
            <button
              type="button"
              className="label-tab__icon-btn label-tab__icon-btn--delete"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              title="Reset to default"
            >
              ↺
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

interface LabelPreviewPanelProps {
  /** Flat map of "screen_key.field_key" -> overridden text, for display in preview. */
  overridesFlat: Record<string, string>;
}

function LabelPreviewPanel({ overridesFlat }: LabelPreviewPanelProps): React.JSX.Element {
  function resolve(screen: ScreenKey, field: string, fallback: string): string {
    const overrideKey = `${screen}.${field}`;
    if (overridesFlat[overrideKey]) return overridesFlat[overrideKey];
    const screenDefaults = DEFAULT_LABELS[screen] as Record<string, string> | undefined;
    return screenDefaults?.[field] ?? fallback;
  }

  return (
    <div className="label-tab__preview-panel">
      <p className="label-tab__preview-title">Label Preview</p>
      <div className="label-tab__preview-row">
        <div className="label-tab__preview-col">
          <p className="label-tab__preview-header">{resolve("dashboard", "title", "Dashboard")}</p>
          {[
            resolve("dashboard", "kpi.book_premium", "Total Book Premium"),
            resolve("dashboard", "kpi.est_earned", "Est. Earned Premium"),
            resolve("dashboard", "kpi.actual_earned", "Actual Earned Premium"),
            resolve("dashboard", "kpi.variance", "Total Variance"),
          ].map((l) => (
            <p key={l} className="label-tab__preview-item">{l}</p>
          ))}
        </div>
        <div className="label-tab__preview-col">
          <p className="label-tab__preview-header">{resolve("policies", "title", "Policies")}</p>
          {[
            resolve("policies", "col.policy_number", "Policy #"),
            resolve("policies", "col.insured_name", "Insured"),
            resolve("policies", "col.state", "State"),
            resolve("policies", "col.est_premium", "Est. Premium"),
            resolve("policies", "col.variance_pct", "Variance %"),
          ].map((l) => (
            <p key={l} className="label-tab__preview-item">{l}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Labels sub-tab ───────────────────────────────────────────────────────────

interface LabelsSubTabProps {
  carrierId: number;
}

function LabelsSubTab({ carrierId }: LabelsSubTabProps): React.JSX.Element {
  const [searchQuery, setSearchQuery] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const { data: overrides = [], isLoading } = useQuery({
    queryKey: ["admin-label", carrierId],
    queryFn: () => fetchLabelOverrides(carrierId),
    staleTime: 60_000,
  });

  const allRows = buildLabelRows(overrides);

  const filteredRows = allRows.filter(
    (r) =>
      searchQuery === "" ||
      r.field_key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.screen_key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.default_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.override?.label_text ?? "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  // FIX: overridesFlat was used in JSX but never defined in this scope.
  // Derived from the query data by flattening "screen_key.field_key" → label_text.
  const overridesFlat: Record<string, string> = {};
  for (const o of overrides) {
    overridesFlat[`${o.screen_key}.${o.field_key}`] = o.label_text;
  }

  const handleExport = async (): Promise<void> => {
    try {
      const response = await axios.post(
        `/api/v1/admin/ui-labels/${carrierId}/export-csv`,
        {},
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(new Blob([response.data as BlobPart]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `labels_carrier_${carrierId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently handle
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      await axios.post(`/api/v1/admin/ui-labels/${carrierId}/import-csv`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      window.location.reload();
    } catch {
      // silently handle
    }
    e.target.value = "";
  };

  // Group filtered rows by screen_key
  const rowsBySection = useMemo<Map<string, LabelTableRow[]>>(() => {
    const map = new Map<string, LabelTableRow[]>();
    for (const row of filteredRows) {
      const key = row.screen_key;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(row);
    }
    return map;
  }, [filteredRows]);

  // Auto-expand sections that have matches when searching
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const toggleSection = (sectionKey: string): void => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionKey)) {
        next.delete(sectionKey);
      } else {
        next.add(sectionKey);
      }
      return next;
    });
  };

  const isSectionOpen = (key: string): boolean =>
    searchQuery.length > 0 || expandedSections.has(key);

  if (isLoading) {
    return <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>Loading labels…</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {/* Toolbar */}
      <div className="label-tab__toolbar">
        <input
          type="text"
          className="label-tab__search"
          placeholder="Search by key or text…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <button
          type="button"
          className="label-tab__btn"
          onClick={() => void handleExport()}
          title="Export all labels as CSV"
        >
          Export CSV
        </button>
        <button
          type="button"
          className="label-tab__btn"
          onClick={() => fileInputRef.current?.click()}
          title="Import labels from CSV"
        >
          Import CSV
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={(e) => void handleImport(e)}
        />
        <button
          type="button"
          className={`label-tab__btn ${showPreview ? "label-tab__preview-toggle--active" : ""}`}
          onClick={() => setShowPreview((v) => !v)}
        >
          {showPreview ? "Hide Preview" : "Preview Mode"}
        </button>
      </div>

      {/* Preview panel */}
      {showPreview && <LabelPreviewPanel overridesFlat={overridesFlat} />}

      {/* Collapsible sections by screen_key */}
      {rowsBySection.size === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          No labels match your search.
        </p>
      ) : (
        Array.from(rowsBySection.entries()).map(([sectionKey, rows]) => {
          const open = isSectionOpen(sectionKey);
          return (
            <div key={sectionKey} className="labels-section">
              <button
                type="button"
                className="labels-section__header"
                onClick={() => toggleSection(sectionKey)}
                aria-expanded={open}
              >
                <span className={`labels-section__chevron ${open ? "labels-section__chevron--open" : ""}`}>
                  ▶
                </span>
                <span className="labels-section__name">{sectionKey}</span>
                <span className="labels-section__count">{rows.length}</span>
              </button>
              <div className={`labels-section__body ${open ? "labels-section__body--open" : ""}`}>
                {rows.map((row) => (
                  <div key={`${row.screen_key}|${row.field_key}`} className="labels-section__row">
                    <span className="labels-section__key">{row.field_key}</span>
                    <LabelRowEdit
                      row={row}
                      carrierId={carrierId}
                      onSaved={() => {}}
                    />
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ─── Display Config sub-tab ───────────────────────────────────────────────────

interface DisplayConfigSubTabProps {
  carrierId: number;
}

function DisplayConfigSubTab({ carrierId }: DisplayConfigSubTabProps): React.JSX.Element {
  const queryClient = useQueryClient();
  const [localConfigs, setLocalConfigs] = useState<DisplayConfigRow[] | null>(null);

  const { data: serverConfigs = [], isLoading } = useQuery({
    queryKey: ["display-config", carrierId],
    queryFn: () => fetchDisplayConfig(carrierId),
    staleTime: 60_000,
  });

  const configs = localConfigs ?? serverConfigs;

  const saveMutation = useMutation({
    mutationFn: () =>
      saveDisplayConfig(
        carrierId,
        configs.map((c) => ({
          screen_key: c.screen_key,
          field_key: c.field_key,
          is_visible: c.is_visible,
          display_order: c.display_order,
          conditional_format_rule: c.conditional_format_rule ?? null,
        }))
      ),
    onSuccess: (saved) => {
      setLocalConfigs(null);
      queryClient.setQueryData(["display-config", carrierId], saved);
    },
  });

  const updateConfig = useCallback(
    (idx: number, patch: Partial<DisplayConfigRow>) => {
      setLocalConfigs((prev) => {
        const base = prev ?? serverConfigs;
        return base.map((c, i) => (i === idx ? { ...c, ...patch } : c));
      });
    },
    [serverConfigs]
  );

  if (isLoading) {
    return (
      <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
        Loading display config…
      </p>
    );
  }

  if (configs.length === 0) {
    return (
      <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
        No display config entries. Column visibility settings will appear here once configured.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ overflowX: "auto" }}>
        <table className="display-config__table">
          <thead>
            <tr>
              <th className="display-config__th">Screen</th>
              <th className="display-config__th">Column</th>
              <th className="display-config__th">Visible</th>
              <th className="display-config__th">Order</th>
              <th className="display-config__th">Conditional Format</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((row, idx) => (
              <tr key={`${row.screen_key}-${row.field_key}`}>
                <td className="display-config__td">
                  <span className="label-tab__screen-badge">{row.screen_key}</span>
                </td>
                <td className="display-config__td" style={{ fontSize: "var(--text-sm)" }}>
                  {row.field_key}
                </td>
                <td className="display-config__td">
                  <input
                    type="checkbox"
                    className="display-config__toggle"
                    checked={row.is_visible}
                    onChange={(e) => updateConfig(idx, { is_visible: e.target.checked })}
                    aria-label={`Toggle visibility of ${row.field_key}`}
                  />
                </td>
                <td className="display-config__td">
                  <input
                    type="number"
                    className="display-config__order-input"
                    value={row.display_order ?? ""}
                    min={1}
                    onChange={(e) =>
                      updateConfig(idx, {
                        display_order: e.target.value
                          ? parseInt(e.target.value, 10)
                          : null,
                      })
                    }
                  />
                </td>
                <td className="display-config__td">
                  <input
                    type="text"
                    className="display-config__order-input"
                    style={{
                      width: "180px",
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: "0.7rem",
                    }}
                    placeholder='{"field":"variance_pct","operator":"gt","value":30,"color":"var(--color-red)"}'
                    value={
                      row.conditional_format_rule
                        ? JSON.stringify(row.conditional_format_rule)
                        : ""
                    }
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      try {
                        const parsed = raw
                          ? (JSON.parse(raw) as ConditionalFormatRule)
                          : null;
                        updateConfig(idx, { conditional_format_rule: parsed });
                      } catch {
                        // Invalid JSON — leave unchanged until user fixes it
                      }
                    }}
                    aria-label={`Conditional format rule for ${row.field_key}`}
                    title="JSON: {field, operator (gt|lt|eq|gte|lte), value, color}"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          className="label-tab__btn label-tab__btn--primary"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || localConfigs === null}
        >
          {saveMutation.isPending ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface LabelsDisplayTabProps {
  carrierId: number;
}

export function LabelsDisplayTab({ carrierId }: LabelsDisplayTabProps): React.JSX.Element {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("label");

  return (
    <div className="label-tab">
      <nav className="label-tab__sub-nav" role="tablist" aria-label="Label config sections">
        {(["label", "display"] as SubTab[]).map((key) => (
          <button
            key={key}
            role="tab"
            type="button"
            className={`label-tab__sub-btn ${
              activeSubTab === key ? "label-tab__sub-btn--active" : ""
            }`}
            aria-selected={activeSubTab === key}
            onClick={() => setActiveSubTab(key)}
          >
            {key === "label" ? "Labels" : "Display Config"}
          </button>
        ))}
      </nav>

      {activeSubTab === "label"   && <LabelsSubTab carrierId={carrierId} />}
      {activeSubTab === "display" && <DisplayConfigSubTab carrierId={carrierId} />}
    </div>
  );
}