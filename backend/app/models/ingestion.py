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


# ---------------------------------------------------------------------------
# Phase 4 — New ORM models for tables that existed in schema but lacked models
# ---------------------------------------------------------------------------

class IngestionSkippedRow(Base):
    """
    Tenant schema: ingestion_skipped_rows.
    One row per skipped row during ingestion when skip_on_error=TRUE.
    resolution_status lifecycle: PENDING → CORRECTED | DISMISSED.
    """

    __tablename__ = "ingestion_skipped_rows"

    skip_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    skip_reason: Mapped[str] = mapped_column(Text(), nullable=False)
    error_codes: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False, server_default="{}")
    resolution_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="PENDING")
    corrected_data: Mapped[Optional[dict]] = mapped_column(JSONB(), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class IngestionRollback(Base):
    """
    Tenant schema: ingestion_rollbacks.
    One row per rollback initiated for an ingestion run.
    The ingestion_run row itself is NOT deleted — it stays as an audit trail
    with status='rolled_back'. Fact table rows ARE deleted by RollbackService.
    """

    __tablename__ = "ingestion_rollbacks"

    rollback_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    initiated_by: Mapped[str] = mapped_column(Text(), nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="IN_PROGRESS")
    rows_removed: Mapped[Optional[int]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)


class IngestionFieldMap(Base):
    """
    Tenant schema: ingestion_field_maps.
    Pre-configured canonical mappings per carrier + file_type.
    Used as Pass 1 (saved mapping = HIGH confidence) by AutoMappingService.
    Populated via Tab 2 (Field Mapping pre-config) in CarrierConfigHub.

    V9 S11.9 column spec: file_type, source_field, target_column, transform_fn.
    Uniqueness: (carrier_id, source_field) — one canonical target per source field per carrier.
    """

    __tablename__ = "ingestion_field_maps"

    map_id: Mapped[int] = mapped_column(BigInteger(), Identity(always=False), primary_key=True)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default="xlsx")
    source_field: Mapped[str] = mapped_column(Text(), nullable=False)
    target_column: Mapped[str] = mapped_column(Text(), nullable=False)
    transform_fn: Mapped[str] = mapped_column(Text(), nullable=False, server_default="as-is")
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    created_at: Mapped[datetime] = mapped_column(nullable=False)
