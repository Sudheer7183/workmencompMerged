"""
ORM model for carrier-scoped LLM configuration.

Phase 7C — one row per carrier per tenant schema.
The row is seeded as unconfigured (all nullable fields NULL) when a carrier
is added to a tenant. It is updated in-place when TENANT_ADMIN configures a provider.

The api_key_enc column stores the Fernet-encrypted API key.
The plaintext key is NEVER stored and NEVER returned in API responses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CarrierLLMConfig(Base):
    """
    {schema}.carrier_llm_config — per-carrier LLM provider configuration.

    Note: This table lives in the tenant schema (not public).
    The ORM model is used for type-safe access; raw SQL with schema prefix
    is used for cross-schema queries in the provisioning service.
    """

    __tablename__ = "carrier_llm_config"
    __table_args__ = (
        UniqueConstraint("carrier_id", name="uq_carrier_llm_config_carrier_id"),
    )

    config_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    carrier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")
