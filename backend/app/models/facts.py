from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Computed, Date, Identity, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PremiumVariance(Base):
    """
    Tenant schema: premium_variance — one row per policy per ingestion run.
    variance_amount is a GENERATED column — always available regardless of engine mode.
    variance_pct is engine-derived and will be NULL when the engine is off.
    """

    __tablename__ = "premium_variance"

    pv_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    policy_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date(), nullable=False)
    est_premium_end: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    actual_premium: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    # GENERATED — actual_premium - est_premium_end
    variance_amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        Computed("actual_premium - est_premium_end", persisted=True),
        nullable=False,
    )
    # Engine-derived — NULL when engine is off
    variance_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class PayrollVariancePolicy(Base):
    """
    Tenant schema: payroll_variance_policy — policy-level payroll summary.
    reported_over_under and classified_over_under are GENERATED columns.
    reported_pct and classified_pct are engine-derived (NULL when engine off).
    """

    __tablename__ = "payroll_variance_policy"

    pvp_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    policy_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date(), nullable=False)
    est_payroll: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    actual_payroll_reported: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    # GENERATED
    reported_over_under: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        Computed("actual_payroll_reported - est_payroll", persisted=True),
        nullable=False,
    )
    # Engine-derived — NULL when engine is off
    reported_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    actual_payroll_classified: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    # GENERATED
    classified_over_under: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        Computed("actual_payroll_classified - est_payroll", persisted=True),
        nullable=False,
    )
    # Engine-derived — NULL when engine is off
    classified_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class PayrollVarianceClass(Base):
    """
    Tenant schema: payroll_variance_class — class-code-level payroll variance.
    Finest-grain fact table; drives the Class Code Variance tab.
    """

    __tablename__ = "payroll_variance_class"

    pvc_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    policy_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    class_code_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    state_code: Mapped[str] = mapped_column(Text(), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date(), nullable=False)
    est_payroll: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default="0")
    actual_reported: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default="0")
    # GENERATED
    reported_over_under: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        Computed("actual_reported - est_payroll", persisted=True),
        nullable=False,
    )
    # Engine-derived
    reported_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    actual_classified: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default="0")
    # GENERATED
    classified_over_under: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        Computed("actual_classified - est_payroll", persisted=True),
        nullable=False,
    )
    # Engine-derived
    classified_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class ZeroPayroll(Base):
    """Tenant schema: zero_payroll — payroll submissions where wages = 0."""

    __tablename__ = "zero_payroll"

    zp_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    policy_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    policyholder_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    policy_number: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    report_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    payroll_frequency: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class MissingPayroll(Base):
    """Tenant schema: missing_payroll — detected gaps in payroll submission schedule."""

    __tablename__ = "missing_payroll"

    mp_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    policy_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    policyholder_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    policy_number: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    payroll_frequency: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    days_since_last_run: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
