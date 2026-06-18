

from __future__ import annotations

"""
ReportGenerationService — Phase 5.

Generates PDF (via WeasyPrint + Jinja2) and Excel (via openpyxl) reports.
All 5 report types per V9 S21.1.

Branding resolution chain (V9 S21.3 / V9 S14.2):
  1. carrier_report_templates.logo_url       (carrier-specific)
  2. tenant_branding.logo_url                (tenant default)
  3. None → text fallback "the Audit Platform"

Engine-derived fields (variance_pct, reported_pct, classified_pct, risk_level)
that are NULL render as "N/A" in ALL output formats — never as blank, "None",
0, or an error. This matches the NaIndicator behaviour in the UI.

PDF colour values:
  Always explicit hex from carrier_report_templates — never CSS custom properties.
  WeasyPrint renders HTML server-side with no DOM and no runtime JS, so
  CSS variables would resolve to empty strings.

Report types:
  1. policy_audit        — PDF + Excel. Full policy detail (all 4 tabs).
  2. book_summary        — PDF + Excel. All policies for a carrier.
  3. class_code_variance — Excel only. payroll_variance_class full export.
  4. ingestion_audit_trail — Excel only. ingestion_runs history.
  5. exception_report    — Excel only. ingestion_errors + skipped_rows for a run.
"""

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import jinja2
import structlog
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML as WeasyHTML

logger = structlog.get_logger(__name__)

# ── Report type → format constraints ──────────────────────────────────────────
# Excel-only report types cannot be requested as PDF.
EXCEL_ONLY_REPORT_TYPES: frozenset[str] = frozenset(
    {"class_code_variance", "ingestion_audit_trail", "exception_report"}
)

VALID_REPORT_TYPES: frozenset[str] = frozenset(
    {
        "policy_audit",
        "book_summary",
        "class_code_variance",
        "ingestion_audit_trail",
        "exception_report",
    }
)

VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"pdf", "excel"})

# ── Default branding colours (6-char hex, no #) ────────────────────────────────
DEFAULT_PRIMARY_COLOUR = "1A3C5E"
DEFAULT_SECONDARY_COLOUR = "2E86C1"


@dataclass
class ReportBranding:
    """Resolved branding values for a report. All colours are 6-char hex without #."""

    logo_url: Optional[str]
    primary_colour: str
    secondary_colour: str
    contact_block: Optional[str]
    carrier_name: str
    tenant_name: str
    generated_at: str


