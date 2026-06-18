"""
test_report_generation_service.py — Phase 5 unit tests.

Tests for ReportGenerationService: branding resolution, all 5 report type
generators, NULL→N/A rendering, Excel styling, and Jinja2 filter correctness.

Uses pytest-asyncio + mocked AsyncSession; no real DB or S3 connection needed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openpyxl import load_workbook
import io

from app.services.report_generation_service import (
    ReportGenerationService,
    ReportBranding,
    EXCEL_ONLY_REPORT_TYPES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def svc() -> ReportGenerationService:
    return ReportGenerationService()


def _mock_db_with_responses(responses: dict[str, Any]) -> AsyncMock:
    """
    Creates a mock AsyncSession where each execute() call returns
    the next value from responses keyed by call order or SQL substring.
    """
    db = AsyncMock()
    call_count = [0]
    response_list = list(responses.values())

    async def execute_mock(query: Any, params: Any = None) -> MagicMock:
        idx = call_count[0]
        call_count[0] += 1
        result = MagicMock()
        if idx < len(response_list):
            data = response_list[idx]
            if data is None:
                result.fetchone.return_value = None
                result.fetchall.return_value = []
            elif isinstance(data, list):
                result.fetchone.return_value = data[0] if data else None
                result.fetchall.return_value = data
            else:
                result.fetchone.return_value = data
                result.fetchall.return_value = [data]
        else:
            result.fetchone.return_value = None
            result.fetchall.return_value = []
        return result

    db.execute = execute_mock
    return db


@pytest.fixture
def default_branding() -> ReportBranding:
    return ReportBranding(
        logo_url=None,
        primary_colour="1A3C5E",
        secondary_colour="2E86C1",
        contact_block=None,
        carrier_name="Test Carrier",
        tenant_name="Test Tenant",
        generated_at="2026-01-01 00:00 UTC",
    )


@pytest.fixture
def carrier_branding() -> ReportBranding:
    return ReportBranding(
        logo_url="http://minio:9000/bucket/logos/carrier/test.png",
        primary_colour="2E86C1",
        secondary_colour="1A3C5E",
        contact_block="<p>123 Main St</p>",
        carrier_name="Test Carrier",
        tenant_name="Test Tenant",
        generated_at="2026-01-01 00:00 UTC",
    )


# ── Branding resolution tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_branding_uses_carrier_logo_when_set(svc: ReportGenerationService) -> None:
    """carrier_report_templates.logo_url present → branding.logo_url = carrier logo"""
    carrier_logo = "http://minio/bucket/carrier-logo.png"
    tenant_logo = "http://minio/bucket/tenant-logo.png"

    db = _mock_db_with_responses({
        "template": (None, carrier_logo, "2E86C1", "1A3C5E", "<p>Contact</p>"),
        "branding": (tenant_logo, None),
        "carrier": ("Test Carrier",),
        "tenant": ("Test Tenant",),
    })

    branding = await svc.get_branding(carrier_id=1, db=db)
    assert branding.logo_url == carrier_logo


@pytest.mark.asyncio
async def test_get_branding_falls_back_to_tenant_logo(svc: ReportGenerationService) -> None:
    """No carrier template → branding.logo_url = tenant_branding.logo_url"""
    tenant_logo = "http://minio/bucket/tenant-logo.png"

    db = _mock_db_with_responses({
        "template": None,
        "branding": (tenant_logo, None),
        "carrier": ("Test Carrier",),
        "tenant": ("Test Tenant",),
    })

    branding = await svc.get_branding(carrier_id=1, db=db)
    assert branding.logo_url == tenant_logo


@pytest.mark.asyncio
async def test_get_branding_no_logo_when_neither_set(svc: ReportGenerationService) -> None:
    """No carrier template, no tenant branding → branding.logo_url = None"""
    db = _mock_db_with_responses({
        "template": None,
        "branding": None,
        "carrier": ("Test Carrier",),
        "tenant": ("Test Tenant",),
    })

    branding = await svc.get_branding(carrier_id=1, db=db)
    assert branding.logo_url is None


# ── Policy Audit PDF/Excel tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_policy_audit_pdf_returns_bytes(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """generate_policy_audit returns non-empty bytes with content_type='application/pdf'"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-001", "Test Insured", "CA", "2025-01-01", "2026-01-01",
                        "active", "monthly", "individual", "open", None, Decimal("10000"), None),
            "pv": (Decimal("10000"), Decimal("9500"), Decimal("-500"), None),
            "pvp": [],
            "pvc": [],
            "mp": [],
            "zp": [],
        })
        result_bytes, content_type, ext = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="pdf", run_id=None, db=db
        )
    assert len(result_bytes) > 0
    assert content_type == "application/pdf"
    assert ext == "pdf"


