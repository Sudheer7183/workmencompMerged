from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PolicyListItem(BaseModel):
    """One row in the Policies List DataTable — 11 columns."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    policy_number: str
    insured_name: str
    state_code: Optional[str]
    effective_date: Optional[date]
    policy_status: str
    # est_premium_end sourced from premium_variance latest run
    est_premium: Optional[Decimal]
    # variance_amount is GENERATED — always available
    variance_amount: Optional[Decimal]
    # variance_pct is engine-derived — NULL when engine off
    variance_pct: Optional[Decimal]
    risk_level: Optional[str]
    audit_status: str


class PolicyListResponse(BaseModel):
    """Paginated response for the Policies List screen."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PolicyListItem]
    total: int
    page: int
    page_size: int


class PolicyMetaCard(BaseModel):
    """
    11-field meta card shown at the top of the Policy Detail screen.
    total_est_payroll is NULL until the calc engine has run.
    """

    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    policy_number: str
    insured_name: str
    fein: Optional[str]
    state_code: Optional[str]
    effective_date: Optional[date]
    expiration_date: Optional[date]
    cancellation_date: Optional[date]
    policy_status: str
    payment_frequency: Optional[str]
    owner_status: Optional[str]
    audit_status: str
    # Engine-derived — NaIndicator renders N/A when NULL
    total_est_payroll: Optional[Decimal]


class PolicyDetailResponse(BaseModel):
    """Full Policy Detail screen response — meta card + engine_on flag."""

    model_config = ConfigDict(from_attributes=True)

    meta: PolicyMetaCard
    # engine_on drives NaIndicator rendering across all 4 tabs
    engine_on: bool
    latest_run_id: Optional[int]
