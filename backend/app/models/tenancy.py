from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Identity, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublicTenant(Base):
    """
    public.tenants — platform-wide tenant registry.
    slug is the primary key and the source of truth for schema_name derivation.
    No tenant_id integer — slug IS the identifier throughout the platform.
    """

    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    slug: Mapped[str] = mapped_column(Text(), primary_key=True)
    schema_name: Mapped[str] = mapped_column(Text(), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    tenant_type: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="PROVISIONING")
    config: Mapped[Optional[dict]] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE" and self.deleted_at is None


class PublicCarrier(Base):
    """
    public.carriers — platform-wide carrier registry.
    Carriers are shared across tenants; tenant_carriers (tenant schema) provides
    the many-to-many relationship.
    """

    __tablename__ = "carriers"
    __table_args__ = {"schema": "public"}

    carrier_id: Mapped[int] = mapped_column(
        BigInteger(), Identity(always=False), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    slug: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    contact_email: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    ai_narrative_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="TRUE"
    )
