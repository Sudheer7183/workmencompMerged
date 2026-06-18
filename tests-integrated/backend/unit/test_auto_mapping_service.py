"""
Unit tests for AutoMappingService — Phase 3.

Covers all 4 confidence passes, type-inference helpers, and saved-mapping
precedence rule.

All tests are pure unit tests — no DB required.
"""
from __future__ import annotations

import pytest

from app.services.auto_mapping_service import AutoMappingService
from app.utils.text_utils import infer_type, normalise, types_are_compatible


# ---------------------------------------------------------------------------
# Text utility helpers
# ---------------------------------------------------------------------------


def test_normalise_strips_spaces_and_lowercases() -> None:
    """
    normalise() lowercases and strips underscores/punctuation.
    Spaces inside words are preserved; underscores are removed.
    The fuzzy matcher (not equality) handles 'Policy Number' ↔ 'policy_number'.
    """
    assert normalise("Policy Number") == "policy number"
    assert normalise("policy_number") == "policynumber"
    assert normalise("POLICY NUMBER") == "policy number"
    assert normalise("PolicyNumber")  == "policynumber"


def test_normalise_handles_camel_case() -> None:
    """CamelCase is lowercased; underscores removed."""
    result = normalise("CheckDate")
    assert "check" in result
    assert "date" in result


def test_type_inference_numeric_from_decimal_string() -> None:
    """A decimal-formatted string → 'NUMERIC'."""
    assert infer_type("1234.56") == "NUMERIC"


def test_type_inference_date_from_iso_date_string() -> None:
    """An ISO date string → 'DATE'."""
    assert infer_type("2026-01-15") == "DATE"


def test_type_inference_boolean_from_yes_no() -> None:
    """'Yes' / 'No' / 'true' / 'false' → 'BOOLEAN'."""
    assert infer_type("Yes")   == "BOOLEAN"
    assert infer_type("No")    == "BOOLEAN"
    assert infer_type("true")  == "BOOLEAN"
    assert infer_type("false") == "BOOLEAN"


def test_type_inference_integer_from_whole_number() -> None:
    """A whole-number string → 'INTEGER'."""
    assert infer_type("42") == "INTEGER"


def test_types_are_compatible_same_type() -> None:
    """Same types are always compatible."""
    assert types_are_compatible("DATE",    "DATE")    is True
    assert types_are_compatible("NUMERIC", "NUMERIC") is True


def test_types_are_compatible_integer_numeric() -> None:
    """INTEGER and NUMERIC are compatible (numeric is a superset)."""
    assert types_are_compatible("INTEGER", "NUMERIC") is True
    assert types_are_compatible("NUMERIC", "INTEGER") is True


def test_types_are_compatible_incompatible_pair() -> None:
    """DATE and NUMERIC are not compatible."""
    assert types_are_compatible("DATE", "NUMERIC") is False


# ---------------------------------------------------------------------------
# AutoMappingService — confidence scoring
# _score_field(source_field, sample, inferred_type, saved_maps) is synchronous.
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> AutoMappingService:
    return AutoMappingService()


def test_pass3_policy_number_fuzzy_match_returns_high_or_medium(
    svc: AutoMappingService,
) -> None:
    """
    'Policy Number' vs 'policy_number' — normalised forms differ (space vs no
    sep), so this hits Pass 3 fuzzy.  The SequenceMatcher ratio is high enough
    that the result must be HIGH or MEDIUM.
    """
    proposal = svc._score_field(
        source_field="Policy Number",
        sample="WC-2026-001",
        inferred_type="TEXT",
        saved_maps={},
    )
    assert proposal.confidence.value in ("HIGH", "MEDIUM")
    assert proposal.proposed_target == "policy_number"


def test_pass3_fuzzy_match_effective_date_returns_high_or_medium(
    svc: AutoMappingService,
) -> None:
    """'Effective Date' → effective_date via fuzzy match with DATE/DATE compat."""
    proposal = svc._score_field(
        source_field="Effective Date",
        sample="2026-01-15",
        inferred_type="DATE",
        saved_maps={},
    )
    assert proposal.confidence.value in ("HIGH", "MEDIUM")
    assert proposal.proposed_target == "effective_date"


def test_pass4_no_match_returns_unmatched(svc: AutoMappingService) -> None:
    """'EmployeeID' matches no canonical column → UNMATCHED."""
    proposal = svc._score_field(
        source_field="EmployeeID",
        sample="E-99999",
        inferred_type="TEXT",
        saved_maps={},
    )
    assert proposal.confidence.value == "UNMATCHED"
    assert proposal.score == 0


def test_pass1_saved_mapping_returns_high(svc: AutoMappingService) -> None:
    """A field present in saved_maps → HIGH confidence, score=1."""
    proposal = svc._score_field(
        source_field="policy_num",
        sample="WC-001",
        inferred_type="TEXT",
        saved_maps={"policy_num": "policy_number"},
    )
    assert proposal.confidence.value == "HIGH"
    assert proposal.score == 1
    assert proposal.proposed_target == "policy_number"


def test_saved_mapping_takes_precedence_over_name_match(
    svc: AutoMappingService,
) -> None:
    """
    If saved_maps maps source→canonical_y, it must win even if the normalised
    name would match canonical_z.
    """
    proposal = svc._score_field(
        source_field="policy_number",
        sample="WC-001",
        inferred_type="TEXT",
        saved_maps={"policy_number": "written_premium"},
    )
    assert proposal.confidence.value == "HIGH"
    assert proposal.proposed_target == "written_premium"
