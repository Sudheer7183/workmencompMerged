from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class KpiMetrics(BaseModel):
    """Four KPI cards shown at the top of the Dashboard screen."""

    model_config = ConfigDict(from_attributes=True)

    total_book_premium: Decimal
    total_est_earned_premium: Decimal
    total_actual_earned_premium: Decimal
    # variance_amount uses the GENERATED column — always non-NULL
    total_variance_amount: Decimal


class RiskDistribution(BaseModel):
    """Risk level counts for the Policy Risk Distribution donut chart."""

    model_config = ConfigDict(from_attributes=True)

    high_count: int
    medium_count: int
    low_count: int
    unassigned_count: int


class PolicyStatusDistribution(BaseModel):
    """Active / Cancelled counts for the Policy Status Distribution donut."""

    model_config = ConfigDict(from_attributes=True)

    active_count: int
    cancelled_count: int


class StateRiskProfile(BaseModel):
    """One row in the Policies by State & Risk grouped bar chart."""

    model_config = ConfigDict(from_attributes=True)

    state_code: str
    high_count: int
    medium_count: int
    low_count: int


class TargetVarianceMetrics(BaseModel):
    """
    Two-card callout row on the Dashboard.
    Uses variance_amount (GENERATED) — never variance_pct (engine-derived).
    """

    model_config = ConfigDict(from_attributes=True)

    policies_above_threshold: int
    total_variance_above_threshold: Decimal
    threshold_pct: int = 30


class DashboardSummaryResponse(BaseModel):
    """Complete Dashboard summary response."""

    model_config = ConfigDict(from_attributes=True)

    carrier_id: int
    kpi: KpiMetrics
    policy_status: PolicyStatusDistribution
    risk_distribution: RiskDistribution
    state_risk_profiles: list[StateRiskProfile]
    target_variance: TargetVarianceMetrics
