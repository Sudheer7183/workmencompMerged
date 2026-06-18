"""
Phase 4 — Unit tests: CSV ingestion helpers in IngestionServiceV4.

V9 S16.5 / prompt spec:
  - csv.reader (not DictReader)
  - utf-8-sig decoding (handles BOM natively)
  - delimiter from ingestion_sources.delimiter, default ','
"""
from __future__ import annotations

import pytest

from app.services.ingestion_service import IngestionServiceV4


@pytest.fixture
def svc() -> IngestionServiceV4:
    return IngestionServiceV4()


# ---------------------------------------------------------------------------
# _is_csv detection
# ---------------------------------------------------------------------------

def test_is_csv_plain_csv(svc: IngestionServiceV4) -> None:
    assert svc._is_csv(b"Policy Number,Name\n001,Corp\n") is True


def test_is_csv_with_bom_header(svc: IngestionServiceV4) -> None:
    """Excel-saved CSVs include UTF-8 BOM — must be detected as CSV."""
    bom_csv = b"\xef\xbb\xbfPolicy Number,Name\n001,Corp\n"
    assert svc._is_csv(bom_csv) is True


def test_is_csv_rejects_xlsx_magic(svc: IngestionServiceV4) -> None:
    """XLSX files start with PK zip magic."""
    assert svc._is_csv(b"PK\x03\x04" + b"\x00" * 50) is False


def test_is_csv_rejects_xml(svc: IngestionServiceV4) -> None:
    assert svc._is_csv(b"<?xml version='1.0'?><root/>") is False


def test_is_csv_rejects_binary(svc: IngestionServiceV4) -> None:
    assert svc._is_csv(bytes(range(256))) is False


def test_is_csv_tab_delimited(svc: IngestionServiceV4) -> None:
    assert svc._is_csv(b"Policy\tName\n001\tCorp\n") is True


def test_is_csv_semicolon_delimited(svc: IngestionServiceV4) -> None:
    assert svc._is_csv(b"Policy;Name\n001;Corp\n") is True


# ---------------------------------------------------------------------------
# AutoMappingService CSV header extraction
# ---------------------------------------------------------------------------

def test_auto_mapping_extracts_csv_headers() -> None:
    """AutoMappingService._extract_fields_csv must decode utf-8-sig and return headers."""
    from app.services.auto_mapping_service import AutoMappingService
    svc_am = AutoMappingService()
    # UTF-8 BOM + CSV
    csv_bytes = "\ufeffPolicy Number,Insured Name,Est Premium End\n001,Corp,10000\n".encode("utf-8")
    fields, samples = svc_am._extract_fields_csv(csv_bytes)
    # BOM should be stripped — first header should be clean
    assert fields[0] == "Policy Number"
    assert "Insured Name" in fields
    assert "Est Premium End" in fields


def test_auto_mapping_csv_samples_from_first_data_row() -> None:
    """Sample values come from the first data row."""
    from app.services.auto_mapping_service import AutoMappingService
    svc_am = AutoMappingService()
    csv_bytes = b"Policy Number,Premium\nPOL-001,9500.00\n"
    fields, samples = svc_am._extract_fields_csv(csv_bytes)
    assert samples.get("Policy Number") == "POL-001"
    assert samples.get("Premium") == "9500.00"
