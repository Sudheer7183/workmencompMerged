from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Identity, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Policyholder(Base):
    """Tenant schema: policyholders — one row per insured entity per carrier."""

    __tablename__ = "policyholders"

    policyholder_id: Mapped[int] = mapped_column(
        BigInteger(), Identity(always=False), primary_key=True
    )
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    fein: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class Policy(Base):
    """
    Tenant schema: policies — master policy record.
    carrier_id is the sub-dimension within the tenant schema.
    Every query against this table MUST filter by carrier_id.
    """

    __tablename__ = "policies"

    policy_id: Mapped[int] = mapped_column(
        BigInteger(), Identity(always=False), primary_key=True
    )
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    policyholder_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    policy_number: Mapped[str] = mapped_column(Text(), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    cancellation_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    premium_written: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    payment_frequency: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    owner_status: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    policy_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="Active")
    audit_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="Pending")
    risk_level: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    total_est_payroll: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
