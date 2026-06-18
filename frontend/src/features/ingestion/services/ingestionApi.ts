

import axios from "axios";

// ── Types ────────────────────────────────────────────────────────────────────

export type IngestionMode = "calc_engine" | "display_only";

export interface UploadResponse {
  run_id: number;
  status: string;
  session_id: number;
  rows_ingested: number | null;
  rows_skipped: number;
  rows_failed: number;
  error_detail: string | null;
}

export interface MappingProposal {
  proposal_id: number;
  session_id: number;
  source_field: string;
  source_sample: string | null;
  inferred_type: string;
  proposed_target: string | null;
  confidence: "HIGH" | "MEDIUM" | "LOW" | "UNMATCHED";
  score: number;
  transform_fn: string;
  is_excluded: boolean;
  match_reason: string;
}

export interface MappingSession {
  session_id: number;
  ingestion_run_id: number;
  carrier_id: number;
  status: string;
  auto_mapped_count: number;
  flagged_count: number;
  unmatched_count: number;
  proposals: MappingProposal[];
}

export interface CanonicalColumn {
  column_name: string;
  data_type: string;
}

export interface MappingActionResponse {
  session_id: number;
  run_id: number;
  status: string;
  message: string;
}

export interface IngestionRunStatus {
  run_id: number;
  status: string;
  rows_ingested: number | null;
  rows_skipped: number;
  rows_failed: number;
  error_detail: string | null;
  started_at: string;
  completed_at: string | null;
}

// ── Upload ───────────────────────────────────────────────────────────────────

/**
 * Upload a single file to the ingestion endpoint.
 * Returns the run_id and session_id for the mapping gate.
 *
 * For multi-file uploads (Type 1: XML + Payroll + Audit Report,
 * Type 2: Payroll + Audit Report), the caller uploads each file
 * individually and the backend pairs them by policy number.
 * The last upload's session_id is what the user reviews.
 */
export async function uploadFile(
  carrierId: number,
  sourceId: number,
  file: File,
  ingestionMode: IngestionMode = "calc_engine"
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("carrier_id", String(carrierId));
  form.append("source_id", String(sourceId));
  form.append("file", file);
  form.append("ingestion_mode", ingestionMode);

  const { data } = await axios.post<UploadResponse>(
    "/api/v1/ingestion/upload",
    form
  );
  return data;
}

// ── Mapping gate ─────────────────────────────────────────────────────────────

export async function fetchMappingSession(
  sessionId: number
): Promise<MappingSession> {
  const { data } = await axios.get<MappingSession>(
    `/api/v1/ingestion/mapping/${sessionId}`
  );
  return data;
}

export async function fetchCanonicalColumns(): Promise<CanonicalColumn[]> {
  const { data } = await axios.get<CanonicalColumn[]>(
    "/api/v1/ingestion/mapping/canonical-columns"
  );
  return data;
}

export async function updateMappingProposal(
  sessionId: number,
  proposalId: number,
  updates: {
    proposed_target?: string | null;
    transform_fn?: string;
    is_excluded?: boolean;
  }
): Promise<void> {
  await axios.put(
    `/api/v1/ingestion/mapping/${sessionId}/${proposalId}`,
    updates
  );
}

export async function approveMapping(
  sessionId: number
): Promise<MappingActionResponse> {
  const { data } = await axios.post<MappingActionResponse>(
    `/api/v1/ingestion/mapping/${sessionId}/approve`
  );
  return data;
}

export async function rejectMapping(
  sessionId: number
): Promise<MappingActionResponse> {
  const { data } = await axios.post<MappingActionResponse>(
    `/api/v1/ingestion/mapping/${sessionId}/reject`
  );
  return data;
}

// ── Run status ───────────────────────────────────────────────────────────────

export async function fetchRunStatus(
  runId: number
): Promise<IngestionRunStatus> {
  const { data } = await axios.get<IngestionRunStatus>(
    `/api/v1/ingestion/runs/${runId}`
  );
  return data;
}

// ── Carrier mode lock ─────────────────────────────────────────────────────────

export interface CarrierIngestionMode {
  /** null = no runs yet, either mode is available */
  locked_mode: "calc_engine" | "display_only" | null;
  has_runs: boolean;
}

/**
 * Returns the ingestion mode that this carrier is locked to.
 * null means the carrier has no prior runs — either mode can be chosen.
 */
export async function fetchCarrierIngestionMode(
  carrierId: number
): Promise<CarrierIngestionMode> {
  const { data } = await axios.get<CarrierIngestionMode>(
    `/api/v1/ingestion/carrier-mode/${carrierId}`
  );
  return data;
}

// =============================================================================
// Phase 4 — Exception tracking, rollback, data sources, field maps
// All calls use axios (per FIXES.md Bug #2 — no raw fetch)
// =============================================================================



// ---------------------------------------------------------------------------
// Exception tracking types
// ---------------------------------------------------------------------------

export interface IngestionErrorRecord {
  error_id: number;
  run_id: number;
  row_number: number | null;
  field_name: string | null;
  error_type: string;
  error_message: string;
  raw_value: string | null;
  created_at: string;
}