class ReportGenerationService:
    """
    Generates report bytes for all 5 report types.

    Does NOT write to S3 or update DB — that is ReportJobService's responsibility.
    Each generate_*() method returns (bytes, content_type, file_extension).
    """

    # ── Jinja2 environment ─────────────────────────────────────────────────────
    _jinja: jinja2.Environment = jinja2.Environment(
        loader=jinja2.PackageLoader("app", "templates"),
        autoescape=jinja2.select_autoescape(["html"]),
    )

    def __init__(self) -> None:
        # Register custom Jinja2 filters used in all templates
        self._jinja.filters["currency"] = self._fmt_currency
        self._jinja.filters["pct"] = self._fmt_pct

    # ── Input validation ───────────────────────────────────────────────────────

    @staticmethod
    def validate_report_request(
        report_type: str,
        output_format: str,
        policy_id: Optional[int],
        run_id: Optional[int],
    ) -> None:
        """
        Validates the report type / format combination and required parameters.
        Raises ValueError with a descriptive message for any invalid combination.
        These become HTTP 422 responses in the API router.
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Unknown report_type '{report_type}'")
        if output_format not in VALID_OUTPUT_FORMATS:
            raise ValueError(f"Unknown output_format '{output_format}'")
        if output_format == "pdf" and report_type in EXCEL_ONLY_REPORT_TYPES:
            raise ValueError(
                f"Report type '{report_type}' is Excel-only and cannot be generated as PDF"
            )
        if report_type == "policy_audit" and policy_id is None:
            raise ValueError("policy_id is required for report_type='policy_audit'")
        if report_type == "exception_report" and run_id is None:
            raise ValueError("run_id is required for report_type='exception_report'")
        if report_type == "ingestion_audit_trail" and run_id is None:
            raise ValueError(
                "run_id is required for report_type='ingestion_audit_trail'"
            )

    # ── Branding resolution (V9 S21.3) ────────────────────────────────────────

    async def get_branding(
        self,
        carrier_id: int,
        db: AsyncSession,
    ) -> ReportBranding:
        """
        Resolves branding for a report following the three-level chain:
          1. carrier_report_templates (carrier-specific — takes precedence)
          2. tenant_branding (tenant default)
          3. Hard defaults (text logo, default hex colours)
        """
        now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Level 1: carrier-specific template
        tmpl_result = await db.execute(
            text(
                "SELECT logo_url, primary_colour, secondary_colour, contact_block "
                "FROM carrier_report_templates WHERE carrier_id = :cid"
            ),
            {"cid": carrier_id},
        )
        tmpl = tmpl_result.fetchone()

        # Level 2: tenant branding (for logo fallback and carrier/tenant name)
        branding_result = await db.execute(
            text("SELECT logo_url, brand_color FROM tenant_branding LIMIT 1")
        )
        tenant_branding = branding_result.fetchone()

        # Carrier name
        carrier_result = await db.execute(
            text("SELECT carrier_name FROM carriers WHERE carrier_id = :cid"),
            {"cid": carrier_id},
        )
        carrier_row = carrier_result.fetchone()
        carrier_name = carrier_row[0] if carrier_row else "Unknown Carrier"

        # Tenant name — sourced from public.tenants (the platform-wide registry).
        # The column is `name`; `schema_name` ties the row to the current tenant schema.
        tenant_result = await db.execute(
            text(
                "SELECT name FROM public.tenants "
                "WHERE schema_name = current_schema() LIMIT 1"
            )
        )
        tenant_row = tenant_result.fetchone()
        tenant_name = tenant_row[0] if tenant_row else "Unknown Tenant"

        # Resolve logo URL: carrier template → tenant branding → None
        logo_url: Optional[str] = None
        if tmpl and tmpl[0]:
            logo_url = tmpl[0]
        elif tenant_branding and tenant_branding[0]:
            logo_url = tenant_branding[0]

        # Resolve colours: carrier template → defaults
        primary_colour = (
            tmpl[1] if tmpl and tmpl[1] else DEFAULT_PRIMARY_COLOUR
        )
        secondary_colour = (
            tmpl[2] if tmpl and tmpl[2] else DEFAULT_SECONDARY_COLOUR
        )
        contact_block: Optional[str] = tmpl[3] if tmpl and tmpl[3] else None

        return ReportBranding(
            logo_url=logo_url,
            primary_colour=primary_colour,
            secondary_colour=secondary_colour,
            contact_block=contact_block,
            carrier_name=carrier_name,
            tenant_name=tenant_name,
            generated_at=now_str,
        )

    # ── 1. Individual Policy Audit Report ─────────────────────────────────────

    async def generate_policy_audit(
        self,
        policy_id: int,
        carrier_id: int,
        output_format: str,
        run_id: Optional[int],
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """
        Generates an Individual Policy Audit Report (V9 S8.5 — all 4 tabs).

        Returns (bytes, content_type, file_extension).
        Engine-derived NULL fields render as N/A.
        """
        branding = await self.get_branding(carrier_id, db)

        # Policy record
        policy_result = await db.execute(
            text(
                "SELECT p.policy_id, p.policy_number, ph.name AS insured_name, p.state_code, "
                "p.effective_date, p.expiration_date, p.policy_status, p.payment_frequency, "
                "p.owner_status, p.audit_status, p.total_est_payroll, p.premium_written, "
                "p.risk_level "
                "FROM policies p "
                "JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id "
                "WHERE p.policy_id = :pid AND p.carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        policy_row = policy_result.fetchone()
        if policy_row is None:
            raise ValueError(f"Policy {policy_id} not found for carrier {carrier_id}")

        policy_data = {
            "policy_id": policy_row[0],
            "policy_number": policy_row[1],
            "insured_name": policy_row[2],
            "state_code": policy_row[3],
            "effective_date": str(policy_row[4]) if policy_row[4] else None,
            "expiration_date": str(policy_row[5]) if policy_row[5] else None,
            "policy_status": policy_row[6],
            "payment_frequency": policy_row[7],
            "owner_status": policy_row[8],
            "audit_status": policy_row[9],
            "total_est_payroll": policy_row[10],
            "premium_written": policy_row[11],
            "risk_level": policy_row[12],
        }

        # Premium variance (latest run if run_id not specified)
        pv_query = (
            "SELECT est_premium_end, actual_premium, variance_amount, variance_pct "
            "FROM premium_variance WHERE policy_id = :pid AND carrier_id = :cid "
            + ("AND ingestion_run_id = :rid " if run_id else "")
            + "ORDER BY as_of_date DESC LIMIT 1"
        )
        pv_params: dict[str, Any] = {"pid": policy_id, "cid": carrier_id}
        if run_id:
            pv_params["rid"] = run_id
        pv_result = await db.execute(text(pv_query), pv_params)
        pv_row = pv_result.fetchone()
        premium_variance = (
            {
                "est_premium_end": pv_row[0],
                "actual_premium": pv_row[1],
                "variance_amount": pv_row[2],
                "variance_pct": pv_row[3],
            }
            if pv_row
            else None
        )

        # Payroll variance by period.
        # payroll_variance_policy has no period_start/period_end/payment_frequency columns —
        # the date dimension is as_of_date; frequency lives on policies.payment_frequency.
        # NULL placeholders keep the dict shape consistent for templates.
        pvp_result = await db.execute(
            text(
                "SELECT as_of_date, NULL AS period_end, NULL AS payment_frequency, "
                "est_payroll, actual_payroll_reported, reported_over_under, reported_pct "
                "FROM payroll_variance_policy "
                "WHERE policy_id = :pid AND carrier_id = :cid "
                "ORDER BY as_of_date ASC"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        payroll_variances = [
            {
                "period_start": str(r[0]) if r[0] else None,
                "period_end": str(r[1]) if r[1] else None,
                "payment_frequency": r[2],
                "est_payroll": r[3],
                "actual_reported": r[4],
                "reported_over_under": r[5],
                "reported_pct": r[6],
            }
            for r in pvp_result.fetchall()
        ]

        # Class code variance.
        # payroll_variance_class stores class_code_id (FK → public.class_codes).
        # JOIN to public.class_codes to resolve the human-readable code text.
        pvc_result = await db.execute(
            text(
                "SELECT pvc.state_code, cc.code AS class_code, "
                "pvc.est_payroll, pvc.actual_reported, "
                "pvc.reported_over_under, pvc.reported_pct, pvc.actual_classified, "
                "pvc.classified_over_under, pvc.classified_pct "
                "FROM payroll_variance_class pvc "
                "JOIN public.class_codes cc ON cc.class_code_id = pvc.class_code_id "
                "WHERE pvc.policy_id = :pid AND pvc.carrier_id = :cid "
                "ORDER BY pvc.state_code, cc.code"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        class_codes = [
            {
                "state_code": r[0],
                "class_code": r[1],
                "est_payroll": r[2],
                "actual_reported": r[3],
                "reported_over_under": r[4],
                "reported_pct": r[5],
                "actual_classified": r[6],
                "classified_over_under": r[7],
                "classified_pct": r[8],
            }
            for r in pvc_result.fetchall()
        ]

        # Missing payrolls.
        # Column names: period_start / period_end / days_since_last_run
        # (not expected_period_start / expected_period_end / days_overdue).
        mp_result = await db.execute(
            text(
                "SELECT period_start, period_end, days_since_last_run "
                "FROM missing_payroll WHERE policy_id = :pid AND carrier_id = :cid "
                "ORDER BY period_start"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        missing_payrolls = [
            {
                "expected_period_start": str(r[0]) if r[0] else None,
                "expected_period_end": str(r[1]) if r[1] else None,
                "days_overdue": r[2],
            }
            for r in mp_result.fetchall()
        ]

        # Zero payrolls.
        # zero_payroll only has: report_date, payroll_frequency, state_code.
        # The columns reason_code / other_reason / payroll_vendor / sprs_flag / agency_name
        # do not exist in this schema — NULL placeholders preserve the dict shape for templates.
        zp_result = await db.execute(
            text(
                "SELECT report_date, "
                "NULL AS reason_code, NULL AS other_reason, "
                "NULL AS payroll_vendor, NULL AS sprs_flag, NULL AS agency_name "
                "FROM zero_payroll WHERE policy_id = :pid AND carrier_id = :cid "
                "ORDER BY report_date DESC"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        zero_payrolls = [
            {
                "report_date": str(r[0]) if r[0] else None,
                "reason_code": r[1],
                "other_reason": r[2],
                "payroll_vendor": r[3],
                "sprs_flag": r[4],
                "agency_name": r[5],
            }
            for r in zp_result.fetchall()
        ]

        # ── AI narrative ─────────────────────────────────────────────────────────
        # Strategy (three-level cascade):
        #
        # 1. If run_id is explicitly provided, read narrative directly from that
        #    ingestion_runs row — this is the most reliable path and avoids any
        #    run_id vs ingestion_run_id mismatch.
        #
        # 2. If run_id is not provided, find the most recent ingestion_runs row
        #    for this carrier that has narrative_text set, regardless of which
        #    premium_variance row it was linked through.
        #
        # 3. Final fallback: scan all ingestion_runs for this carrier ordered by
        #    run_id DESC — catches cases where the JOIN via premium_variance would
        #    miss the row due to ingestion_run_id / audit_run_id mismatch.
        #
        # The previous JOIN-only approach failed when:
        #   - Multiple premium_variance rows exist per policy (different run_ids)
        #   - The audit run used a run_id not present in premium_variance
        narrative_text: str | None = None
        narrative_is_fallback: bool = False

        if run_id is not None:
            # Level 1: direct lookup by explicit run_id
            narr_direct = await db.execute(
                text(
                    "SELECT narrative_text, narrative_is_fallback "
                    "FROM ingestion_runs "
                    "WHERE run_id = :rid AND narrative_text IS NOT NULL"
                ),
                {"rid": run_id},
            )
            narr_row = narr_direct.fetchone()
            if narr_row:
                narrative_text = (narr_row[0] or "").strip() or None
                narrative_is_fallback = bool(narr_row[1])

        if narrative_text is None:
            # Level 2: most recent run for this carrier that has a narrative
            narr_carrier = await db.execute(
                text(
                    """
                    SELECT ir.narrative_text, ir.narrative_is_fallback
                    FROM ingestion_runs ir
                    JOIN premium_variance pv
                      ON pv.ingestion_run_id = ir.run_id
                    WHERE pv.policy_id  = :pid
                      AND pv.carrier_id = :cid
                      AND ir.narrative_text IS NOT NULL
                    ORDER BY ir.run_id DESC
                    LIMIT 1
                    """
                ),
                {"pid": policy_id, "cid": carrier_id},
            )
            narr_row2 = narr_carrier.fetchone()
            if narr_row2:
                narrative_text = (narr_row2[0] or "").strip() or None
                narrative_is_fallback = bool(narr_row2[1])

        if narrative_text is None:
            # Level 3: scan all carrier runs joined through policies table
            # to guarantee the narrative belongs to THIS specific policy.
            # This prevents bulk-uploaded policies from inheriting the
            # most-recent narrative across all policies for the carrier.
            narr_fallback = await db.execute(
                text(
                    """
                    SELECT ir.narrative_text, ir.narrative_is_fallback
                    FROM ingestion_runs ir
                    JOIN premium_variance pv ON pv.ingestion_run_id = ir.run_id
                    WHERE ir.carrier_id = :cid
                      AND pv.policy_id  = :pid
                      AND ir.narrative_text IS NOT NULL
                    ORDER BY ir.run_id DESC
                    LIMIT 1
                    """
                ),
                {"cid": carrier_id, "pid": policy_id},
            )
            narr_row3 = narr_fallback.fetchone()
            if narr_row3:
                narrative_text = (narr_row3[0] or "").strip() or None
                narrative_is_fallback = bool(narr_row3[1])

            # Level 4 (absolute last resort): only if no policy-specific narrative
            # exists at all — e.g. calc engine was never run for this policy.
            # Returns None so the report shows "narrative not available" rather
            # than showing another policy's narrative.
            # (No carrier-wide fallback — that caused cross-policy contamination.)

        if output_format == "pdf":
            ctx = {
                # Branding
                "primary_colour": branding.primary_colour,
                "secondary_colour": branding.secondary_colour,
                "logo_url": branding.logo_url,
                "contact_block": branding.contact_block,
                "carrier_name": branding.carrier_name,
                "tenant_name": branding.tenant_name,
                "generated_at": branding.generated_at,
                # Data
                "policy": policy_data,
                "premium_variance": premium_variance,
                "payroll_variances": payroll_variances,
                "class_codes": class_codes,
                "missing_payrolls": missing_payrolls,
                "zero_payrolls": zero_payrolls,
                "narrative": narrative_text,
                "narrative_is_fallback": narrative_is_fallback,
            }
            pdf_bytes = self._render_pdf("reports/policy_audit.html", ctx)
            return pdf_bytes, "application/pdf", "pdf"

        # Excel format
        wb, ws = self._new_excel_workbook(branding, "Policy Audit")
        self._write_excel_branding_row(
            ws,
            branding,
            f"Individual Policy Audit — {policy_data['policy_number']}",
            col_count=8,
        )

        # Policy info section
        self._write_section_header(ws, "Policy Information", col_count=8)
        info_rows = [
            ("Policy Number", policy_data["policy_number"]),
            ("Insured Name", policy_data["insured_name"]),
            ("State", policy_data["state_code"] or "—"),
            ("Status", policy_data["policy_status"]),
            ("Effective Date", policy_data["effective_date"] or "—"),
            ("Expiration Date", policy_data["expiration_date"] or "—"),
            ("Premium Written", policy_data["premium_written"]),
            ("Total Est. Payroll", policy_data["total_est_payroll"]),
            ("Risk Level", policy_data["risk_level"]),
            ("Audit Status", policy_data["audit_status"]),
        ]
        for label, value in info_rows:
            ws.append([label, self._na_or_value(value)])
        ws.append([])

        # Premium variance
        if premium_variance:
            self._write_section_header(ws, "Premium Variance", col_count=8)
            headers = ["Est Premium End", "Actual Premium", "Variance $", "Variance %"]
            self._write_excel_header(ws, headers, branding)
            ws.append([
                self._na_or_currency(premium_variance["est_premium_end"]),
                self._na_or_currency(premium_variance["actual_premium"]),
                self._na_or_currency(premium_variance["variance_amount"]),
                self._na_or_pct(premium_variance["variance_pct"]),
            ])
            self._apply_variance_colour(ws, ws.max_row, col_index=3)
            ws.append([])

        # Class codes
        if class_codes:
            self._write_section_header(ws, "Class Code Variance", col_count=9)
            self._write_excel_header(
                ws,
                ["State", "Class Code", "Est Payroll", "Act Reported",
                 "Rep Over/Under", "Rep %", "Act Classified", "Class Over/Under", "Class %"],
                branding,
            )
            for r in class_codes:
                row = [
                    r["state_code"], r["class_code"],
                    self._na_or_currency(r["est_payroll"]),
                    self._na_or_currency(r["actual_reported"]),
                    self._na_or_currency(r["reported_over_under"]),
                    self._na_or_pct(r["reported_pct"]),
                    self._na_or_currency(r["actual_classified"]),
                    self._na_or_currency(r["classified_over_under"]),
                    self._na_or_pct(r["classified_pct"]),
                ]
                ws.append(row)
                self._apply_variance_colour(ws, ws.max_row, col_index=5)
                self._apply_variance_colour(ws, ws.max_row, col_index=8)
            ws.append([])

        # ── Payroll variance by period ──────────────────────────────────────────
        if payroll_variances:
            self._write_section_header(ws, "Payroll Variance by Period", col_count=8)
            self._write_excel_header(
                ws,
                ["Period Start", "Period End", "Frequency",
                 "Est Payroll", "Act Reported", "Reported Over/Under", "Reported %"],
                branding,
            )
            for r in payroll_variances:
                ws.append([
                    r["period_start"] or "—",
                    r["period_end"] or "—",
                    r["payment_frequency"] or "—",
                    self._na_or_currency(r["est_payroll"]),
                    self._na_or_currency(r["actual_reported"]),
                    self._na_or_currency(r["reported_over_under"]),
                    self._na_or_pct(r["reported_pct"]),
                ])
                self._apply_variance_colour(ws, ws.max_row, col_index=6)
            ws.append([])

        # ── Missing payrolls ─────────────────────────────────────────────────────
        if missing_payrolls:
            self._write_section_header(ws, "Missing Payrolls", col_count=8)
            self._write_excel_header(
                ws,
                ["Expected Period Start", "Expected Period End", "Days Overdue"],
                branding,
            )
            for r in missing_payrolls:
                ws.append([
                    r["expected_period_start"] or "—",
                    r["expected_period_end"] or "—",
                    r["days_overdue"] if r["days_overdue"] is not None else "—",
                ])
            ws.append([])

        # ── Zero payrolls ────────────────────────────────────────────────────────
        if zero_payrolls:
            self._write_section_header(ws, "Zero Payroll Reports", col_count=8)
            self._write_excel_header(
                ws,
                ["Report Date", "Reason", "Payroll Vendor", "SPRS?", "Agency"],
                branding,
            )
            for r in zero_payrolls:
                ws.append([
                    r["report_date"] or "—",
                    r["reason_code"] or r["other_reason"] or "—",
                    r["payroll_vendor"] or "—",
                    "Yes" if r["sprs_flag"] else "No",
                    r["agency_name"] or "—",
                ])
            ws.append([])

        # ── AI Narrative ─────────────────────────────────────────────────────────
        if narrative_text:
            self._write_section_header(ws, "Audit Narrative (AI Generated)", col_count=8)

            # Fallback notice row
            if narrative_is_fallback:
                ws.append(["⚠ This narrative was generated using a template "
                           "(AI service was unavailable at time of audit run)."])
                notice_cell = ws.cell(row=ws.max_row, column=1)
                notice_cell.font = Font(
                    color="E67E22", italic=True, name="Arial", size=9
                )
                ws.merge_cells(
                    start_row=ws.max_row, start_column=1,
                    end_row=ws.max_row,   end_column=8,
                )

            # Narrative text — written into a single merged tall cell so it
            # wraps naturally inside Excel without being clipped.
            ws.append([narrative_text])
            narrative_cell = ws.cell(row=ws.max_row, column=1)
            narrative_cell.font      = Font(name="Arial", size=10)
            narrative_cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(
                start_row=ws.max_row, start_column=1,
                end_row=ws.max_row,   end_column=8,
            )
            # Estimate row height: ~15pt per line, ~80 chars per line at this width
            char_per_line = 80
            lines = max(3, len(narrative_text) // char_per_line + 1)
            ws.row_dimensions[ws.max_row].height = lines * 15
            ws.append([])

        self._auto_fit_columns(ws)
        excel_bytes = self._workbook_to_bytes(wb)
        return (
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    # ── 2. Policy Book Summary ─────────────────────────────────────────────────

    async def generate_book_summary(
        self,
        carrier_id: int,
        output_format: str,
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """
        Generates a Policy Book Summary for all policies in a carrier.
        Per V9 S8.4 — matches the Policies List columns.
        """
        branding = await self.get_branding(carrier_id, db)

        policies_result = await db.execute(
            text(
                "SELECT p.policy_id, p.policy_number, ph.name AS insured_name, p.state_code, "
                "p.effective_date, p.expiration_date, p.policy_status, "
                "p.premium_written, pv.variance_amount, pv.variance_pct, "
                "p.risk_level, p.audit_status "
                "FROM policies p "
                "JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id "
                "LEFT JOIN LATERAL ( "
                "  SELECT variance_amount, variance_pct "
                "  FROM premium_variance "
                "  WHERE policy_id = p.policy_id AND carrier_id = p.carrier_id "
                "  ORDER BY as_of_date DESC LIMIT 1 "
                ") pv ON TRUE "
                "WHERE p.carrier_id = :cid "
                "ORDER BY p.policy_number"
            ),
            {"cid": carrier_id},
        )
        policies = [
            {
                "policy_number": r[1],
                "insured_name": r[2],
                "state_code": r[3],
                "effective_date": str(r[4]) if r[4] else None,
                "expiration_date": str(r[5]) if r[5] else None,
                "policy_status": r[6],
                "premium_written": r[7],
                "variance_amount": r[8],
                "variance_pct": r[9],
                "risk_level": r[10],
                "audit_status": r[11],
            }
            for r in policies_result.fetchall()
        ]

        total_premium_written = sum(
            p["premium_written"] for p in policies if p["premium_written"] is not None
        )
        high_risk_count = sum(1 for p in policies if p.get("risk_level") == "HIGH")
        open_audit_count = sum(
            1 for p in policies if p.get("audit_status") not in ("closed", "complete")
        )

        if output_format == "pdf":
            ctx = {
                "primary_colour": branding.primary_colour,
                "secondary_colour": branding.secondary_colour,
                "logo_url": branding.logo_url,
                "contact_block": branding.contact_block,
                "carrier_name": branding.carrier_name,
                "tenant_name": branding.tenant_name,
                "generated_at": branding.generated_at,
                "policies": policies,
                "total_premium_written": total_premium_written,
                "high_risk_count": high_risk_count,
                "open_audit_count": open_audit_count,
            }
            pdf_bytes = self._render_pdf("reports/book_summary.html", ctx)
            return pdf_bytes, "application/pdf", "pdf"

        # Excel format
        wb, ws = self._new_excel_workbook(branding, "Policy Book Summary")
        self._write_excel_branding_row(ws, branding, "Policy Book Summary", col_count=11)
        self._write_excel_header(
            ws,
            [
                "Policy #", "Insured Name", "State", "Effective", "Expiration",
                "Status", "Premium Written", "Variance $", "Variance %",
                "Risk Level", "Audit Status",
            ],
            branding,
        )
        for p in policies:
            row = [
                p["policy_number"],
                p["insured_name"],
                p["state_code"] or "—",
                p["effective_date"] or "—",
                p["expiration_date"] or "—",
                p["policy_status"],
                self._na_or_currency(p["premium_written"]),
                self._na_or_currency(p["variance_amount"]),
                self._na_or_pct(p["variance_pct"]),
                p["risk_level"] if p["risk_level"] else "N/A",
                p["audit_status"] or "—",
            ]
            ws.append(row)
            self._apply_variance_colour(ws, ws.max_row, col_index=8)

        self._auto_fit_columns(ws)
        excel_bytes = self._workbook_to_bytes(wb)
        return (
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    # ── 3. Class Code Variance Export ─────────────────────────────────────────

    async def generate_class_code_variance(
        self,
        carrier_id: int,
        run_id: Optional[int],
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """
        Excel export of payroll_variance_class for all policies.
        Excel-only — PDF format is not supported and will raise ValueError.
        """
        branding = await self.get_branding(carrier_id, db)

        query = text(
            "SELECT p.policy_number, ph.name AS insured_name, "
            "pvc.state_code, cc.code AS class_code, "
            "pvc.est_payroll, pvc.actual_reported, "
            "pvc.reported_over_under, pvc.reported_pct, "
            "pvc.actual_classified, pvc.classified_over_under, pvc.classified_pct "
            "FROM payroll_variance_class pvc "
            "JOIN policies p ON p.policy_id = pvc.policy_id "
            "JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id "
            "JOIN public.class_codes cc ON cc.class_code_id = pvc.class_code_id "
            "WHERE pvc.carrier_id = :cid "
            + ("AND pvc.ingestion_run_id = :rid " if run_id else "")
            + "ORDER BY p.policy_number, pvc.state_code, cc.code"
        )
        params: dict[str, Any] = {"cid": carrier_id}
        if run_id:
            params["rid"] = run_id
        result = await db.execute(query, params)
        rows = result.fetchall()

        wb, ws = self._new_excel_workbook(branding, "Class Code Variance")
        self._write_excel_branding_row(ws, branding, "Class Code Variance Export", col_count=11)
        self._write_excel_header(
            ws,
            [
                "Policy #", "Insured Name", "State", "Class Code",
                "Est Payroll", "Act Reported", "Rep Over/Under", "Rep %",
                "Act Classified", "Class Over/Under", "Class %",
            ],
            branding,
        )
        for r in rows:
            ws.append([
                r[0], r[1], r[2], r[3],
                self._na_or_currency(r[4]),
                self._na_or_currency(r[5]),
                self._na_or_currency(r[6]),
                self._na_or_pct(r[7]),
                self._na_or_currency(r[8]),
                self._na_or_currency(r[9]),
                self._na_or_pct(r[10]),
            ])
            self._apply_variance_colour(ws, ws.max_row, col_index=7)
            self._apply_variance_colour(ws, ws.max_row, col_index=10)

        self._auto_fit_columns(ws)
        excel_bytes = self._workbook_to_bytes(wb)
        return (
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    # ── 4. Ingestion Run Audit Trail ───────────────────────────────────────────

    async def generate_ingestion_audit_trail(
        self,
        carrier_id: int,
        run_id: Optional[int],
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """
        Excel export of ingestion_runs history.
        Includes status, row counts, engine mode, timestamps.
        Excel-only.
        """
        branding = await self.get_branding(carrier_id, db)

        query_str = (
            "SELECT ir.run_id, ir.source_id, ins.source_name, "
            "ir.status, ir.rows_ingested, ir.rows_skipped, ir.rows_failed, "
            "ir.started_at, ir.completed_at, ir.use_calculation_engine, ir.skip_on_error "
            "FROM ingestion_runs ir "
            "LEFT JOIN ingestion_sources ins ON ins.source_id = ir.source_id "
            "WHERE ir.carrier_id = :cid "
            + ("AND ir.run_id = :rid " if run_id else "")
            + "ORDER BY ir.started_at DESC"
        )
        params: dict[str, Any] = {"cid": carrier_id}
        if run_id:
            params["rid"] = run_id
        result = await db.execute(text(query_str), params)
        rows = result.fetchall()

        wb, ws = self._new_excel_workbook(branding, "Ingestion Audit Trail")
        self._write_excel_branding_row(
            ws, branding, "Ingestion Run Audit Trail", col_count=11
        )
        self._write_excel_header(
            ws,
            [
                "Run ID", "Source ID", "Source Name", "Status",
                "Rows Ingested", "Rows Skipped", "Rows Failed",
                "Started At", "Completed At", "Calc Engine", "Skip on Error",
            ],
            branding,
        )
        for r in rows:
            # r[9] = use_calculation_engine (Boolean | None)
            engine_display = (
                "Enabled" if r[9] is True
                else "Disabled" if r[9] is False
                else "N/A"
            )
            ws.append([
                r[0], r[1],
                r[2] or "—",
                r[3],
                r[4] if r[4] is not None else "N/A",   # rows_ingested
                r[5] if r[5] is not None else "N/A",   # rows_skipped
                r[6] if r[6] is not None else "N/A",   # rows_failed
                str(r[7]) if r[7] else "—",             # started_at
                str(r[8]) if r[8] else "—",             # completed_at
                engine_display,
                "Yes" if r[10] else "No",
            ])

        self._auto_fit_columns(ws)
        excel_bytes = self._workbook_to_bytes(wb)
        return (
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    # ── 5. Exception Report ────────────────────────────────────────────────────

    async def generate_exception_report(
        self,
        carrier_id: int,
        run_id: int,
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """
        Excel export with two sheets:
          Sheet 1 — 'Ingestion Errors': rows from ingestion_errors
          Sheet 2 — 'Skipped Rows': rows from ingestion_skipped_rows
        Excel-only.
        """
        branding = await self.get_branding(carrier_id, db)

        wb = Workbook()

        # ── Sheet 1: Ingestion Errors ──────────────────────────────────────
        ws_errors = wb.active
        ws_errors.title = "Ingestion Errors"

        self._write_excel_branding_row(
            ws_errors, branding,
            f"Ingestion Errors — Run {run_id}",
            col_count=6,
        )
        self._write_excel_header(
            ws_errors,
            ["Error ID", "Row Number", "Error Code", "Error Message",
             "Field Name", "Raw Value"],
            branding,
        )

        errors_result = await db.execute(
            text(
                "SELECT error_id, row_number, error_code, error_message, "
                "field_name, raw_value "
                "FROM ingestion_errors WHERE run_id = :rid "
                "ORDER BY row_number, error_id"
            ),
            {"rid": run_id},
        )
        for r in errors_result.fetchall():
            ws_errors.append([
                r[0], r[1] if r[1] is not None else "N/A",
                r[2] or "—", r[3] or "—",
                r[4] or "—", r[5] or "—",
            ])
        self._auto_fit_columns(ws_errors)

        # ── Sheet 2: Skipped Rows ──────────────────────────────────────────
        ws_skipped = wb.create_sheet("Skipped Rows")

        self._write_excel_branding_row(
            ws_skipped, branding,
            f"Skipped Rows — Run {run_id}",
            col_count=6,
        )
        self._write_excel_header(
            ws_skipped,
            ["Skip ID", "Row Number", "Skip Reason", "Raw Row Data",
             "Resolution Status", "Resolved At"],
            branding,
        )

        skipped_result = await db.execute(
            text(
                "SELECT skip_id, row_number, skip_reason, raw_row_data, "
                "resolution_status, resolved_at "
                "FROM ingestion_skipped_rows WHERE run_id = :rid "
                "ORDER BY row_number"
            ),
            {"rid": run_id},
        )
        for r in skipped_result.fetchall():
            raw_data = r[3]
            raw_display = str(raw_data)[:500] if raw_data else "—"
            ws_skipped.append([
                r[0], r[1] if r[1] is not None else "N/A",
                r[2] or "—", raw_display,
                r[4] or "—",
                str(r[5]) if r[5] else "—",
            ])
        self._auto_fit_columns(ws_skipped)

        excel_bytes = self._workbook_to_bytes(wb)
        return (
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    # ── PDF rendering ──────────────────────────────────────────────────────────

    def _render_pdf(self, template_name: str, ctx: dict[str, Any]) -> bytes:
        """Renders a Jinja2 template → HTML string → WeasyPrint → PDF bytes."""
        template = self._jinja.get_template(template_name)
        html_str = template.render(**ctx)
        return WeasyHTML(string=html_str).write_pdf()  # type: ignore[no-any-return]

    # ── Excel helpers ──────────────────────────────────────────────────────────

    def _new_excel_workbook(
        self, branding: ReportBranding, sheet_name: str
    ) -> tuple[Workbook, Any]:
        """Creates an openpyxl Workbook with the active sheet named sheet_name."""
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name  # type: ignore[union-attr]
        return wb, ws

    def _write_excel_branding_row(
        self,
        ws: Any,
        branding: ReportBranding,
        report_title: str,
        col_count: int,
    ) -> None:
        """
        Writes Row 1: merged branding header with carrier name, report title,
        and generated date. Uses primary_colour fill, white bold text.
        """
        header_fill = PatternFill(
            fill_type="solid", fgColor=branding.primary_colour or DEFAULT_PRIMARY_COLOUR
        )
        header_font = Font(bold=True, color="FFFFFF", name="Arial", size=11)

        label = f"{branding.carrier_name} | {report_title} | {branding.generated_at}"
        ws.append([label])
        ws.merge_cells(
            start_row=ws.max_row,
            start_column=1,
            end_row=ws.max_row,
            end_column=col_count,
        )
        cell = ws.cell(row=ws.max_row, column=1)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[ws.max_row].height = 22

    def _write_excel_header(
        self, ws: Any, headers: list[str], branding: ReportBranding
    ) -> None:
        """
        Writes a styled column header row.
        Fill: primary_colour. Text: white, bold, Arial 10pt.
        """
        header_fill = PatternFill(
            fill_type="solid", fgColor=branding.primary_colour or DEFAULT_PRIMARY_COLOUR
        )
        header_font = Font(bold=True, color="FFFFFF", name="Arial", size=10)

        ws.append(headers)
        header_row = ws.max_row
        for col_idx, _ in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="left", vertical="center")

    def _write_section_header(
        self, ws: Any, title: str, col_count: int
    ) -> None:
        """Writes a section separator row with bold text."""
        ws.append([title])
        cell = ws.cell(row=ws.max_row, column=1)
        cell.font = Font(bold=True, name="Arial", size=10)
        ws.merge_cells(
            start_row=ws.max_row,
            start_column=1,
            end_row=ws.max_row,
            end_column=col_count,
        )

    def _apply_variance_colour(
        self, ws: Any, row_number: int, col_index: int
    ) -> None:
        """
        Applies green (1E8449) or red (C0392B) font to a numeric cell
        based on whether its value is >= 0 or < 0.
        Cells containing "N/A" are coloured grey (7F8C8D).
        """
        cell = ws.cell(row=row_number, column=col_index)
        value = cell.value
        if value == "N/A":
            cell.font = Font(color="7F8C8D", italic=True, name="Arial", size=10)
        elif isinstance(value, (int, float, Decimal)):
            colour = "1E8449" if float(value) >= 0 else "C0392B"
            cell.font = Font(color=colour, bold=True, name="Arial", size=10)

    def _auto_fit_columns(self, ws: Any) -> None:
        """Sets column widths based on maximum cell content length (min 10, max 50)."""
        for col in ws.columns:
            max_length = 10
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    cell_len = len(str(cell.value)) if cell.value is not None else 0
                    max_length = max(max_length, cell_len)
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

    def _apply_na_grey(self, ws: Any, row_number: int, col_index: int) -> None:
        """Applies grey italic font to N/A cells."""
        cell = ws.cell(row=row_number, column=col_index)
        if cell.value == "N/A":
            cell.font = Font(color="7F8C8D", italic=True, name="Arial", size=10)

    @staticmethod
    def _workbook_to_bytes(wb: Workbook) -> bytes:
        """Serialises an openpyxl Workbook to bytes without touching the filesystem."""
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # ── Value formatters ───────────────────────────────────────────────────────
    # Used as both Jinja2 filters (for PDF) and direct helpers (for Excel).

    @staticmethod
    def _fmt_currency(value: Any) -> str:
        """Formats a numeric value as a currency string. Returns 'N/A' for None."""
        if value is None:
            return "N/A"
        return f"${float(value):,.2f}"

    @staticmethod
    def _fmt_pct(value: Any) -> str:
        """Formats a numeric value as a percentage string. Returns 'N/A' for None."""
        if value is None:
            return "N/A"
        return f"{float(value):.2f}%"

    @staticmethod
    def _na_or_value(value: Any) -> Any:
        """Returns 'N/A' string if value is None, otherwise the value unchanged."""
        return "N/A" if value is None else value

    @staticmethod
    def _na_or_currency(value: Any) -> str:
        """Returns formatted currency string or 'N/A' for None."""
        if value is None:
            return "N/A"
        return f"${float(value):,.2f}"

    @staticmethod
    def _na_or_pct(value: Any) -> str:
        """Returns formatted percentage string or 'N/A' for None."""
        if value is None:
            return "N/A"
        return f"{float(value):.2f}%"