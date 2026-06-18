


from __future__ import annotations

"""
AutoMappingService — Phase 3.

4-pass confidence scoring for source file columns vs canonical DB columns.

Pass 1: Saved mapping in ingestion_field_maps  → HIGH  (score 1.000)
Pass 2: Normalised name equality               → HIGH  (score 0.950)
Pass 3: Fuzzy ratio + type compatibility       → MEDIUM (≥0.75) | LOW (0.50–0.75)
Pass 4: No match                               → UNMATCHED (score 0.000)

Creates a field_mapping_session + N field_mapping_proposals rows.
Returns session_id. Does NOT write to fact tables.

File type support:
  - XLSX: payroll detail, audit report, premium var, PR var, payroll var,
          missing PR, zero PR
  - XML:  PPlus policy XML
"""

import difflib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from io import BytesIO
from typing import Optional

import openpyxl
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.text_utils import infer_type, normalise, types_are_compatible

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Canonical target columns
# Covers every fact table column that can be ingested from any file type.
# ---------------------------------------------------------------------------

CANONICAL_COLUMNS: dict[str, str] = {
    # policies / policyholders
    "policy_number":             "TEXT",
    "insured_name":              "TEXT",
    "fein":                      "TEXT",
    "state_code":                "TEXT",
    "effective_date":            "DATE",
    "expiration_date":           "DATE",
    "cancellation_date":         "DATE",
    "premium_written":           "NUMERIC",
    "payment_frequency":         "TEXT",
    "owner_status":              "TEXT",
    "policy_status":             "TEXT",
    # premium_variance
    "actual_premium":            "NUMERIC",
    "est_premium_end":           "NUMERIC",
    "premium_as_written":        "NUMERIC",
    # payroll_variance_policy
    "est_payroll":               "NUMERIC",
    "actual_payroll_reported":   "NUMERIC",
    "actual_payroll_classified": "NUMERIC",
    "as_of_date":                "DATE",
    # payroll_variance_class (per-employee detail)
    "class_code":                "TEXT",
    "wages":                     "NUMERIC",
    "overtime":                  "NUMERIC",
    "exposure":                  "NUMERIC",
    "net_rate":                  "NUMERIC",
    "earned_premium":            "NUMERIC",
    # zero_payroll
    "report_date":               "DATE",
    "reason_code":               "TEXT",
    "other_reason":              "TEXT",
    "payroll_vendor":            "TEXT",
    "sprs_flag":                 "BOOLEAN",
    "agency_name":               "TEXT",
    # missing_payroll
    "expected_period_start":     "DATE",
    "expected_period_end":       "DATE",
    "days_overdue":              "INTEGER",
    "notice_instance":           "INTEGER",
}

# ---------------------------------------------------------------------------
# Source column → canonical name aliases
# Key = normalised version of what appears in real files
# Value = canonical column name
# ---------------------------------------------------------------------------