@pytest.mark.asyncio
async def test_policy_audit_excel_returns_bytes(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """generate_policy_audit format='excel' returns xlsx bytes"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-001", "Test Insured", "CA", "2025-01-01", "2026-01-01",
                        "active", "monthly", "individual", "open", None, Decimal("10000"), None),
            "pv": (Decimal("10000"), Decimal("9500"), Decimal("-500"), None),
            "pvp": [],
            "pvc": [],
            "mp": [],
            "zp": [],
        })
        result_bytes, content_type, ext = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="excel", run_id=None, db=db
        )
    assert len(result_bytes) > 0
    expected_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert content_type == expected_ct
    assert ext == "xlsx"


@pytest.mark.asyncio
async def test_policy_audit_pdf_contains_policy_number(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """PDF content includes the policy number string"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-UNIQUE-999", "Test Insured", "CA", "2025-01-01", "2026-01-01",
                        "active", "monthly", "individual", "open", None, Decimal("10000"), None),
            "pv": None, "pvp": [], "pvc": [], "mp": [], "zp": [],
        })
        pdf_bytes, _, _ = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="pdf", run_id=None, db=db
        )
    # WeasyPrint PDF bytes contain embedded text
    assert b"POL-UNIQUE-999" in pdf_bytes


@pytest.mark.asyncio
async def test_null_variance_pct_renders_na_in_pdf(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """variance_pct=NULL in DB → PDF contains 'N/A', not 'None' or blank"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-001", "Test Insured", "CA", None, None,
                        "active", None, None, "open", None, Decimal("10000"), None),
            "pv": (Decimal("10000"), Decimal("9500"), Decimal("-500"), None),  # variance_pct = None
            "pvp": [], "pvc": [], "mp": [], "zp": [],
        })
        pdf_bytes, _, _ = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="pdf", run_id=None, db=db
        )
    pdf_text = pdf_bytes.decode("latin-1", errors="replace")
    assert "N/A" in pdf_text
    assert "None" not in pdf_text


@pytest.mark.asyncio
async def test_null_variance_pct_renders_na_in_excel(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """variance_pct=NULL in DB → Excel cell value='N/A'"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-001", "Test Insured", "CA", None, None,
                        "active", None, None, "open", None, Decimal("10000"), None),
            "pv": (Decimal("10000"), Decimal("9500"), Decimal("-500"), None),
            "pvp": [], "pvc": [], "mp": [], "zp": [],
        })
        xlsx_bytes, _, _ = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="excel", run_id=None, db=db
        )

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active
    all_values = [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value]
    assert "N/A" in all_values
    assert "None" not in all_values


