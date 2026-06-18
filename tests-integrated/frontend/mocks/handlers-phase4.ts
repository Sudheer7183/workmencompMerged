/**
 * MSW (Mock Service Worker) handlers for Phase 4 API endpoints.
 *
 * Extends the existing Phase 1–3 handler set.
 * Import these into your MSW server setup:
 *
 *   import { handlers as phase4Handlers } from "./handlers-phase4";
 *   const server = setupServer(...existingHandlers, ...phase4Handlers);
 *
 * All handlers return realistic response shapes matching the Phase 4
 * Pydantic response models defined in:
 *   - backend/app/api/v1/ingestion.py  (exception tracking, rollback endpoints)
 *   - backend/app/api/v1/data_sources.py  (data sources, field maps)
 */

import { http, HttpResponse } from "msw";

// ---------------------------------------------------------------------------
// Shared mock data
// ---------------------------------------------------------------------------

const MOCK_SKIPPED_ROWS = [
  {
    skip_id: 1,
    run_id: 42,
    row_number: 5,
    raw_data: { "Policy Number": "", "Insured Name": "Acme Corp", "Est Premium End": "not-a-number" },
    skip_reason: "Row 5 has no policy_number",
    error_codes: ["MISSING_POLICY_NUMBER"],
    resolution_status: "PENDING",
    corrected_data: null,
    resolved_by: null,
    resolved_at: null,
  },
  {
    skip_id: 2,
    run_id: 42,
    row_number: 9,
    raw_data: { "Policy Number": "POL-X", "Insured Name": "Beta Inc", "Est Premium End": "bad" },
    skip_reason: "INVALID_NUMERIC_VALUE for est_premium_end",
    error_codes: ["INVALID_NUMERIC_VALUE"],
    resolution_status: "PENDING",
    corrected_data: null,
    resolved_by: null,
    resolved_at: null,
  },
];

const MOCK_ERRORS = [
  {
    error_id: 1,
    run_id: 42,
    row_number: 5,
    field_name: "policy_number",
    error_type: "MISSING_POLICY_NUMBER",
    error_message: "Row 5 has no policy_number — cannot create policy record",
    raw_value: null,
    created_at: "2026-06-01T10:00:30Z",
  },
  {
    error_id: 2,
    run_id: 42,
    row_number: 9,
    field_name: "est_premium_end",
    error_type: "INVALID_NUMERIC_VALUE",
    error_message: "Cannot parse 'bad' as Decimal",
    raw_value: "bad",
    created_at: "2026-06-01T10:00:31Z",
  },
];

