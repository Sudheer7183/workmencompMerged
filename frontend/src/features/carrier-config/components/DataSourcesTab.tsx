/**
 * DataSourcesTab — Phase 4 (V9 S15.2 Tab 1).
 *
 * Allows TENANT_ADMIN to manage data source configurations per carrier.
 * Features:
 *   - List all active sources for a carrier
 *   - Add new source (name, type, anchor, sheet, delimiter)
 *   - Edit existing source inline
 *   - Soft-delete source
 *   - Upload & Test: validates a sample file and returns detected columns
 *
 * Only visible when user.role === TENANT_ADMIN.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IngestionRun {
  run_id: number;
  status: string;
  rows_ingested: number | null;
  rows_skipped: number;
  started_at: string;
  completed_at: string | null;
}

interface DataSource {
  source_id: number;
  carrier_id: number;
  source_name: string;
  source_type: "xlsx" | "csv" | "xml";
  anchor_string: string | null;
  sheet_name: string | null;
  delimiter: string | null;
  is_active: boolean;
  created_at: string;
}

interface FormState {
  source_name: string;
  source_type: "xlsx" | "csv" | "xml";
  anchor_string: string;
  sheet_name: string;
  delimiter: string;
}

const DEFAULT_FORM: FormState = {
  source_name: "",
  source_type: "xlsx",
  anchor_string: "",
  sheet_name: "",
  delimiter: "",
};

// ---------------------------------------------------------------------------
// DataSourcesTab
// ---------------------------------------------------------------------------

interface DataSourcesTabProps {
  carrierId: number;
}

export function DataSourcesTab({ carrierId }: DataSourcesTabProps): React.JSX.Element {
  const label_calc_engine = useLabels("calc_engine");
  const label_shared = useLabels("shared");
  const { user } = useAuth();

  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Add/edit state.
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Test upload state.
  const [testingSourceId, setTestingSourceId] = useState<number | null>(null);
  const [testColumns, setTestColumns] = useState<string[]>([]);
  const [testError, setTestError] = useState<string | null>(null);
  const testFileRef = useRef<HTMLInputElement>(null);

  // Ingestion history
  const [recentRuns, setRecentRuns] = useState<IngestionRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  const fetchSources = useCallback(async (): Promise<void> => {
    if (!carrierId) return;
    setLoading(true);
    setLoadError(null);
    setRunsLoading(true);
    try {
      const [srcRes, runsRes] = await Promise.allSettled([
        axios.get<DataSource[]>(`/api/v1/admin/data-sources?carrier_id=${carrierId}`),
        axios.get<{ runs: IngestionRun[] }>(`/api/v1/ingestion/runs?carrier_id=${carrierId}&limit=10`).catch(() => ({ data: { runs: [] } })),
      ]);
      if (srcRes.status === "fulfilled") setSources(srcRes.value.data);
      if (runsRes.status === "fulfilled") setRecentRuns((runsRes.value as { data: { runs?: IngestionRun[] } }).data.runs ?? []);
    } catch (e: unknown) {
      setLoadError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Failed to load data sources."
      );
    } finally {
      setLoading(false);
      setRunsLoading(false);
    }
  }, [carrierId]);

  useEffect(() => {
    void fetchSources();
  }, [fetchSources]);

  function startAdd(): void {
    setEditingId(null);
    setForm(DEFAULT_FORM);
    setFormError(null);
    setShowAddForm(true);
  }

  function startEdit(source: DataSource): void {
    setShowAddForm(false);
    setEditingId(source.source_id);
    setForm({
      source_name: source.source_name,
      source_type: source.source_type,
      anchor_string: source.anchor_string ?? "",
      sheet_name: source.sheet_name ?? "",
      delimiter: source.delimiter ?? "",
    });
    setFormError(null);
  }

  function cancelEdit(): void {
    setShowAddForm(false);
    setEditingId(null);
    setForm(DEFAULT_FORM);
    setFormError(null);
  }

  async function handleSave(): Promise<void> {
    if (!form.source_name.trim()) {
      setFormError("Source name is required.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const payload = {
      carrier_id: carrierId,
      source_name: form.source_name.trim(),
      source_type: form.source_type,
      anchor_string: form.anchor_string.trim() || null,
      sheet_name: form.sheet_name.trim() || null,
      delimiter: form.delimiter.trim() || null,
    };

    try {
      if (editingId !== null) {
        await axios.put(`/api/v1/admin/data-sources/${editingId}`, payload);
      } else {
        await axios.post("/api/v1/admin/data-sources", payload);
      }
      cancelEdit();
      await fetchSources();
    } catch (e: unknown) {
      setFormError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Save failed."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(sourceId: number): Promise<void> {
    if (!window.confirm("Are you sure you want to remove this data source?")) return;
    try {
      await axios.delete(`/api/v1/admin/data-sources/${sourceId}`);
      await fetchSources();
    } catch (e: unknown) {
      alert(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Delete failed."
      );
    }
  }

  async function handleTestUpload(sourceId: number): Promise<void> {
    const input = testFileRef.current;
    if (!input?.files?.length) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append("file", file);

    setTestingSourceId(sourceId);
    setTestColumns([]);
    setTestError(null);

    try {
      const res = await axios.post<{ detected_columns: string[] }>(
        `/api/v1/admin/data-sources/${sourceId}/test`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setTestColumns(res.data.detected_columns);
    } catch (e: unknown) {
      setTestError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Test failed."
      );
    } finally {
      if (input) input.value = "";
    }
  }

  if (user?.role !== "TENANT_ADMIN") {
    return (
      <div className="data-sources-tab data-sources-tab--no-access" data-testid="data-sources-tab">
        <p className="data-sources-tab__access-note">
          {label_shared("admin_only_tab", "admin_only_tab") ?? "This tab requires Tenant Administrator access."}
        </p>
      </div>
    );
  }

  return (
    <div className="data-sources-tab" data-testid="data-sources-tab">
      <div className="data-sources-tab__toolbar">
        <h2 className="data-sources-tab__heading">
          {label_shared("data_sources_heading", "data_sources_heading") ?? "Data Sources"}
        </h2>
        <button
          className="btn btn--primary"
          onClick={startAdd}
          disabled={showAddForm}
          data-testid="data-sources-tab__add-btn"
        >
          {label_shared("btn_add_source", "btn_add_source") ?? "+ Add Source"}
        </button>
      </div>

      {loadError && (
        <p className="data-sources-tab__error" role="alert">
          {loadError}
        </p>
      )}

      {/* ── Add / Edit form ─────────────────────────────────────────────── */}
      {(showAddForm || editingId !== null) && (
        <div
          className="data-sources-tab__form"
          data-testid="data-sources-tab__form"
        >
          <h3 className="data-sources-tab__form-title">
            {editingId !== null
              ? label_shared("edit_source_title", "edit_source_title") ?? "Edit Source"
              : label_shared("add_source_title", "add_source_title") ?? "Add Source"}
          </h3>

          <div className="data-sources-tab__form-row">
            <label className="data-sources-tab__label">
              {label_shared("source_name_label", "source_name_label") ?? "Source Name"}
              <input
                type="text"
                className="data-sources-tab__input"
                value={form.source_name}
                onChange={(e) => setForm((p) => ({ ...p, source_name: e.target.value }))}
                placeholder="e.g. WC Payroll Feed"
                data-testid="data-sources-tab__name-input"
              />
            </label>

            <label className="data-sources-tab__label">
              {label_shared("source_type_label", "source_type_label") ?? "File Type"}
              <select
                className="data-sources-tab__select"
                value={form.source_type}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    source_type: e.target.value as "xlsx" | "csv" | "xml",
                  }))
                }
                data-testid="data-sources-tab__type-select"
              >
                <option value="xlsx">XLSX</option>
                <option value="csv">CSV</option>
                <option value="xml">XML</option>
              </select>
            </label>
          </div>

          <div className="data-sources-tab__form-row">
            <label className="data-sources-tab__label">
              {label_shared("anchor_string_label", "anchor_string_label") ?? "Anchor String (optional)"}
              <input
                type="text"
                className="data-sources-tab__input"
                value={form.anchor_string}
                onChange={(e) => setForm((p) => ({ ...p, anchor_string: e.target.value }))}
                placeholder="e.g. Policy Number"
                data-testid="data-sources-tab__anchor-input"
              />
            </label>

            {form.source_type === "xlsx" && (
              <label className="data-sources-tab__label">
                {label_shared("sheet_name_label", "sheet_name_label") ?? "Sheet Name (optional)"}
                <input
                  type="text"
                  className="data-sources-tab__input"
                  value={form.sheet_name}
                  onChange={(e) => setForm((p) => ({ ...p, sheet_name: e.target.value }))}
                  placeholder="e.g. Sheet1"
                  data-testid="data-sources-tab__sheet-input"
                />
              </label>
            )}

            {form.source_type === "csv" && (
              <label className="data-sources-tab__label">
                {label_shared("delimiter_label", "delimiter_label") ?? "Delimiter (optional)"}
                <input
                  type="text"
                  className="data-sources-tab__input"
                  value={form.delimiter}
                  onChange={(e) => setForm((p) => ({ ...p, delimiter: e.target.value }))}
                  placeholder="e.g. , or ;"
                  maxLength={1}
                  data-testid="data-sources-tab__delimiter-input"
                />
              </label>
            )}
          </div>

          {formError && (
            <p className="data-sources-tab__form-error" role="alert">
              {formError}
            </p>
          )}

          <div className="data-sources-tab__form-actions">
            <button
              className="btn btn--primary"
              onClick={() => void handleSave()}
              disabled={saving}
              data-testid="data-sources-tab__save-btn"
            >
              {saving ? "Saving…" : label_calc_engine("btn.save", "Save Changes") ?? "Save"}
            </button>
            <button
              className="btn btn--secondary"
              onClick={cancelEdit}
              data-testid="data-sources-tab__cancel-btn"
            >
              {label_calc_engine("btn.cancel", "Cancel") ?? "Cancel"}
            </button>
          </div>
        </div>
      )}

      {/* ── Sources list ─────────────────────────────────────────────────── */}
      {loading ? (
        <p className="data-sources-tab__loading">
          {label_shared("loading", "Loading…") ?? "Loading…"}
        </p>
      ) : sources.length === 0 ? (
        <p className="data-sources-tab__empty" data-testid="data-sources-tab__empty">
          {label_shared("no_data_sources", "no_data_sources") ?? "No data sources configured yet. Click Add Source to begin."}
        </p>
      ) : (
        <div
          className="data-sources-tab__list"
          data-testid="data-sources-tab__list"
        >
          {sources.map((source) => (
            <div
              key={source.source_id}
              className="data-sources-tab__source-card"
              data-testid={`data-sources-tab__source-${source.source_id}`}
            >
              <div className="data-sources-tab__source-info">
                <span className="data-sources-tab__source-name">{source.source_name}</span>
                <span className="data-sources-tab__source-type badge badge--info">
                  {source.source_type.toUpperCase()}
                </span>
                {source.anchor_string && (
                  <span className="data-sources-tab__source-meta">
                    Anchor: <code>{source.anchor_string}</code>
                  </span>
                )}
                {source.sheet_name && (
                  <span className="data-sources-tab__source-meta">
                    Sheet: <code>{source.sheet_name}</code>
                  </span>
                )}
              </div>

              <div className="data-sources-tab__source-actions">
                <button
                  className="btn btn--small btn--secondary"
                  onClick={() => startEdit(source)}
                  data-testid="data-sources-tab__edit-btn"
                >
                  {label_calc_engine("btn.edit", "Edit") ?? "Edit"}
                </button>

                {/* Upload & Test */}
                <label
                  className="btn btn--small btn--ghost data-sources-tab__test-label"
                  data-testid="data-sources-tab__test-label"
                >
                  {label_shared("btn_test", "btn_test") ?? "Upload & Test"}
                  <input
                    ref={testFileRef}
                    type="file"
                    className="data-sources-tab__test-input"
                    accept=".xlsx,.csv,.xml,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    onChange={() => void handleTestUpload(source.source_id)}
                    data-testid="data-sources-tab__test-file-input"
                  />
                </label>

                <button
                  className="btn btn--small btn--ghost btn--destructive"
                  onClick={() => void handleDelete(source.source_id)}
                  data-testid="data-sources-tab__delete-btn"
                >
                  {label_shared("btn_delete", "btn_delete") ?? "Remove"}
                </button>
              </div>

              {/* Test result */}
              {testingSourceId === source.source_id && (
                <div
                  className="data-sources-tab__test-result"
                  data-testid="data-sources-tab__test-result"
                >
                  {testError ? (
                    <p className="data-sources-tab__test-error" role="alert">
                      {testError}
                    </p>
                  ) : testColumns.length > 0 ? (
                    <div>
                      <p className="data-sources-tab__test-success">
                        ✓ Detected {testColumns.length} columns:
                      </p>
                      <ul className="data-sources-tab__test-columns">
                        {testColumns.map((col) => (
                          <li key={col}>
                            <code>{col}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {/* ── Ingestion History (last 10 runs) ───────────────────────────── */}
      <section
        className="data-sources-tab__history"
        data-testid="data-sources-tab__history"
        aria-label="Ingestion history"
      >
        <h3 className="data-sources-tab__history-title">
          {label_shared("ingestion_history_heading", "ingestion_history_heading") ?? "Ingestion History"}
          <span className="data-sources-tab__section-count">(last 10 runs)</span>
        </h3>
        {runsLoading ? (
          <p className="data-sources-tab__loading">{label_shared("loading", "Loading…") ?? "Loading…"}</p>
        ) : recentRuns.length === 0 ? (
          <p className="data-sources-tab__empty" data-testid="data-sources-tab__no-runs">
            {label_shared("no_runs", "no_runs") ?? "No ingestion runs for this carrier yet."}
          </p>
        ) : (
          <table
            className="data-sources-tab__history-table"
            data-testid="data-sources-tab__history-table"
          >
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Status</th>
                <th>Rows Ingested</th>
                <th>Rows Skipped</th>
                <th>Started</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.map((run) => (
                <tr key={run.run_id} data-testid={`data-sources-tab__run-row-${run.run_id}`}>
                  <td>#{run.run_id}</td>
                  <td>
                    <span className={`badge badge--${run.status === "complete" ? "success" : run.status === "partial" ? "warning" : run.status === "failed" ? "error" : "neutral"}`}>
                      {run.status}
                    </span>
                  </td>
                  <td>{run.rows_ingested ?? 0}</td>
                  <td>{run.rows_skipped}</td>
                  <td>{new Date(run.started_at).toLocaleString()}</td>
                  <td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
