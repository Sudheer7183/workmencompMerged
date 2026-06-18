/**
 * Database Cleanup — API service layer.
 *
 * All API calls for the database cleanup feature.
 * Uses axios exclusively — never raw fetch.
 */

import axios from "axios";

export interface CleanupPreview {
  premium_variance: number;
  payroll_variance_class: number;
  payroll_variance_policy: number;
  zero_payroll: number;
  missing_payroll: number;
  policies: number;
  policyholders: number;
  ingestion_runs: number;
  ingestion_errors: number;
  ingestion_skipped_rows: number;
  ingestion_rollbacks: number;
  field_mapping_sessions: number;
  field_mapping_proposals: number;
  report_jobs: number;
}

export interface CleanupExecuteResult {
  cleanup_id: number;
  status: string;
  policies_archived: number | null;
  completed_at: string | null;
}

export interface CleanupHistoryEntry {
  cleanup_id: number;
  initiated_by: string;
  initiated_at: string;
  status: "COMPLETE" | "FAILED" | "IN_PROGRESS";
  policies_archived: number | null;
  completed_at: string | null;
  error_detail: string | null;
}

export async function fetchCleanupPreview(): Promise<CleanupPreview> {
  const { data } = await axios.post<CleanupPreview>(
    "/api/v1/database-cleanup/preview",
    {}
  );
  return data;
}

export async function executeCleanup(): Promise<CleanupExecuteResult> {
  const { data } = await axios.post<CleanupExecuteResult>(
    "/api/v1/database-cleanup/execute",
    { confirm: "CONFIRM" }
  );
  return data;
}

export async function fetchCleanupHistory(): Promise<CleanupHistoryEntry[]> {
  const { data } = await axios.get<CleanupHistoryEntry[]>(
    "/api/v1/database-cleanup/history"
  );
  return data;
}