KNOWN_ALIASES: dict[str, str] = {
    # ── Payroll detail ────────────────────────────────────────────────────
    "client name":                    "insured_name",
    "clientname":                     "insured_name",
    "clientnam":                      "insured_name",
    "insured name":                   "insured_name",
    "insuredname":                    "insured_name",
    "insured":                        "insured_name",
    "insurednm":                      "insured_name",
    "policyholder":                   "insured_name",
    "provider":                       "insured_name",
    "carrier name":                   "insured_name",
    "carriername":                    "insured_name",
    "policy number":                  "policy_number",
    "policynumber":                   "policy_number",
    "policynum":                      "policy_number",
    "policyno":                       "policy_number",
    "fein":                           "fein",
    "tax id":                         "fein",
    "ein":                            "fein",
    "check date":                     "as_of_date",
    "checkdate":                      "as_of_date",
    "process date":                   "as_of_date",
    "processdate":                    "as_of_date",
    "effective date":                 "effective_date",
    "effectivedate":                  "effective_date",
    "policy effective date":          "effective_date",
    "policyeffectivedate":            "effective_date",
    "pol eff  date":                  "effective_date",
    "pol eff date":                   "effective_date",
    "poleffdate":                     "effective_date",
    "class effective date":           "effective_date",
    "policy expiration date":         "expiration_date",
    "policyexpirationdate":           "expiration_date",
    "pol exp date":                   "expiration_date",
    "policyexpdate":                  "expiration_date",
    "expiration date":                "expiration_date",
    "class expiration date":          "expiration_date",
    "cancellation date":              "cancellation_date",
    "cancellationdate":               "cancellation_date",
    "payment cycle":                  "payment_frequency",
    "paymentcycle":                   "payment_frequency",
    "payment frequency":              "payment_frequency",
    "paymentfrequency":               "payment_frequency",
    "policy status":                  "policy_status",
    "policystatus":                   "policy_status",
    "st":                             "state_code",
    "state":                          "state_code",
    "state code":                     "state_code",
    "statecode":                      "state_code",
    "class code":                     "class_code",
    "classcode":                      "class_code",
    "wages":                          "wages",
    "ot":                             "overtime",
    "overtime":                       "overtime",
    "exposure":                       "exposure",
    "net rate":                       "net_rate",
    "netrate":                        "net_rate",
    "net rate per":                   "net_rate",
    "netrateper":                     "net_rate",
    "earned prem":                    "earned_premium",
    "earned prem ":                   "earned_premium",
    "earnedprem":                     "earned_premium",
    "earned premium":                 "earned_premium",
    "census rate":                    "net_rate",
    "censorrate":                     "net_rate",
    "census prem ":                   "earned_premium",
    "censusprem":                     "earned_premium",
    # ── Premium Var ───────────────────────────────────────────────────────
    "policy premium as written":      "premium_as_written",
    "policypremiumaswritten":         "premium_as_written",
    "policypremiumaswrittenfu":       "premium_as_written",
    "actual premium to date":         "actual_premium",
    "actualpremiumtodate":            "actual_premium",
    "estimated premium to  end date": "est_premium_end",
    "estimated premium to end date":  "est_premium_end",
    "estimatedpremiumtoenddate":      "est_premium_end",
    "estimatedpremiumtoend":          "est_premium_end",
    # ── PR Var / Payroll Var ──────────────────────────────────────────────
    "carrier":                        "insured_name",
    "estimated payroll":              "est_payroll",
    "estimatedpayroll":               "est_payroll",
    "actual payroll as reported":     "actual_payroll_reported",
    "actualpayrollasreported":        "actual_payroll_reported",
    "actualpayrollasreporte":         "actual_payroll_reported",
    "actual payroll as classified":   "actual_payroll_classified",
    "actualpayrollasclassified":      "actual_payroll_classified",
    # ── Missing PR ────────────────────────────────────────────────────────
    "days since report date":         "days_overdue",
    "dayssincereportdate":            "days_overdue",
    "notice instance":                "notice_instance",
    "noticeinstance":                 "notice_instance",
    "payroll vendor":                 "payroll_vendor",
    "payrollvendor":                  "payroll_vendor",
    "sprs enabled":                   "sprs_flag",
    "sprsenabled":                    "sprs_flag",
    # ── Zero PR ───────────────────────────────────────────────────────────
    "report date":                    "report_date",
    "reportdate":                     "report_date",
    "zero payroll reason":            "reason_code",
    "zeropayrollreason":              "reason_code",
    "other reason":                   "other_reason",
    "otherreason":                    "other_reason",
    "sprs?":                          "sprs_flag",
    "sprs":                           "sprs_flag",
    "agency":                         "agency_name",
    # ── Audit Report — Classification Summary ─────────────────────────────
    # Multiple space variants because \n→space conversion differs per file
    "exposure received  per class":   "actual_payroll_reported",
    "exposure received   per class":  "actual_payroll_reported",
    "exposure received    per class": "actual_payroll_reported",
    "exposure assessed  per class":   "exposure",
    "exposure assessed   per class":  "exposure",
    "exposure assessed    per class": "exposure",
    # ── Audit Report — Rate Detail ────────────────────────────────────────
    "employee count":                 "notice_instance",
    "exposure received  per net rate":   "actual_payroll_reported",
    "exposure received   per net rate":  "actual_payroll_reported",
    "exposure assessed  per net rate":   "exposure",
    "exposure assessed   per net rate":  "exposure",
    "exposure assessed    per net rate": "exposure",
    # ── Audit Report — Premium Summary ───────────────────────────────────
    "payroll premium":                "actual_premium",
    "total premium calculated":       "est_premium_end",
    "total collected premium during policy term": "actual_premium",
    # ── XML display names ─────────────────────────────────────────────────
    "est premium":                    "est_premium_end",
    "estpremium":                     "est_premium_end",
    "premium":                        "premium_as_written",
}