@pytest.mark.asyncio
async def test_class_code_variance_excel_has_all_columns(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """Excel has state_code, class_code, est_payroll, actual_reported — all 11 columns"""
    mock_row = (
        "POL-001", "Test Co", "CA", "8810",
        Decimal("50000"), Decimal("48000"),
        Decimal("-2000"), Decimal("96.00"),
        Decimal("47000"), Decimal("-3000"), Decimal("94.00"),
    )
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({"rows": [mock_row]})
        xlsx_bytes, _, _ = await svc.generate_class_code_variance(
            carrier_id=1, run_id=None, db=db
        )

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active
    # Row 2 is column headers
    header_row = [str(ws.cell(row=2, column=c).value or "") for c in range(1, 12)]
    assert "State" in header_row
    assert "Class Code" in header_row
    assert "Est Payroll" in header_row


@pytest.mark.asyncio
async def test_exception_report_has_two_sheets(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """Excel has sheets: 'Ingestion Errors' and 'Skipped Rows'"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({
            "errors": [(1, 5, "MISSING_REQUIRED_FIELD", "Field is required", "policy_number", "")],
            "skipped": [(1, 5, "Row skipped", "{}", "pending", None)],
        })
        xlsx_bytes, _, _ = await svc.generate_exception_report(
            carrier_id=1, run_id=42, db=db
        )

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    assert "Ingestion Errors" in wb.sheetnames
    assert "Skipped Rows" in wb.sheetnames


@pytest.mark.asyncio
async def test_ingestion_audit_trail_includes_engine_mode_column(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """Excel has a 'Calc Engine' column showing Enabled/Disabled/N/A per run"""
    mock_row = (1, 1, "source_1", "complete", 100, 98, 2, None, None, True, False)
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({"rows": [mock_row]})
        xlsx_bytes, _, _ = await svc.generate_ingestion_audit_trail(
            carrier_id=1, run_id=1, db=db
        )

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active
    header_row = [str(ws.cell(row=2, column=c).value or "") for c in range(1, 12)]
    assert "Calc Engine" in header_row


@pytest.mark.asyncio
async def test_book_summary_pdf_includes_all_policies(
    svc: ReportGenerationService,
    default_branding: ReportBranding,
) -> None:
    """PDF contains a table row for each policy in the carrier"""
    policies = [
        ("POL-A", "Insured A", "CA", "2025-01-01", "2026-01-01",
         "active", Decimal("10000"), None, None, None, "open"),
        ("POL-B", "Insured B", "NY", "2025-01-01", "2026-01-01",
         "active", Decimal("20000"), Decimal("-500"), Decimal("-5.0"), "MEDIUM", "open"),
    ]
    with patch.object(svc, "get_branding", AsyncMock(return_value=default_branding)):
        db = _mock_db_with_responses({"policies": policies})
        pdf_bytes, _, _ = await svc.generate_book_summary(
            carrier_id=1, output_format="pdf", db=db
        )
    pdf_text = pdf_bytes.decode("latin-1", errors="replace")
    assert "POL-A" in pdf_text
    assert "POL-B" in pdf_text


@pytest.mark.asyncio
async def test_excel_header_row_uses_primary_colour(
    svc: ReportGenerationService,
    carrier_branding: ReportBranding,
) -> None:
    """openpyxl workbook header row fill colour matches branding.primary_colour"""
    with patch.object(svc, "get_branding", AsyncMock(return_value=carrier_branding)):
        db = _mock_db_with_responses({
            "policy": (1, "POL-001", "Test Insured", "CA", None, None,
                        "active", None, None, "open", None, Decimal("10000"), None),
            "pv": None, "pvp": [], "pvc": [], "mp": [], "zp": [],
        })
        xlsx_bytes, _, _ = await svc.generate_policy_audit(
            policy_id=1, carrier_id=1, output_format="excel", run_id=None, db=db
        )

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active
    # Row 1 is the branding header
    header_cell = ws.cell(row=1, column=1)
    assert header_cell.fill.fgColor.rgb.upper().endswith(
        carrier_branding.primary_colour.upper()
    )


def test_currency_filter_formats_correctly(svc: ReportGenerationService) -> None:
    """_fmt_currency(Decimal('1234.56')) == '$1,234.56'"""
    assert svc._fmt_currency(Decimal("1234.56")) == "$1,234.56"
    assert svc._fmt_currency(0) == "$0.00"
    assert svc._fmt_currency(1234567.89) == "$1,234,567.89"


def test_pct_filter_returns_na_for_none(svc: ReportGenerationService) -> None:
    """_fmt_pct(None) == 'N/A'"""
    assert svc._fmt_pct(None) == "N/A"
    assert svc._fmt_pct(Decimal("5.25")) == "5.25%"
    assert svc._fmt_pct(0) == "0.00%"


def test_report_type_format_validation(svc: ReportGenerationService) -> None:
    """class_code_variance + pdf → raises ValueError (Excel only)"""
    with pytest.raises(ValueError, match="Excel-only"):
        svc.validate_report_request(
            report_type="class_code_variance",
            output_format="pdf",
            policy_id=None,
            run_id=None,
        )

    with pytest.raises(ValueError, match="policy_id is required"):
        svc.validate_report_request(
            report_type="policy_audit",
            output_format="pdf",
            policy_id=None,
            run_id=None,
        )

    with pytest.raises(ValueError, match="run_id is required"):
        svc.validate_report_request(
            report_type="exception_report",
            output_format="excel",
            policy_id=None,
            run_id=None,
        )

    # Valid combos should not raise
    svc.validate_report_request("policy_audit", "pdf", policy_id=1, run_id=None)
    svc.validate_report_request("book_summary", "excel", policy_id=None, run_id=None)
    svc.validate_report_request("exception_report", "excel", policy_id=None, run_id=42)
