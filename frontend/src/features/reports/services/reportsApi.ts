/**
 * reportsApi.ts — Phase 5
 *
 * All API calls for the report generation feature.
 * Per V9 S21.2 and V9 S26.
 *
 * All calls use axios — no raw fetch() per FIXES.md Bug #2.
 */

import axios from "axios";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ReportType =
  | "policy_audit"
  | "book_summary"
  | "class_code_variance"
  | "ingestion_audit_trail"
  | "exception_report";

export type OutputFormat = "pdf" | "excel";

export type JobStatus = "QUEUED" | "PROCESSING" | "COMPLETE" | "FAILED";

export interface GenerateReportRequest {
  carrier_id: number;
  report_type: ReportType;
  output_format: OutputFormat;
  policy_id?: number;
  run_id?: number;
}

export interface GenerateReportResponse {
  job_id: string;
}

export interface ReportJobStatus {
  job_id: string;
  status: JobStatus;
  file_url: string | null;
  report_type: ReportType;
  output_format: OutputFormat;
  requested_at: string | null;
  completed_at: string | null;
  error_detail: string | null;
}

export interface ReportTemplate {
  carrier_id: number;
  logo_url: string | null;
  primary_colour: string | null;
  secondary_colour: string | null;
  contact_block: string | null;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * POST /api/v1/reports/generate
 * Creates a report job and returns the job_id for polling.
 * Returns 202 Accepted immediately.
 */
export async function generateReport(
  request: GenerateReportRequest
): Promise<GenerateReportResponse> {
  const { data } = await axios.post<GenerateReportResponse>(
    "/api/v1/reports/generate",
    request
  );
  return data;
}

/**
 * GET /api/v1/reports/{jobId}/status
 * Polls the job status. Returns file_url when status='COMPLETE'.
 */
export async function getReportStatus(jobId: string): Promise<ReportJobStatus> {
  const { data } = await axios.get<ReportJobStatus>(
    `/api/v1/reports/${jobId}/status`
  );
  return data;
}

/**
 * GET /api/v1/admin/report-template/{carrierId}
 * Returns the carrier_report_templates row (branding for reports).
 */
export async function getReportTemplate(
  carrierId: number
): Promise<ReportTemplate> {
  const { data } = await axios.get<ReportTemplate>(
    `/api/v1/admin/report-template/${carrierId}`
  );
  return data;
}

/**
 * PUT /api/v1/admin/report-template/{carrierId}
 * Saves the carrier report template branding.
 */
export async function putReportTemplate(
  carrierId: number,
  body: Partial<Omit<ReportTemplate, "carrier_id">>
): Promise<ReportTemplate> {
  const { data } = await axios.put<ReportTemplate>(
    `/api/v1/admin/report-template/${carrierId}`,
    body
  );
  return data;
}

/**
 * POST /api/v1/tenant/branding/report-logo/{carrierId}
 * Uploads a carrier-specific report logo to S3.
 */
export async function uploadReportLogo(
  carrierId: number,
  file: File
): Promise<{ logo_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await axios.post<{ logo_url: string }>(
    `/api/v1/tenant/branding/report-logo/${carrierId}`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Returns true for report types that support only Excel output.
 * Used to decide whether to show a PDF option in the format dropdown.
 */
export function isExcelOnly(reportType: ReportType): boolean {
  return (
    reportType === "class_code_variance" ||
    reportType === "ingestion_audit_trail" ||
    reportType === "exception_report"
  );
}
