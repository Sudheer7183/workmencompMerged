"""
Phase 4 — Unit tests: ORM model imports and structure.

Verifies that the three new models are importable, have correct table names,
and expose the columns defined in V9 S11.9.
"""
from __future__ import annotations

import pytest

from app.models.ingestion import (
    IngestionSkippedRow,
    IngestionRollback,
    IngestionFieldMap,
    IngestionSource,
    IngestionRun,
    IngestionError,
)


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------

def test_ingestion_skipped_row_importable() -> None:
    assert IngestionSkippedRow is not None


def test_ingestion_rollback_importable() -> None:
    assert IngestionRollback is not None


def test_ingestion_field_map_importable() -> None:
    assert IngestionFieldMap is not None


# ---------------------------------------------------------------------------
# Table name checks
# ---------------------------------------------------------------------------

def test_ingestion_skipped_row_tablename() -> None:
    assert IngestionSkippedRow.__tablename__ == "ingestion_skipped_rows"


def test_ingestion_rollback_tablename() -> None:
    assert IngestionRollback.__tablename__ == "ingestion_rollbacks"


def test_ingestion_field_map_tablename() -> None:
    assert IngestionFieldMap.__tablename__ == "ingestion_field_maps"


# ---------------------------------------------------------------------------
# IngestionSkippedRow column checks — V9 S11.9
# ---------------------------------------------------------------------------

def test_ingestion_skipped_row_has_required_columns() -> None:
    cols = {c.key for c in IngestionSkippedRow.__table__.columns}
    required = {"skip_id", "run_id", "row_number", "raw_data", "skip_reason",
                "error_codes", "resolution_status", "corrected_data",
                "resolved_by", "resolved_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"


# ---------------------------------------------------------------------------
# IngestionRollback column checks — V9 S11.9
# ---------------------------------------------------------------------------

def test_ingestion_rollback_has_required_columns() -> None:
    cols = {c.key for c in IngestionRollback.__table__.columns}
    required = {"rollback_id", "run_id", "initiated_by", "initiated_at",
                "status", "rows_removed", "completed_at", "error_detail"}
    assert required.issubset(cols), f"Missing: {required - cols}"


# ---------------------------------------------------------------------------
# IngestionFieldMap column checks — V9 S11.9
# target_column + transform_fn (not canonical_column)
# ---------------------------------------------------------------------------

def test_ingestion_field_map_has_target_column() -> None:
    """V9 S11.9 uses target_column, not canonical_column."""
    cols = {c.key for c in IngestionFieldMap.__table__.columns}
    assert "target_column" in cols, "target_column missing from IngestionFieldMap"


def test_ingestion_field_map_has_transform_fn() -> None:
    """V9 S11.9 requires transform_fn column."""
    cols = {c.key for c in IngestionFieldMap.__table__.columns}
    assert "transform_fn" in cols, "transform_fn missing from IngestionFieldMap"


def test_ingestion_field_map_no_canonical_column() -> None:
    """canonical_column is not in V9 S11.9 spec — should not be present."""
    cols = {c.key for c in IngestionFieldMap.__table__.columns}
    assert "canonical_column" not in cols, "canonical_column should not be in IngestionFieldMap"


def test_ingestion_field_map_has_all_required_columns() -> None:
    cols = {c.key for c in IngestionFieldMap.__table__.columns}
    required = {"map_id", "carrier_id", "file_type", "source_field",
                "target_column", "transform_fn", "is_active", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"


# ---------------------------------------------------------------------------
# Phase 3 model regression
# ---------------------------------------------------------------------------

def test_phase3_models_still_importable() -> None:
    assert IngestionSource is not None
    assert IngestionRun is not None
    assert IngestionError is not None
