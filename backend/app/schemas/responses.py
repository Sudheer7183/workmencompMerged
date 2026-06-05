from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ============================================================================
# variance.py — Premium and Payroll variance response schemas
# ============================================================================


class PremiumVarianceResponse(BaseModel):
    """Tab 1 — Premium Variance Section: 4 horizontal cards."""

    model_config = ConfigDict(from_attributes=True)

    est_premium_end: Decimal
    actual_premium: Decimal
    # GENERATED — always non-NULL
    variance_amount: Decimal
    # Engine-derived — NULL when engine off; NaIndicator renders N/A
    variance_pct: Optional[Decimal]
    as_of_date: date


class PayrollVariancePolicyResponse(BaseModel):
    """Tab 1 — Payroll Variance Section: 7 horizontal cards."""

    model_config = ConfigDict(from_attributes=True)

    est_payroll: Decimal
    actual_payroll_reported: Decimal
    # GENERATED
    reported_over_under: Decimal
    # Engine-derived — NULL when engine off
    reported_pct: Optional[Decimal]
    actual_payroll_classified: Decimal
    # GENERATED
    classified_over_under: Decimal
    # Engine-derived — NULL when engine off
    classified_pct: Optional[Decimal]
    as_of_date: date


class ClassCodeVarianceRow(BaseModel):
    """One row in the Class Code Variance table — 9 columns."""

    model_config = ConfigDict(from_attributes=True)

    class_code: str
    description: Optional[str]
    state_code: str
    est_payroll: Decimal
    actual_reported: Decimal
    # GENERATED
    reported_over_under: Decimal
    # Engine-derived — NULL when engine off
    reported_pct: Optional[Decimal]
    actual_classified: Decimal
    # GENERATED
    classified_over_under: Decimal
    # Engine-derived — NULL when engine off
    classified_pct: Optional[Decimal]


class ClassCodeVarianceResponse(BaseModel):
    """Class Code Variance tab response."""

    model_config = ConfigDict(from_attributes=True)

    rows: list[ClassCodeVarianceRow]


# ============================================================================
# submission.py — Payroll Metrics Row (5 pills)
# ============================================================================


class PayrollMetricsResponse(BaseModel):
    """
    Tab 1 — PayrollMetricsRow: 5 pills.
    actual_received and zero_payroll_count are always available (raw counts).
    The remaining three are engine-derived.
    """

    model_config = ConfigDict(from_attributes=True)

    # Always available
    actual_received: int
    zero_payroll_count: int
    # Engine-derived — NULL when engine off
    expected_submissions: Optional[int]
    missing_payroll_count: Optional[int]
    submission_rate: Optional[Decimal]


# ============================================================================
# zero_payroll.py — Zero Payroll tab response
# ============================================================================


class ZeroPayrollRow(BaseModel):
    """One row in the Zero Payrolls table — 9 columns always available."""

    model_config = ConfigDict(from_attributes=True)

    zp_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    report_date: Optional[date]
    payroll_frequency: Optional[str]
    ingestion_run_id: int


class ZeroPayrollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rows: list[ZeroPayrollRow]
    total: int


# ============================================================================
# missing_payroll.py — Missing Payroll tab response
# ============================================================================


class MissingPayrollRow(BaseModel):
    """One row in the Missing Payrolls table — 11 columns."""

    model_config = ConfigDict(from_attributes=True)

    mp_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    payroll_frequency: Optional[str]
    days_since_last_run: Optional[int]
    ingestion_run_id: int


class MissingPayrollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rows: list[MissingPayrollRow]
    total: int


# ============================================================================
# ingestion.py — Upload request and run response
# ============================================================================


class IngestionRunResponse(BaseModel):
    """Response after a file upload triggers an ingestion run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    status: str
    rows_ingested: Optional[int]
    rows_skipped: int
    rows_failed: int
    error_detail: Optional[str]


# ============================================================================
# audit_run.py — Manual audit run trigger
# ============================================================================


class AuditRunRequest(BaseModel):
    """Body for POST /api/v1/audit/run."""

    carrier_id: int
    ingestion_run_id: int
    # None = respect carrier/tenant default; True/False = force override
    override_use_engine: Optional[bool] = None


class AuditRunResponse(BaseModel):
    """Response after the audit calculation pipeline completes."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    ingestion_run_id: int
    skipped: bool
    engine_ran: bool
    risk_level: Optional[str]
    variance_amount: Optional[Decimal]
    variance_pct: Optional[Decimal]
    missing_payroll_count: int
    zero_payroll_count: int
    narrative_generated: bool
