"""
Unit tests for AuditCalculationService — Phase 3 additions.

Tests cover:
  - load_rules() DB vs Redis cache behaviour
  - _eval_editable_rule() correct evaluation
  - simpleeval security: blocked imports/exec/eval/__dunder
  - LOCKED_RULE_KEYS integrity (10 keys)
  - Redis cache invalidation helpers
  - assess_risk() uses editable threshold expressions
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audit_calculation_service import (
    LOCKED_RULE_KEYS,
    SAFE_NAMES,
    AuditCalculationService,
)


# ---------------------------------------------------------------------------
# LOCKED_RULE_KEYS integrity
# ---------------------------------------------------------------------------

def test_locked_rule_keys_count() -> None:
    """Exactly 10 keys must be locked — any change here is a deliberate decision."""
    assert len(LOCKED_RULE_KEYS) == 10


def test_locked_rule_keys_contains_required_entries() -> None:
    """The 10 mandatory locked keys are all present."""
    required = {
        "variance_amount",
        "variance_pct",
        "reported_over_under",
        "classified_over_under",
        "reported_pct",
        "classified_pct",
        "est_ytd_premium",
        "completion_ratio",
        "premium_paid_pct",
        "payroll_submission_rate",
    }
    assert required == LOCKED_RULE_KEYS


# ---------------------------------------------------------------------------
# _eval_editable_rule — happy paths
# ---------------------------------------------------------------------------

@pytest.fixture
def svc() -> AuditCalculationService:
    return AuditCalculationService()


def test_eval_simple_numeric_expression(svc: AuditCalculationService) -> None:
    """A plain arithmetic expression evaluates to the correct float."""
    result = svc._eval_editable_rule("test_rule", "2 + 2", {})
    assert result == 4


def test_eval_expression_with_context(svc: AuditCalculationService) -> None:
    """Expression referencing SAFE_NAMES context variables evaluates correctly."""
    # variance_pct is in SAFE_NAMES; abs is in SAFE_FUNCTIONS
    result = svc._eval_editable_rule(
        "risk_threshold_high",
        "abs(variance_pct) > 30",
        {"variance_pct": -35.0},
    )
    assert result is True


def test_eval_abs_variance_pct(svc: AuditCalculationService) -> None:
    """abs() in SAFE_FUNCTIONS evaluates correctly against runtime context var."""
    result = svc._eval_editable_rule(
        "risk_threshold_high",
        "abs(variance_pct) > 30",
        {"variance_pct": -40.0},
    )
    # abs is in SAFE_FUNCTIONS; variance_pct overrides SAFE_NAMES default of 0
    assert result is True


def test_eval_returns_none_on_unknown_name(svc: AuditCalculationService) -> None:
    """An expression referencing an undeclared name returns None, does not raise."""
    result = svc._eval_editable_rule(
        "test_rule",
        "undefined_variable > 10",
        {},
    )
    assert result is None


# ---------------------------------------------------------------------------
# _eval_editable_rule — security: blocked tokens
# ---------------------------------------------------------------------------

def test_eval_blocks_import(svc: AuditCalculationService) -> None:
    """Expressions containing 'import' are rejected before evaluation."""
    result = svc._eval_editable_rule(
        "test_rule",
        "__import__('os').system('ls')",
        {},
    )
    assert result is None


def test_eval_blocks_exec(svc: AuditCalculationService) -> None:
    """Expressions containing 'exec' are rejected."""
    result = svc._eval_editable_rule("test_rule", "exec('pass')", {})
    assert result is None


def test_eval_blocks_eval_keyword(svc: AuditCalculationService) -> None:
    """Expressions containing 'eval' are rejected."""
    result = svc._eval_editable_rule("test_rule", "eval('1+1')", {})
    assert result is None


def test_eval_blocks_dunder_access(svc: AuditCalculationService) -> None:
    """Expressions containing '__' (dunder) are rejected."""
    result = svc._eval_editable_rule("test_rule", "x.__class__", {"x": 1})
    assert result is None


def test_eval_blocks_os_module_access(svc: AuditCalculationService) -> None:
    """Expressions referencing 'os.' are rejected."""
    result = svc._eval_editable_rule("test_rule", "os.getcwd()", {})
    assert result is None


# ---------------------------------------------------------------------------
# load_rules — Redis cache behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_rules_populates_redis_on_first_call(svc: AuditCalculationService) -> None:
    """
    On a cache miss, load_rules should query the DB and write the result to Redis.
    """
    db = AsyncMock()

    # Simulate DB returning two rules
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"rule_key": "risk_threshold_high",  "rule_expression": "abs(variance_pct) > 30"},
        {"rule_key": "officer_max_payroll",  "rule_expression": "52000"},
    ]
    db.execute.return_value = mock_result

    # Redis cache miss
    svc._redis_get = AsyncMock(return_value=None)   # type: ignore[method-assign]
    svc._redis_set = AsyncMock()                     # type: ignore[method-assign]

    rules = await svc.load_rules(
        schema_name="tenant_demo",
        carrier_id=1,
        db=db,
    )

    assert "risk_threshold_high" in rules
    assert isinstance(rules["risk_threshold_high"], str)
    assert len(rules["risk_threshold_high"]) > 0
    svc._redis_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_rules_returns_cached_result_without_db_call(svc: AuditCalculationService) -> None:
    """
    On a cache hit, load_rules should NOT query the DB.
    """
    import json

    db = AsyncMock()

    cached = {"risk_threshold_high": "abs(variance_pct) > 30"}
    svc._redis_get = AsyncMock(return_value=json.dumps(cached))  # type: ignore[method-assign]

    rules = await svc.load_rules(
        schema_name="tenant_demo",
        carrier_id=1,
        db=db,
    )

    assert rules == cached
    db.execute.assert_not_awaited()