class MappingConfidence(StrEnum):
    HIGH      = "HIGH"
    MEDIUM    = "MEDIUM"
    LOW       = "LOW"
    UNMATCHED = "UNMATCHED"


@dataclass
class MappingProposal:
    source_field:    str
    source_sample:   Optional[str]
    inferred_type:   str
    proposed_target: Optional[str]
    confidence:      MappingConfidence
    score:           Decimal
    transform_fn:    str
    is_excluded:     bool
    match_reason:    str


class AutoMappingService:

    async def run(
        self,
        run_id: int,
        carrier_id: int,
        file_bytes: bytes,
        db: AsyncSession,
        file_type: str = "xlsx",
        schema_name: str = "public",
    ) -> int:
        source_fields, sample_values = self._extract_fields(file_bytes, file_type)
        print("debugging fields",len(source_fields),source_fields,file_type)
        logger.info(
            "DEBUG_FIELDS",
            count=len(source_fields),
            fields=source_fields
        )


        proposals = await self._score_all_fields(
            source_fields=source_fields,
            sample_values=sample_values,
            carrier_id=carrier_id,
            db=db,
            schema_name=schema_name,
        )

        session_id = await self._persist_session_and_proposals(
            run_id=run_id,
            carrier_id=carrier_id,
            proposals=proposals,
            db=db,
        )

        logger.info(
            "auto_mapping.complete",
            run_id=run_id,
            session_id=session_id,
            total_fields=len(proposals),
            high=sum(1 for p in proposals if p.confidence == MappingConfidence.HIGH),
            medium=sum(1 for p in proposals if p.confidence == MappingConfidence.MEDIUM),
            low=sum(1 for p in proposals if p.confidence == MappingConfidence.LOW),
            unmatched=sum(1 for p in proposals if p.confidence == MappingConfidence.UNMATCHED),
        )
        return session_id

    # =========================================================================
    # Field extraction
    # =========================================================================

    def _extract_fields(
        self,
        file_bytes: bytes,
        file_type: str = "xlsx",
    ) -> tuple[list[str], dict[str, str]]:
        """
        Dispatches to the correct header extractor based on file_type.
        Phase 4: CSV extraction added per prompt spec.
        """
        if file_type == "xml":
            return self._extract_fields_xml(file_bytes)
        if file_type == "csv":
            return self._extract_fields_csv(file_bytes)
        return self._extract_fields_xlsx(file_bytes)

    def _extract_fields_csv(
        self,
        file_bytes: bytes,
    ) -> tuple[list[str], dict[str, str]]:
        """
        Extracts headers from a CSV file using csv.reader with utf-8-sig decoding.
        Returns (field_names, {field_name: sample_value}).
        Phase 4 — per V9 S16.5 CSV spec.
        """
        import csv
        import io
        text_content = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text_content), delimiter=",")
        try:
            header_row = next(reader)
            sample_row = next(reader, [])
        except StopIteration:
            return [], {}
        field_names = [str(h).strip() for h in header_row if str(h).strip()]
        sample_values: dict[str, str] = {}
        for i, name in enumerate(field_names):
            sample_values[name] = str(sample_row[i]).strip() if i < len(sample_row) else ""
        return field_names, sample_values
    def _extract_fields_audit_report(
        self,
        file_bytes: bytes,
    ) -> tuple[list[str], dict[str, str]]:
        """
        Dedicated parser for the multi-section Audit Report XLSX format.

        The audit report has 7 sections each with a different header row.
        This method extracts a flat field list covering all ingestion-relevant
        sections instead of stopping at the first header found.

        Sections parsed:
          - Policy metadata (header rows 3-6 as key:value pairs)
          - Classification Summary (Exposure Received/Assessed per class)
          - Rate Detail (Net Rate per class with dates)
          - Business Entity (payment frequency, submission counts)
          - Premium Summary (key:value pairs)
        """
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=False)
        ws = wb.worksheets[0]
        all_rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
        wb.close()

        fields: list[str] = []
        samples: dict[str, str] = {}

        def _add(field_name: str, sample_val: object) -> None:
            if field_name not in samples:
                fields.append(field_name)
                if sample_val is not None:
                    s = str(sample_val).strip()
                    if s:
                        samples[field_name] = s

        # ── Section: Policy metadata (rows 3-8, key:value format) ─────────────
        for row in all_rows[2:8]:
            cells = [str(v).strip() for v in row if v is not None and str(v).strip()]
            for cell in cells:
                if cell.startswith("Policy Number:"):
                    val = cell.replace("Policy Number:", "").strip()
                    _add("Policy Number", val)
                elif cell.startswith("Policy Period:"):
                    # "05/24/2025 - 05/24/2026"
                    period = cell.replace("Policy Period:", "").strip()
                    parts = period.split(" - ")
                    if len(parts) == 2:
                        _add("Policy Effective Date", parts[0].strip())
                        _add("Policy Expiration Date", parts[1].strip())
                elif cell.startswith("Policy Cancellation Date:"):
                    val = cell.replace("Policy Cancellation Date:", "").strip()
                    if val:
                        _add("Cancellation Date", val)
            # Insured name is in column C (index 2) of the "Date Report Run:" row —
            # index 1 is None due to merged cell formatting.  Scan past index 0.
            if len(cells) >= 2:
                row_text = str(all_rows[2][0] or "")
                if "Date Report Run:" in row_text:
                    for cell in all_rows[2][1:]:
                        insured = str(cell or "").strip()
                        if insured:
                            _add("Insured Name", insured)
                            break

        # ── Section: Classification Summary ───────────────────────────────────
        # Find the "State | Class Code | Description | Exposure Received | Exposure Assessed" header
        for idx, row in enumerate(all_rows):
            cells = [str(v).replace("\n"," ").strip() for v in row if v is not None and str(v).strip()]
            if (len(cells) >= 4 and "State" in cells and "Class Code" in cells
                    and any("Exposure" in c for c in cells)):
                # This is the classification summary header
                header = [str(v).replace("\n"," ").strip() if v is not None else "" for v in row]
                _add("State", None)
                _add("Class Code", None)
                _add("Description", None)
                # Add columns from header
                for col_name in header:
                    col_clean = col_name.strip()
                    if col_clean and col_clean not in ("State", "Class Code", "Description"):
                        _add(col_clean, None)
                # Get sample values from first data row
                if idx + 1 < len(all_rows):
                    data_row = all_rows[idx + 1]
                    for col_name, val in zip(header, data_row):
                        col_clean = col_name.strip()
                        if col_clean and col_clean not in samples and val is not None:
                            s = str(val).strip()
                            if s:
                                samples[col_clean] = s
                break

        # ── Section: Rate Detail ───────────────────────────────────────────────
        for idx, row in enumerate(all_rows):
            cells = [str(v).replace("\n"," ").strip() for v in row if v is not None and str(v).strip()]
            if (len(cells) >= 5 and "Net Rate" in cells
                    and "Class Code" in cells and "Employee Count" in cells):
                header = [str(v).replace("\n"," ").strip() if v is not None else "" for v in row]
                for col_name in header:
                    col_clean = col_name.strip()
                    if col_clean and col_clean not in samples:
                        _add(col_clean, None)
                if idx + 1 < len(all_rows):
                    data_row = all_rows[idx + 1]
                    for col_name, val in zip(header, data_row):
                        col_clean = col_name.strip()
                        if col_clean and col_clean not in samples and val is not None:
                            s = str(val).strip()
                            if s:
                                samples[col_clean] = s
                break

        # ── Section: Business Entity ───────────────────────────────────────────
        for idx, row in enumerate(all_rows):
            cells = [str(v).replace("\n"," ").strip() for v in row if v is not None and str(v).strip()]
            if (len(cells) >= 4 and "Business Entity" in cells
                    and "Payroll Frequency" in cells):
                header = [str(v).replace("\n"," ").strip() if v is not None else "" for v in row]
                for col_name in header:
                    col_clean = col_name.strip()
                    if col_clean and col_clean not in samples:
                        _add(col_clean, None)
                if idx + 1 < len(all_rows):
                    data_row = all_rows[idx + 1]
                    for col_name, val in zip(header, data_row):
                        col_clean = col_name.strip()
                        if col_clean and col_clean not in samples and val is not None:
                            s = str(val).strip()
                            if s:
                                samples[col_clean] = s
                break

        # ── Section: Employee Detail ──────────────────────────────────────────
        # This is the critical section containing Wages, Employee Name, Class Code.
        # It must be extracted so the mapping gate produces a 'wages' canonical
        # column — without it, the ingestion router never matches and returns 0 rows.
        for idx, row in enumerate(all_rows):
            cells = [
                str(v).replace("\n", " ").strip()
                for v in row
                if v is not None and str(v).replace("\n", " ").strip()
            ]
            # Identify the Employee Detail header: must contain Employee Name,
            # Wages, AND Class Code together in the same row.
            if "Employee Name" in cells and "Wages" in cells and "Class Code" in cells:
                header = [
                    str(v).replace("\n", " ").strip() if v is not None else ""
                    for v in row
                ]
                for col_name in header:
                    col_clean = col_name.strip()
                    if col_clean:
                        _add(col_clean, None)
                # Populate samples from the first data row that is not a total row
                for data_row in all_rows[idx + 1: idx + 6]:
                    first_cell = str(data_row[0] or "").strip() if data_row else ""
                    if first_cell and first_cell.lower() not in ("", "total"):
                        for col_name, val in zip(header, data_row):
                            col_clean = col_name.strip()
                            if col_clean and col_clean not in samples and val is not None:
                                s = str(val).strip()
                                if s:
                                    samples[col_clean] = s
                        break
                break  # Only one Employee Detail section per audit report

        # ── Section: Premium Summary (key:value rows 22-30) ───────────────────
        for row in all_rows[20:32]:
            cells = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if len(cells) >= 2:
                label = cells[-2] if len(cells) >= 2 else cells[0]
                value = cells[-1]
                if label and not label.startswith("Total of"):
                    _add(label, value)

        return fields, samples
    def _extract_fields_xlsx(
        self,
        file_bytes: bytes,
    ) -> tuple[list[str], dict[str, str]]:
        """
        Reads ALL sheets in the XLSX, finds the header row in each sheet,
        and returns a unified flat list of (source_field, sample_value) pairs.

        This is necessary because a single upload can contain multiple sheets
        each representing a different data type (e.g. audit report has both
        Classification Detail and Breakdown of Premium sections).

        Key fixes vs the old implementation:
        - Uses read_only=False so openpyxl reads true column dimensions
          (read_only=True uses lazy streaming that reports wrong max_column)
        - Scans up to 10 data rows for sample values (payroll files have a
          blank row2 immediately after the header)
        - Strips multiline cell values (\\n in audit report headers)
        - Header detection requires only >= 2 non-null values (not 3)
          to handle narrow sheets like Missing PR
        - Detects data rows masquerading as headers by checking if ALL
          non-empty values are strings (not dates/numbers)
        """
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=False)

        print("sheets:", wb.sheetnames)
        all_fields: list[str] = []
        sample_map: dict[str, str] = {}
        seen_fields: set[str] = set()

        # These keywords identify SINGLE-CELL title/metadata rows to skip.
        # Only applied when the row has <= 2 non-empty cells, so a header row
        # like ["Provider", "Policyholder", "Zero Payroll Reason", ...] is
        # NOT skipped even though it contains the word "ZERO PAYROLL".
        SINGLE_CELL_SKIP = (
            "AUDIT REPORT", "DATE REPORT RUN", "POLICY NUMBER:",
            "POLICY PERIOD:", "CLASSIFICATION DETAIL",
            "BREAKDOWN OF PREMIUM", "PROVIDER(S) SELECTED",
            "POLICY STATUS(ES) SELECTED", "REPORT(S) SUBMITTED",
            "LATE MISSING PAYROLL", "ZERO PAYROLL",
        )

        for check_sheet in wb.sheetnames:
            check_ws = wb[check_sheet]
            first_rows = list(check_ws.iter_rows(min_row=1, max_row=5, values_only=True))
            for row in first_rows:
                joined = " ".join(str(v) for v in row if v is not None).upper()
                if "AUDIT REPORT" in joined:
                    wb.close()
                    return self._extract_fields_audit_report(file_bytes)

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            all_rows = list(ws.iter_rows(min_row=1, max_row=60, values_only=True))

            header_row_idx: Optional[int] = None
            header_vals: list[str] = []

            for idx, row in enumerate(all_rows):
                # Clean each cell: strip whitespace and embedded newlines
                clean = [
                    str(v).replace("\n", " ").replace("\r", " ").strip()
                    for v in row
                    if v is not None and str(v).replace("\n"," ").strip()
                ]
                if len(clean) < 2:
                    continue

                joined = " ".join(clean).upper()

                # Skip single-cell or two-cell title/metadata rows
                if len(clean) <= 2 and any(kw in joined for kw in SINGLE_CELL_SKIP):
                    continue

                # Skip rows where average value length suggests data not headers
                # (header cells are typically short labels < 35 chars)
                avg_len = sum(len(v) for v in clean) / len(clean)
                if avg_len > 45:
                    continue

                # Skip rows that contain numbers or dates (those are data rows)
                # A true header row should be all strings
                has_non_string = any(
                    not isinstance(v, str)
                    for v in row
                    if v is not None
                )
                if has_non_string:
                    continue

                # This is the header row
                header_vals = [
                    str(v).replace("\n", " ").replace("\r", " ").strip()
                    if v is not None else ""
                    for v in row
                ]
                header_row_idx = idx
                break

            if not header_vals or header_row_idx is None:
                continue

            # Collect sample values — scan up to 10 rows after header
            sheet_samples: dict[str, str] = {}
            for data_row in all_rows[header_row_idx + 1: header_row_idx + 11]:
                for col_name, val in zip(header_vals, data_row):
                    col_clean = col_name.strip()
                    if col_clean and col_clean not in sheet_samples and val is not None:
                        s = str(val).strip()
                        if s:
                            sheet_samples[col_clean] = s

            # Add fields — deduplicate across sheets by field name
            for col in header_vals:
                col_clean = col.strip()
                if col_clean and col_clean not in seen_fields:
                    seen_fields.add(col_clean)
                    all_fields.append(col_clean)
                    if col_clean in sheet_samples:
                        sample_map[col_clean] = sheet_samples[col_clean]

        wb.close()
        return all_fields, sample_map

    def _extract_fields_xml(
        self,
        file_bytes: bytes,
    ) -> tuple[list[str], dict[str, str]]:
        """
        Extracts field names and sample values from the PPlus XML format.
        """
        try:
            root = ET.fromstring(file_bytes)
        except ET.ParseError as exc:
            logger.warning("auto_mapping.xml_parse_failed", error=str(exc))
            return [], {}

        policy = root.find("Policy")
        if policy is None:
            return [], {}

        fields: list[str] = []
        samples: dict[str, str] = {}

        def _add(field_name: str, value: Optional[str]) -> None:
            if field_name not in samples:
                fields.append(field_name)
                samples[field_name] = value or ""

        policy_data = policy.find("PolicyData")
        if policy_data is not None:
            XML_FIELD_MAP = {
                "PolicyNumber":     "Policy Number",
                "InsuredName":      "Insured Name",
                "Fein":             "FEIN",
                "EffectiveDate":    "Effective Date",
                "ExpirationDate":   "Expiration Date",
                "Premium":          "Premium",
                "GoverningState":   "State Code",
                "PayrollFrequency": "Payment Frequency",
            }
            for xml_tag, display_name in XML_FIELD_MAP.items():
                node = policy_data.find(xml_tag)
                _add(display_name, node.text.strip() if node is not None and node.text else None)

        first_rate = policy.find(".//Rate")
        if first_rate is not None:
            RATE_FIELD_MAP = {
                "ClassCode":      "Class Code",
                "Exposure":       "Exposure",
                "EstPremium":     "Est Premium",
                "CompositeRate":  "Net Rate",
                "EffectiveDate":  "Rate Effective Date",
                "ExpirationDate": "Rate Expiration Date",
            }
            for xml_tag, display_name in RATE_FIELD_MAP.items():
                node = first_rate.find(xml_tag)
                _add(display_name, node.text.strip() if node is not None and node.text else None)

        return fields, samples

    # =========================================================================
    # 4-pass confidence scoring
    # =========================================================================

    async def _score_all_fields(
        self,
        source_fields: list[str],
        sample_values: dict[str, str],
        carrier_id: int,
        db: AsyncSession,
        schema_name: str = "public",
    ) -> list[MappingProposal]:
        saved_maps = await self._load_saved_mappings(carrier_id, db, schema_name=schema_name)
        proposals: list[MappingProposal] = []

        for field in source_fields:
            if not field.strip():
                continue
            sample = sample_values.get(field, "")
            inferred_type = infer_type(sample if sample else None)
            proposals.append(
                self._score_field(
                    source_field=field,
                    sample=sample,
                    inferred_type=inferred_type,
                    saved_maps=saved_maps,
                )
            )
        return proposals

    def _score_field(
        self,
        source_field: str,
        sample: str,
        inferred_type: str,
        saved_maps: dict[str, str],
    ) -> MappingProposal:
        # Pass 1: Saved mapping
        if source_field in saved_maps:
            target = saved_maps[source_field]
            return MappingProposal(
                source_field=source_field,
                source_sample=sample or None,
                inferred_type=inferred_type,
                proposed_target=target,
                confidence=MappingConfidence.HIGH,
                score=Decimal("1.000"),
                transform_fn=self._suggest_transform(inferred_type, CANONICAL_COLUMNS.get(target, "TEXT")),
                is_excluded=False,
                match_reason="saved_mapping",
            )

        norm_source = normalise(source_field)

        # Pass 2a: Known alias lookup (handles real-world column name variants)
        if norm_source in KNOWN_ALIASES:
            target = KNOWN_ALIASES[norm_source]
            if target in CANONICAL_COLUMNS:
                return MappingProposal(
                    source_field=source_field,
                    source_sample=sample or None,
                    inferred_type=inferred_type,
                    proposed_target=target,
                    confidence=MappingConfidence.HIGH,
                    score=Decimal("0.980"),
                    transform_fn=self._suggest_transform(inferred_type, CANONICAL_COLUMNS[target]),
                    is_excluded=False,
                    match_reason="known_alias",
                )

        # Pass 2b: Normalised name equality
        for canonical_col in CANONICAL_COLUMNS:
            if normalise(canonical_col) == norm_source:
                return MappingProposal(
                    source_field=source_field,
                    source_sample=sample or None,
                    inferred_type=inferred_type,
                    proposed_target=canonical_col,
                    confidence=MappingConfidence.HIGH,
                    score=Decimal("0.950"),
                    transform_fn=self._suggest_transform(inferred_type, CANONICAL_COLUMNS[canonical_col]),
                    is_excluded=False,
                    match_reason="exact_normalised_match",
                )

        # Pass 3: Fuzzy ratio + type compatibility
        best_target: Optional[str] = None
        best_ratio: float = 0.0
        best_canonical_type: str = "TEXT"

        for canonical_col, canonical_type in CANONICAL_COLUMNS.items():
            ratio = difflib.SequenceMatcher(
                None, norm_source, normalise(canonical_col)
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_target = canonical_col
                best_canonical_type = canonical_type

        if best_target is not None and best_ratio >= 0.50:
            type_ok = types_are_compatible(inferred_type, best_canonical_type)
            if best_ratio >= 0.75 and type_ok:
                confidence = MappingConfidence.MEDIUM
            elif best_ratio >= 0.50:
                confidence = MappingConfidence.LOW
            else:
                confidence = MappingConfidence.UNMATCHED

            if confidence in (MappingConfidence.MEDIUM, MappingConfidence.LOW):
                return MappingProposal(
                    source_field=source_field,
                    source_sample=sample or None,
                    inferred_type=inferred_type,
                    proposed_target=best_target,
                    confidence=confidence,
                    score=Decimal(str(round(best_ratio, 3))),
                    transform_fn=self._suggest_transform(inferred_type, best_canonical_type),
                    is_excluded=False,
                    match_reason=f"fuzzy_ratio_{best_ratio:.3f}",
                )

        # Pass 4: Unmatched
        return MappingProposal(
            source_field=source_field,
            source_sample=sample or None,
            inferred_type=inferred_type,
            proposed_target=None,
            confidence=MappingConfidence.UNMATCHED,
            score=Decimal("0.000"),
            transform_fn="none",
            is_excluded=False,
            match_reason="no_match",
        )

    def _suggest_transform(self, inferred: str, canonical: str) -> str:
        if inferred == canonical:
            return "none"
        mapping = {"DATE": "to_date", "NUMERIC": "to_decimal",
                   "INTEGER": "to_integer", "BOOLEAN": "to_boolean"}
        return mapping.get(canonical, "strip")

    # async def _load_saved_mappings(
    #     self,
    #     carrier_id: int,
    #     db: AsyncSession,
    # ) -> dict[str, str]:
    #     try:
    #         result = await db.execute(
    #             text(
    #                 "SELECT source_field, canonical_column "
    #                 "FROM ingestion_field_maps WHERE carrier_id = :cid"
    #             ),
    #             {"cid": carrier_id},
    #         )
    #         return {row[0]: row[1] for row in result.fetchall()}
    #     except Exception as exc:
    #         logger.warning("auto_mapping.saved_maps_load_failed", error=str(exc))
    #         try:
    #             await db.rollback()
    #         except Exception:
    #             pass
    #         return {}

    async def _load_saved_mappings(
        self,
        carrier_id: int,
        db: AsyncSession,
        schema_name: str = "public",
    ) -> dict[str, str]:
        try:
            result = await db.execute(
                text(
                    "SELECT source_field, canonical_column "
                    "FROM ingestion_field_maps WHERE carrier_id = :cid"
                ),
                {"cid": carrier_id},
            )
            return {row[0]: row[1] for row in result.fetchall()}
        except Exception as exc:
            logger.warning("auto_mapping.saved_maps_load_failed", error=str(exc))
            try:
                await db.rollback()
            except Exception:
                pass
            # CRITICAL: rollback() resets asyncpg's search_path to the server
            # default. Re-assert it so _persist_session_and_proposals can still
            # INSERT into the tenant schema tables.
            try:
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.commit()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
            except Exception:
                pass
            return {}

    # =========================================================================
    # Persistence
    # =========================================================================

    async def _persist_session_and_proposals(
        self,
        run_id: int,
        carrier_id: int,
        proposals: list[MappingProposal],
        db: AsyncSession,
    ) -> int:
        auto_mapped = sum(1 for p in proposals if p.confidence == MappingConfidence.HIGH)
        flagged = sum(1 for p in proposals if p.confidence in (MappingConfidence.MEDIUM, MappingConfidence.LOW))
        unmatched = sum(1 for p in proposals if p.confidence == MappingConfidence.UNMATCHED)

        session_result = await db.execute(
            text("""
                INSERT INTO field_mapping_sessions
                  (ingestion_run_id, carrier_id, status, created_at,
                   auto_mapped_count, flagged_count, unmatched_count)
                VALUES
                  (:rid, :cid, 'PENDING_REVIEW', now(), :auto, :flagged, :unmatched)
                RETURNING session_id
            """),
            {"rid": run_id, "cid": carrier_id,
             "auto": auto_mapped, "flagged": flagged, "unmatched": unmatched},
        )
        session_id: int = session_result.scalar_one()

        for proposal in proposals:
            await db.execute(
                text("""
                    INSERT INTO field_mapping_proposals
                      (session_id, source_field, source_sample, inferred_type,
                       proposed_target, confidence, score, transform_fn,
                       is_excluded, match_reason)
                    VALUES
                      (:sid, :sf, :ss, :it, :pt, :conf, :score, :tfn, :excl, :reason)
                """),
                {
                    "sid":    session_id,
                    "sf":     proposal.source_field,
                    "ss":     proposal.source_sample,
                    "it":     proposal.inferred_type,
                    "pt":     proposal.proposed_target,
                    "conf":   str(proposal.confidence),
                    "score":  float(proposal.score),
                    "tfn":    proposal.transform_fn,
                    "excl":   proposal.is_excluded,
                    "reason": proposal.match_reason,
                },
            )

        await db.execute(
            text("""
                UPDATE field_mapping_sessions SET
                    auto_mapped_count = (
                        SELECT COUNT(*) FROM field_mapping_proposals
                        WHERE session_id = :sid AND confidence = 'HIGH' AND is_excluded = FALSE
                    ),
                    flagged_count = (
                        SELECT COUNT(*) FROM field_mapping_proposals
                        WHERE session_id = :sid AND confidence IN ('MEDIUM','LOW') AND is_excluded = FALSE
                    ),
                    unmatched_count = (
                        SELECT COUNT(*) FROM field_mapping_proposals
                        WHERE session_id = :sid AND confidence = 'UNMATCHED' AND is_excluded = FALSE
                    )
                WHERE session_id = :sid
            """),
            {"sid": session_id},
        )
        await db.commit()
        logger.info(
            "auto_mapping.session_created",
            session_id=session_id, run_id=run_id,
            auto_mapped=auto_mapped, flagged=flagged, unmatched=unmatched,
        )
        return session_id