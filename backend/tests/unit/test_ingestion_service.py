"""
Unit tests for IngestionService — 5 cases.
Tests Phase 1 XLSX routing and error handling.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.ingestion_service import IngestionService, _safe_decimal
from app.utils.text_utils import normalise as _normalise, find_col as _find_col


svc = IngestionService()


# ============================================================================
# 1. _normalise strips punctuation and lowercases
# ============================================================================
def test_normalise_strips_punctuation():
    assert _normalise("Est. Premium (USD)") == "est premium usd"
    assert _normalise("Policy #") == "policy"


# ============================================================================
# 2. _normalise handles None
# ============================================================================
def test_normalise_handles_none():
    assert _normalise(None) == ""


# ============================================================================
# 3. _safe_decimal handles NA strings
# ============================================================================
def test_safe_decimal_na_strings():
    assert _safe_decimal("N/A") is None
    assert _safe_decimal("NA") is None
    assert _safe_decimal("-") is None
    assert _safe_decimal("") is None


# ============================================================================
# 4. _safe_decimal parses valid values
# ============================================================================
def test_safe_decimal_valid():
    from decimal import Decimal
    assert _safe_decimal("1234.56") == Decimal("1234.56")
    assert _safe_decimal("$1,234.56") == Decimal("1234.56")


# ============================================================================
# 5. run() raises ValueError for non-xlsx file_type
# ============================================================================
@pytest.mark.asyncio
async def test_run_raises_for_non_xlsx():
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match="Phase 3 supports XLSX only"):
        await svc.run(
            schema_name="tenant_demo",
            carrier_id=1,
            source_id=1,
            file_bytes=b"not xlsx",
            file_type="csv",
            db=mock_db,
        )
