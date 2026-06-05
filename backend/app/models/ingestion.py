from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Identity, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IngestionSource(Base):
    """Tenant schema: ingestion_sources — source file configuration per carrier."""

    __tablename__ = "ingestion_sources"

    source_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(Text(), nullable=False)
    source_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default="xlsx")
    anchor_string: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    delimiter: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class IngestionRun(Base):
    """
    Tenant schema: ingestion_runs — lifecycle record for a single file upload.
    use_calculation_engine is the per-run override (NULL = defer to carrier/tenant default).
    """

    __tablename__ = "ingestion_runs"

    run_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(Text(), nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="awaiting_mapping")
    rows_ingested: Mapped[Optional[int]] = mapped_column(nullable=True)
    rows_skipped: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    rows_failed: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    skip_on_error: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="FALSE")
    # Per-run engine mode override — three-level resolution: run → carrier → tenant
    use_calculation_engine: Mapped[Optional[bool]] = mapped_column(Boolean(), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    s3_file_key: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)


class IngestionError(Base):
    """Tenant schema: ingestion_errors — row-level errors during ingestion."""

    __tablename__ = "ingestion_errors"

    error_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    row_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    field_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    error_type: Mapped[str] = mapped_column(Text(), nullable=False)
    error_message: Mapped[str] = mapped_column(Text(), nullable=False)
    raw_value: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