const MOCK_DATA_SOURCES = [
  {
    source_id: 1,
    carrier_id: 1,
    source_name: "WC Payroll Feed",
    source_type: "xlsx",
    anchor_string: "Policy Number",
    sheet_name: null,
    delimiter: null,
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
  {
    source_id: 2,
    carrier_id: 1,
    source_name: "CSV Export",
    source_type: "csv",
    anchor_string: null,
    sheet_name: null,
    delimiter: ",",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
];

// V9 S11.9: field maps use target_column + transform_fn, not canonical_column
const MOCK_FIELD_MAPS = [
  {
    map_id: 1,
    carrier_id: 1,
    source_field: "Policy Number",
    target_column: "policy_number",
    file_type: null,
    transform_fn: "as-is",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
  {
    map_id: 2,
    carrier_id: 1,
    source_field: "Insured Name",
    target_column: "insured_name",
    file_type: "xlsx",
    transform_fn: "trim",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
  {
    map_id: 3,
    carrier_id: 1,
    source_field: "Earned Prem.",
    target_column: "actual_premium",
    file_type: "xlsx",
    transform_fn: "decimal",
    is_active: true,
    created_at: "2026-06-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Exception tracking handlers
// ---------------------------------------------------------------------------

export const handlers = [
  // GET /api/v1/ingestion/runs/:runId/errors
  http.get("/api/v1/ingestion/runs/:runId/errors", ({ params }) => {
    const runId = Number(params.runId);
    if (runId === 404) return HttpResponse.json({ detail: "Run not found" }, { status: 404 });
    return HttpResponse.json(MOCK_ERRORS.filter((e) => e.run_id === runId || runId === 42));
  }),

  // GET /api/v1/ingestion/runs/:runId/skipped
  http.get("/api/v1/ingestion/runs/:runId/skipped", ({ params, request }) => {
    const runId = Number(params.runId);
    const url = new URL(request.url);
    const resFilter = url.searchParams.get("resolution_status");
    let rows = MOCK_SKIPPED_ROWS.filter((r) => r.run_id === runId || runId === 42);
    if (resFilter) rows = rows.filter((r) => r.resolution_status === resFilter);
    return HttpResponse.json(rows);
  }),

  // POST /api/v1/ingestion/runs/:runId/rollback
  http.post("/api/v1/ingestion/runs/:runId/rollback", ({ params }) => {
    const runId = Number(params.runId);
    if (runId === 409) {
      return HttpResponse.json(
        { detail: "Run has already been rolled back" },
        { status: 409 }
      );
    }
    return HttpResponse.json({
      rollback_id: 1,
      run_id: runId,
      status: "COMPLETE",
      rows_removed: 18,
      initiated_by: "demo-admin",
      initiated_at: new Date().toISOString(),
    });
  }),

  // PUT /api/v1/ingestion/skipped/:skipId/correct
  http.put("/api/v1/ingestion/skipped/:skipId/correct", async ({ params, request }) => {
    const skipId = Number(params.skipId);
    const body = await request.json() as { corrected_data: Record<string, unknown> };
    const row = MOCK_SKIPPED_ROWS.find((r) => r.skip_id === skipId);
    if (!row) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json({
      ...row,
      corrected_data: body.corrected_data,
    });
  }),

  // POST /api/v1/ingestion/skipped/:skipId/reingest
  http.post("/api/v1/ingestion/skipped/:skipId/reingest", ({ params }) => {
    const skipId = Number(params.skipId);
    const row = MOCK_SKIPPED_ROWS.find((r) => r.skip_id === skipId);
    if (!row) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json({ success: true, error: null, rows_ingested: 1 });
  }),

  // POST /api/v1/ingestion/skipped/:skipId/dismiss
  http.post("/api/v1/ingestion/skipped/:skipId/dismiss", ({ params }) => {
    const skipId = Number(params.skipId);
    const row = MOCK_SKIPPED_ROWS.find((r) => r.skip_id === skipId);
    if (!row) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json({
      ...row,
      resolution_status: "DISMISSED",
      resolved_by: "demo-auditor",
      resolved_at: new Date().toISOString(),
    });
  }),

  // ---------------------------------------------------------------------------
  // Data Sources handlers
  // ---------------------------------------------------------------------------

  // GET /api/v1/admin/data-sources
  http.get("/api/v1/admin/data-sources", ({ request }) => {
    const url = new URL(request.url);
    const carrierId = Number(url.searchParams.get("carrier_id") ?? 1);
    return HttpResponse.json(MOCK_DATA_SOURCES.filter((s) => s.carrier_id === carrierId));
  }),

  // POST /api/v1/admin/data-sources
  http.post("/api/v1/admin/data-sources", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    const newSource = {
      source_id: MOCK_DATA_SOURCES.length + 1,
      carrier_id: body.carrier_id as number,
      source_name: body.source_name as string,
      source_type: (body.source_type as string) ?? "xlsx",
      anchor_string: (body.anchor_string as string) ?? null,
      sheet_name: (body.sheet_name as string) ?? null,
      delimiter: (body.delimiter as string) ?? null,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    return HttpResponse.json(newSource, { status: 201 });
  }),

  // PUT /api/v1/admin/data-sources/:sourceId
  http.put("/api/v1/admin/data-sources/:sourceId", async ({ params, request }) => {
    const sourceId = Number(params.sourceId);
    const body = await request.json() as Record<string, unknown>;
    const existing = MOCK_DATA_SOURCES.find((s) => s.source_id === sourceId);
    if (!existing) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json({ ...existing, ...body });
  }),

  // DELETE /api/v1/admin/data-sources/:sourceId
  http.delete("/api/v1/admin/data-sources/:sourceId", ({ params }) => {
    const sourceId = Number(params.sourceId);
    const exists = MOCK_DATA_SOURCES.some((s) => s.source_id === sourceId);
    if (!exists) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return new HttpResponse(null, { status: 204 });
  }),

  // POST /api/v1/admin/data-sources/:sourceId/test
  http.post("/api/v1/admin/data-sources/:sourceId/test", ({ params }) => {
    const sourceId = Number(params.sourceId);
    return HttpResponse.json({
      source_id: sourceId,
      source_type: "xlsx",
      detected_columns: [
        "Policy Number",
        "Insured Name",
        "Est Premium End",
        "Actual Premium",
        "As Of Date",
      ],
      column_count: 5,
    });
  }),

  // ---------------------------------------------------------------------------
  // Field Maps handlers
  // ---------------------------------------------------------------------------

  // GET /api/v1/admin/field-maps
  http.get("/api/v1/admin/field-maps", ({ request }) => {
    const url = new URL(request.url);
    const carrierId = Number(url.searchParams.get("carrier_id") ?? 1);
    const fileType = url.searchParams.get("file_type");
    let maps = MOCK_FIELD_MAPS.filter((m) => m.carrier_id === carrierId);
    if (fileType) maps = maps.filter((m) => m.file_type === fileType || m.file_type === null);
    return HttpResponse.json(maps);
  }),

  // PUT /api/v1/admin/field-maps/:carrierId
  http.put("/api/v1/admin/field-maps/:carrierId", async ({ params, request }) => {
    const carrierId = Number(params.carrierId);
    const body = await request.json() as { mappings: Array<{ source_field: string; target_column?: string; canonical_column?: string; file_type?: string; transform_fn?: string }> };
    const upserted = body.mappings.map((m, idx) => ({
      map_id: 100 + idx,
      carrier_id: carrierId,
      source_field: m.source_field,
      target_column: (m as Record<string, unknown>).target_column as string ?? m.source_field,
      file_type: (m as Record<string, unknown>).file_type as string ?? null,
      transform_fn: (m as Record<string, unknown>).transform_fn as string ?? "as-is",
      is_active: true,
      created_at: new Date().toISOString(),
    }));
    return HttpResponse.json(upserted);
  }),

  // DELETE /api/v1/admin/field-maps/:mapId
  http.delete("/api/v1/admin/field-maps/:mapId", ({ params }) => {
    const mapId = Number(params.mapId);
    const exists = MOCK_FIELD_MAPS.some((m) => m.map_id === mapId);
    if (!exists) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return new HttpResponse(null, { status: 204 });
  }),
];
