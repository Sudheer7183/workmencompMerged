"""
Unit tests for AuditCalculationService — 18 cases covering all pipeline steps.
These tests do NOT require a database connection.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.audit_calculation_service import (
    AuditCalculationService,
    CalculationContext,
    RuleConstants,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(**kwargs) -> CalculationContext:
    defaults = dict(
        policy_id=1,
        carrier_id=1,
        ingestion_run_id=1,
        policy_number="TEST-001",
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        payment_frequency="Monthly",
        owner_status="Included",
        est_premium_end=Decimal("100000"),
        actual_premium=Decimal("115000"),
        est_payroll=Decimal("500000"),
        actual_payroll_reported=Decimal("540000"),
        actual_payroll_classified=Decimal("530000"),
        submitted_count=10,
        run_date=date(2024, 7, 1),
    )
    defaults.update(kwargs)
    return CalculationContext(**defaults)


svc = AuditCalculationService()


# ============================================================================
# 1. calc_premium_variance — standard case
# ============================================================================
def test_calc_premium_variance_standard():
    ctx = _make_context(est_premium_end=Decimal("100000"), actual_premium=Decimal("115000"))
    result = svc.calc_premium_variance(ctx)
    assert result.variance_amount == Decimal("15000")
    assert result.variance_pct is not None
    assert abs(result.variance_pct - Decimal("0.15")) < Decimal("0.0001")


# ============================================================================
# 2. calc_premium_variance — zero est returns NULL pct
# ============================================================================
def test_calc_premium_variance_zero_est_returns_null_pct():
    ctx = _make_context(est_premium_end=Decimal("0"), actual_premium=Decimal("5000"))
    result = svc.calc_premium_variance(ctx)
    assert result.variance_amount == Decimal("5000")
    assert result.variance_pct is None


# ============================================================================
# 3. calc_premium_variance — negative variance (actual < est)
# ============================================================================
def test_calc_premium_variance_negative():
    ctx = _make_context(est_premium_end=Decimal("100000"), actual_premium=Decimal("90000"))
    result = svc.calc_premium_variance(ctx)
    assert result.variance_amount == Decimal("-10000")
    assert result.variance_pct is not None
    assert result.variance_pct < 0


# ============================================================================
# 4. calc_premium_variance — None inputs return zero / None
# ============================================================================
def test_calc_premium_variance_none_inputs():
    ctx = _make_context(est_premium_end=None, actual_premium=None)
    result = svc.calc_premium_variance(ctx)
    assert result.variance_amount == Decimal("0")
    assert result.variance_pct is None


# ============================================================================
# 5. calc_payroll_variance — standard case
# ============================================================================
def test_calc_payroll_variance_standard():
    ctx = _make_context(
        est_payroll=Decimal("500000"),
        actual_payroll_reported=Decimal("540000"),
        actual_payroll_classified=Decimal("530000"),
    )
    result = svc.calc_payroll_variance(ctx)
    assert result.reported_over_under == Decimal("40000")
    assert result.classified_over_under == Decimal("30000")
    assert result.reported_pct is not None
    assert result.classified_pct is not None


# ============================================================================
# 6. calc_payroll_variance — zero est returns NULL pcts
# ============================================================================
def test_calc_payroll_variance_zero_est():
    ctx = _make_context(
        est_payroll=Decimal("0"),
        actual_payroll_reported=Decimal("10000"),
        actual_payroll_classified=Decimal("10000"),
    )
    result = svc.calc_payroll_variance(ctx)
    assert result.reported_pct is None
    assert result.classified_pct is None
    assert result.reported_over_under == Decimal("10000")


# ============================================================================
# 7. assess_risk — high: pct > 30% AND missing > 0
# ============================================================================
def test_assess_risk_high():
    from app.services.audit_calculation_service import PremiumVarianceResult
    pv = PremiumVarianceResult(
        variance_amount=Decimal("50000"),
        variance_pct=Decimal("0.50"),  # 50% — above 30% threshold
    )
    result = svc.assess_risk(pv, missing_payroll_count=3, rules={})
    assert result.risk_level == "High"


# ============================================================================
# 8. assess_risk — medium: pct > 30% but no missing
# ============================================================================
def test_assess_risk_medium_variance_only():
    from app.services.audit_calculation_service import PremiumVarianceResult
    pv = PremiumVarianceResult(variance_amount=Decimal("50000"), variance_pct=Decimal("0.50"))
    result = svc.assess_risk(pv, missing_payroll_count=0, rules={})
    assert result.risk_level == "Medium"


# ============================================================================
# 9. assess_risk — medium: missing > 0 but pct ≤ 30%
# ============================================================================
def test_assess_risk_medium_missing_only():
    from app.services.audit_calculation_service import PremiumVarianceResult
    pv = PremiumVarianceResult(variance_amount=Decimal("5000"), variance_pct=Decimal("0.05"))
    result = svc.assess_risk(pv, missing_payroll_count=2, rules={})
    assert result.risk_level == "Medium"


# ============================================================================
# 10. assess_risk — low: both conditions false
# ============================================================================
def test_assess_risk_low():
    from app.services.audit_calculation_service import PremiumVarianceResult
    pv = PremiumVarianceResult(variance_amount=Decimal("1000"), variance_pct=Decimal("0.01"))
    result = svc.assess_risk(pv, missing_payroll_count=0, rules={})
    assert result.risk_level == "Low"


# ============================================================================
# 11. assess_risk — NULL variance_pct treated as not-exceeded
# ============================================================================
def test_assess_risk_null_pct_with_no_missing():
    from app.services.audit_calculation_service import PremiumVarianceResult
    pv = PremiumVarianceResult(variance_amount=Decimal("0"), variance_pct=None)
    result = svc.assess_risk(pv, missing_payroll_count=0, rules={})
    assert result.risk_level == "Low"


# ============================================================================
# 12. check_frequency — monthly: 12 expected submissions
# ============================================================================
def test_check_frequency_monthly():
    ctx = _make_context(
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        payment_frequency="Monthly",
        submitted_count=10,
    )
    result = svc.check_frequency(ctx, rules={})
    assert result.cycle_days == 30
    assert result.expected_submissions is not None
    assert result.expected_submissions > 0


# ============================================================================
# 13. check_frequency — weekly: more expected submissions
# ============================================================================
def test_check_frequency_weekly():
    ctx = _make_context(
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        payment_frequency="Weekly",
        submitted_count=20,
    )
    monthly_ctx = _make_context(
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        payment_frequency="Monthly",
        submitted_count=20,
    )
    weekly = svc.check_frequency(ctx, rules={})
    monthly = svc.check_frequency(monthly_ctx, rules={})
    assert (weekly.expected_submissions or 0) > (monthly.expected_submissions or 0)


# ============================================================================
# 14. check_frequency — None dates returns None expected_submissions
# ============================================================================
def test_check_frequency_none_dates():
    ctx = _make_context(effective_date=None, expiration_date=None)
    result = svc.check_frequency(ctx, rules={})
    assert result.expected_submissions is None
    assert result.submission_rate is None


# ============================================================================
# 15. RuleConstants values match V9 S18.3
# ============================================================================
def test_rule_constants_values():
    assert RuleConstants.OFFICER_MAX_PAYROLL == Decimal("52000")
    assert RuleConstants.OFFICER_MIN_PAYROLL == Decimal("15600")
    assert RuleConstants.RISK_THRESHOLD_HIGH_PCT == Decimal("30")
    assert RuleConstants.CYCLE_WEEKLY_DAYS == 7
    assert RuleConstants.CYCLE_BIWEEKLY_DAYS == 14
    assert RuleConstants.CYCLE_SEMIMONTHLY_DAYS == 15
    assert RuleConstants.CYCLE_MONTHLY_DAYS == 30


# ============================================================================
# 16. check_officer_rules — Phase 1 stub returns within_bounds=True
# ============================================================================
def test_check_officer_rules_phase1_stub():
    ctx = _make_context()
    result = svc.check_officer_rules(ctx, rules={})
    assert result.officer_within_bounds is True


# ============================================================================
# 17. calc_premium_variance — exact equality check
# ============================================================================
def test_calc_premium_variance_exact():
    ctx = _make_context(est_premium_end=Decimal("200000"), actual_premium=Decimal("200000"))
    result = svc.calc_premium_variance(ctx)
    assert result.variance_amount == Decimal("0")
    assert result.variance_pct == Decimal("0")


# ============================================================================
# 18. calc_payroll_variance — None payroll defaults to zero
# ============================================================================
def test_calc_payroll_variance_none_classified():
    ctx = _make_context(
        est_payroll=Decimal("100000"),
        actual_payroll_reported=Decimal("110000"),
        actual_payroll_classified=None,
    )
    result = svc.calc_payroll_variance(ctx)
    assert result.classified_over_under == Decimal("-100000")  # 0 - 100000
