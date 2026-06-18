"""
Phase 4 — Unit tests: IngestionErrorCode and IngestionRowError.

V9 S17.2 specifies exactly 8 error codes:
  FIELD_TYPE_MISMATCH, REQUIRED_FIELD_NULL, POLICY_NOT_FOUND,
  POLICYHOLDER_DUPLICATE, DATE_PARSE_FAILURE, MAPPING_NOT_FOUND,
  TRANSFORM_FAILURE, BATCH_HARD_FAILURE
"""
from __future__ import annotations

import pytest

from app.services.ingestion_error_codes import IngestionErrorCode, IngestionRowError


# ---------------------------------------------------------------------------
# IngestionErrorCode — 8 codes per V9 S17.2
# ---------------------------------------------------------------------------

def test_exactly_eight_error_codes() -> None:
    """V9 S17.2 mandates exactly 8 error codes."""
    assert len(list(IngestionErrorCode)) == 8


def test_field_type_mismatch_present() -> None:
    assert IngestionErrorCode.FIELD_TYPE_MISMATCH == "FIELD_TYPE_MISMATCH"


def test_required_field_null_present() -> None:
    assert IngestionErrorCode.REQUIRED_FIELD_NULL == "REQUIRED_FIELD_NULL"


def test_policy_not_found_present() -> None:
    assert IngestionErrorCode.POLICY_NOT_FOUND == "POLICY_NOT_FOUND"


def test_policyholder_duplicate_present() -> None:
    assert IngestionErrorCode.POLICYHOLDER_DUPLICATE == "POLICYHOLDER_DUPLICATE"


def test_date_parse_failure_present() -> None:
    assert IngestionErrorCode.DATE_PARSE_FAILURE == "DATE_PARSE_FAILURE"


def test_mapping_not_found_present() -> None:
    assert IngestionErrorCode.MAPPING_NOT_FOUND == "MAPPING_NOT_FOUND"


def test_transform_failure_present() -> None:
    assert IngestionErrorCode.TRANSFORM_FAILURE == "TRANSFORM_FAILURE"


def test_batch_hard_failure_present() -> None:
    assert IngestionErrorCode.BATCH_HARD_FAILURE == "BATCH_HARD_FAILURE"


# ---------------------------------------------------------------------------
# IngestionRowError — exception wrapper
# ---------------------------------------------------------------------------

def test_ingestion_row_error_is_exception() -> None:
    err = IngestionRowError(
        code=IngestionErrorCode.REQUIRED_FIELD_NULL,
        message="policy_number is None",
    )
    assert isinstance(err, Exception)


def test_ingestion_row_error_stores_code() -> None:
    err = IngestionRowError(
        code=IngestionErrorCode.FIELD_TYPE_MISMATCH,
        message="Cannot parse 'bad' as Decimal",
    )
    assert err.code == IngestionErrorCode.FIELD_TYPE_MISMATCH


def test_ingestion_row_error_stores_message() -> None:
    err = IngestionRowError(
        code=IngestionErrorCode.DATE_PARSE_FAILURE,
        message="Cannot parse '99/99/9999'",
    )
    assert err.message == "Cannot parse '99/99/9999'"
    assert str(err) == "Cannot parse '99/99/9999'"


def test_ingestion_row_error_defaults_empty_row_data() -> None:
    err = IngestionRowError(code=IngestionErrorCode.BATCH_HARD_FAILURE, message="empty")
    assert err.row_data == {}


def test_ingestion_row_error_stores_row_data() -> None:
    data = {"Policy Number": "", "Insured Name": "Corp"}
    err = IngestionRowError(
        code=IngestionErrorCode.REQUIRED_FIELD_NULL,
        message="No policy_number",
        row_data=data,
    )
    assert err.row_data == data


@pytest.mark.parametrize("code", list(IngestionErrorCode))
def test_each_code_round_trips(code: IngestionErrorCode) -> None:
    """Every code's string value reconstructs the enum member."""
    assert IngestionErrorCode(code.value) == code


def test_all_code_values_are_uppercase_strings() -> None:
    for code in IngestionErrorCode:
        assert isinstance(code.value, str)
        assert code.value == code.value.upper()
