/**
 * ReportDownloadLink.tsx — Phase 5
 *
 * Opens a pre-signed S3 URL in a new browser tab.
 * The URL already contains the 24h TTL signature — no backend call needed.
 * Per V9 S26.
 */

import React from "react";
import { type ReportType, type OutputFormat } from "./services/reportsApi";
import { useLabels } from "@/hooks/useLabels";

interface ReportDownloadLinkProps {
  /** Pre-signed S3 URL returned by the status endpoint when COMPLETE */
  fileUrl: string;
  reportType: ReportType;
  outputFormat: OutputFormat;
  /** Optional policy number for a descriptive filename hint */
  policyNumber?: string;
}

/**
 * Maps a report type + format to a suggested download filename.
 * The actual downloaded filename is determined by S3 content-disposition,
 * but this label is shown in the download button.
 */
function buildFilenameHint(
  reportType: ReportType,
  outputFormat: OutputFormat,
  policyNumber?: string
): string {
  const ext = outputFormat === "pdf" ? "pdf" : "xlsx";
  switch (reportType) {
    case "policy_audit":
      return policyNumber
        ? `policy-audit-${policyNumber}.${ext}`
        : `policy-audit.${ext}`;
    case "book_summary":
      return `policy-book-summary.${ext}`;
    case "class_code_variance":
      return `class-code-variance.${ext}`;
    case "ingestion_audit_trail":
      return `ingestion-audit-trail.${ext}`;
    case "exception_report":
      return `exception-report.${ext}`;
    default:
      return `report.${ext}`;
  }
}

export function ReportDownloadLink({
  fileUrl,
  reportType,
  outputFormat,
  policyNumber,
}: ReportDownloadLinkProps): React.JSX.Element {
  const label = useLabels("reports");
  const filename = buildFilenameHint(reportType, outputFormat, policyNumber);

  function handleDownload(): void {
    window.open(fileUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <button
      type="button"
      className="btn btn--primary"
      onClick={handleDownload}
      data-testid="report-download-btn"
      title={filename}
    >
      {outputFormat === "pdf" ? "📄" : "📊"}{" "}
      {label("btn.download_now", "report_download_now") ?? "Download Now"}
    </button>
  );
}
