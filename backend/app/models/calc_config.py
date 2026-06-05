from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Identity, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TenantCalcConfig(Base):
    """
    Tenant schema: tenant_calc_config — tenant-level engine default.
    Single row per tenant schema. Use carrier_calc_config to override per carrier,
    or ingestion_runs.use_calculation_engine for per-run override.
    """

    __tablename__ = "tenant_calc_config"

    id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    use_calculation_engine: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class CarrierCalcConfig(Base):
    """
    Tenant schema: carrier_calc_config — carrier-level engine default.
    Overrides tenant_calc_config for this carrier.
    """

    __tablename__ = "carrier_calc_config"

    carrier_id: Mapped[int] = mapped_column(BigInteger(), primary_key=True)
    use_calculation_engine: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class CarrierCalcRule(Base):
    """
    Tenant schema: carrier_calc_rules — the 22 configurable calculation rules.
    rule_status lifecycle: DRAFT → PENDING_REVIEW → ACTIVE (two-step approval).
    LOCKED rules have is_editable = FALSE.
    """

    __tablename__ = "carrier_calc_rules"

    rule_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(Text(), nullable=False)
    rule_label: Mapped[str] = mapped_column(Text(), nullable=False)
    rule_description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    expression: Mapped[str] = mapped_column(Text(), nullable=False)
    is_editable: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    rule_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="ACTIVE")
    submitted_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(nullable=True)
