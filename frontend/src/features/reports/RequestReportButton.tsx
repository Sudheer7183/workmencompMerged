/**
 * RequestReportButton.tsx — Phase 5
 *
 * Button that triggers report generation. For report types that support both
 * PDF and Excel, shows a dropdown menu. For Excel-only types, shows a single
 * "Export Excel" button.
 *
 * On click → calls POST /api/v1/reports/generate → opens ReportStatusModal.
 *
 * Per V9 S26.
 */

import React, { useRef, useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import { ReportStatusModal } from "./ReportStatusModal";
import {
  generateReport,
  isExcelOnly,
  type OutputFormat,
  type ReportType,
} from "./services/reportsApi";

interface RequestReportButtonProps {
  carrierId: number;
  reportType: ReportType;
  /** Required for report_type='policy_audit' */
  policyId?: number;
  /** Required for exception_report and ingestion_audit_trail */
  runId?: number;
  /** Optional policy number for download filename hints */
  policyNumber?: string;
  /** Custom label for the trigger button */
  label?: string;
  /** Optional data-testid override for the trigger button (e.g. 'book-summary-btn') */
  "data-testid"?: string;
}

export function RequestReportButton({
  carrierId,
  reportType,
  policyId,
  runId,
  policyNumber,
  label,
  "data-testid": testId,
}: RequestReportButtonProps): React.JSX.Element {
  const label_reports = useLabels("reports");
  const label_shared = useLabels("shared");
  const [dropdownOpen, setDropdownOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeFormat, setActiveFormat] = useState<OutputFormat>("pdf");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const excelOnly = isExcelOnly(reportType);

  async function requestGeneration(format: OutputFormat): Promise<void> {
    setDropdownOpen(false);
    setLoading(true);
    try {
      const response = await generateReport({
        carrier_id: carrierId,
        report_type: reportType,
        output_format: format,
        policy_id: policyId,
        run_id: runId,
      });
      setActiveFormat(format);
      setActiveJobId(response.job_id);
    } finally {
      setLoading(false);
    }
  }

  function handleRetry(): void {
    setActiveJobId(null);
    void requestGeneration(activeFormat);
  }

  // Determine button label
  const buttonLabel =
    label ??
    (excelOnly
      ? (label_reports("btn.export_excel", "report_export_excel") ?? "📊 Export Excel")
      : (label_reports("btn.generate", "report_generate") ?? "Generate Report"));

  // Policy audit without policyId — disable with tooltip
  const missingPolicyId = reportType === "policy_audit" && policyId == null;

  return (
    <>
      <div className="request-report-btn" ref={dropdownRef}>
        {excelOnly ? (
          /* Single button for Excel-only report types */
          <button
            type="button"
            className="btn btn--secondary"
            disabled={loading}
            onClick={() => void requestGeneration("excel")}
            data-testid="generate-report-btn"
          >
            {loading
              ? (label_shared("loading", "Loading…") ?? "Loading…")
              : buttonLabel}
          </button>
        ) : (
          /* Dropdown button for types that support both PDF and Excel */
          <button
            type="button"
            className="btn btn--secondary"
            disabled={loading || missingPolicyId}
            onClick={() => setDropdownOpen((prev) => !prev)}
            title={
              missingPolicyId
                ? (label_reports("msg.select_policy_first", "report_select_policy_first") ??
                  "Select a policy to generate this report")
                : undefined
            }
            data-testid={testId ?? "generate-report-btn"}
          >
            {loading ? (label_shared("loading", "Loading…") ?? "Loading…") : buttonLabel}{" "}
            {!loading && "▾"}
          </button>
        )}

        {dropdownOpen && !excelOnly && (
          <div
            className="request-report-btn__dropdown"
            role="menu"
            data-testid="report-format-dropdown"
          >
            <button
              type="button"
              role="menuitem"
              className="request-report-btn__option"
              onClick={() => void requestGeneration("pdf")}
              data-testid="format-pdf-option"
            >
              📄 {label_reports("format.pdf", "report_format_pdf") ?? "PDF Report"}
            </button>
            <button
              type="button"
              role="menuitem"
              className="request-report-btn__option"
              onClick={() => void requestGeneration("excel")}
              data-testid="format-excel-option"
            >
              📊 {label_reports("format.excel", "report_format_excel") ?? "Excel Report"}
            </button>
          </div>
        )}
      </div>

      {/* Report status modal — shown after successful job creation */}
      {activeJobId && (
        <ReportStatusModal
          jobId={activeJobId}
          reportType={reportType}
          outputFormat={activeFormat}
          policyNumber={policyNumber}
          onClose={() => setActiveJobId(null)}
          onRetry={handleRetry}
        />
      )}
    </>
  );
}