export interface SkippedRow {
  skip_id: number;
  run_id: number;
  row_number: number;
  raw_data: Record<string, unknown>;
  skip_reason: string;
  error_codes: string[];
  resolution_status: "PENDING" | "CORRECTED" | "DISMISSED";
  corrected_data: Record<string, unknown> | null;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface RollbackResult {
  rollback_id: number;
  run_id: number;
  status: string;
  rows_removed: number;
  initiated_by: string;
  initiated_at: string;
}

export interface DataSource {
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

export interface FieldMap {
  map_id: number;
  carrier_id: number;
  source_field: string;
  target_column: string;
  file_type: string | null;
  transform_fn: string;
  is_active: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Exception tracking API calls
// ---------------------------------------------------------------------------

export async function fetchRunErrors(
  runId: number,
  errorCode?: string
): Promise<IngestionErrorRecord[]> {
  const params = errorCode ? `?error_code=${errorCode}` : "";
  const { data } = await axios.get<IngestionErrorRecord[]>(
    `/api/v1/ingestion/runs/${runId}/errors${params}`
  );
  return data;
}

export async function fetchSkippedRows(
  runId: number,
  resolutionStatus?: string
): Promise<SkippedRow[]> {
  const params = resolutionStatus ? `?resolution_status=${resolutionStatus}` : "";
  const { data } = await axios.get<SkippedRow[]>(
    `/api/v1/ingestion/runs/${runId}/skipped${params}`
  );
  return data;
}

export async function rollbackRun(runId: number): Promise<RollbackResult> {
  const { data } = await axios.post<RollbackResult>(
    `/api/v1/ingestion/runs/${runId}/rollback`
  );
  return data;
}

export async function correctSkippedRow(
  skipId: number,
  correctedData: Record<string, unknown>
): Promise<SkippedRow> {
  const { data } = await axios.put<SkippedRow>(
    `/api/v1/ingestion/skipped/${skipId}/correct`,
    { corrected_data: correctedData }
  );
  return data;
}

export async function reingestSkippedRow(
  skipId: number
): Promise<{ success: boolean; error: string | null; rows_ingested: number }> {
  const { data } = await axios.post(
    `/api/v1/ingestion/skipped/${skipId}/reingest`
  );
  return data;
}

export async function dismissSkippedRow(skipId: number): Promise<SkippedRow> {
  const { data } = await axios.post<SkippedRow>(
    `/api/v1/ingestion/skipped/${skipId}/dismiss`
  );
  return data;
}

// ---------------------------------------------------------------------------
// Data Sources API calls
// ---------------------------------------------------------------------------

export async function fetchDataSources(carrierId: number): Promise<DataSource[]> {
  const { data } = await axios.get<DataSource[]>(
    `/api/v1/admin/data-sources?carrier_id=${carrierId}`
  );
  return data;
}

export async function createDataSource(
  payload: Omit<DataSource, "source_id" | "is_active" | "created_at">
): Promise<DataSource> {
  const { data } = await axios.post<DataSource>("/api/v1/admin/data-sources", payload);
  return data;
}

export async function updateDataSource(
  sourceId: number,
  payload: Partial<Omit<DataSource, "source_id" | "carrier_id" | "created_at">>
): Promise<DataSource> {
  const { data } = await axios.put<DataSource>(
    `/api/v1/admin/data-sources/${sourceId}`,
    payload
  );
  return data;
}

export async function deleteDataSource(sourceId: number): Promise<void> {
  await axios.delete(`/api/v1/admin/data-sources/${sourceId}`);
}

export async function testDataSource(
  sourceId: number,
  file: File
): Promise<{ detected_columns: string[]; column_count: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await axios.post(
    `/api/v1/admin/data-sources/${sourceId}/test`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// ---------------------------------------------------------------------------
// Field Maps API calls
// ---------------------------------------------------------------------------

export async function fetchFieldMaps(
  carrierId: number,
  fileType?: string
): Promise<FieldMap[]> {
  const params = fileType ? `&file_type=${fileType}` : "";
  const { data } = await axios.get<FieldMap[]>(
    `/api/v1/admin/field-maps?carrier_id=${carrierId}${params}`
  );
  return data;
}

export async function bulkUpsertFieldMaps(
  carrierId: number,
  mappings: Array<{ source_field: string; target_column: string; file_type?: string; transform_fn?: string }>
): Promise<FieldMap[]> {
  const { data } = await axios.put<FieldMap[]>(
    `/api/v1/admin/field-maps/${carrierId}`,
    { mappings }
  );
  return data;
}

export async function deleteFieldMap(mapId: number): Promise<void> {
  await axios.delete(`/api/v1/admin/field-maps/${mapId}`);
}

// =============================================================================
// Phase 7C — Audit Calculation Engine trigger
// =============================================================================

export interface AuditRunResponse {
  policy_id: number;
  ingestion_run_id: number;
  skipped: boolean;
  engine_ran: boolean;
  risk_level: string | null;
  variance_amount: string | null;
  variance_pct: string | null;
  missing_payroll_count: number;
  zero_payroll_count: number;
  narrative_generated: boolean;
}

/**
 * POST /api/v1/audit/run
 * Triggers the audit calculation engine for a completed ingestion run.
 *
 * For display_only bulk sessions, pass ALL run_ids from the session in
 * bulkRunIds. The backend will then aggregate data across all runs and
 * generate narratives exactly once per unique policy — not once per file.
 * bulkRunIds should only be populated on the LAST file's run_audit call.
 */
export async function runAuditEngine(
  carrierId: number,
  ingestionRunId: number,
  overrideUseEngine?: boolean,
  bulkRunIds?: number[],
): Promise<AuditRunResponse> {
  const { data } = await axios.post<AuditRunResponse>("/api/v1/audit/run", {
    carrier_id: carrierId,
    ingestion_run_id: ingestionRunId,
    override_use_engine: overrideUseEngine ?? null,
    bulk_run_ids: bulkRunIds ?? [],
  });
  return data;
}