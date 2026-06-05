/**
 * ingestion/services/ingestionApi.ts
 *
 * All API calls for the ingestion feature (Phase 3).
 * uploadFile now accepts ingestion_mode and supports uploading
 * multiple files sequentially (one API call per file).
 */

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