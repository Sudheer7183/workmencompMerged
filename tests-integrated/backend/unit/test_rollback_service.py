"""
Phase 4 — Unit tests: RollbackService structure.

V9 S17.5: RollbackService deletes only fact table rows.
The run record and error history are preserved.
"""
from __future__ import annotations

import pytest

from app.services.rollback_service import RollbackService, ROLLBACK_TABLES


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_rollback_service_instantiates() -> None:
    svc = RollbackService()
    assert svc is not None


def test_rollback_service_has_rollback_method() -> None:
    assert callable(RollbackService().rollback)


def test_rollback_service_has_can_rollback_method() -> None:
    assert callable(RollbackService().can_rollback)


# ---------------------------------------------------------------------------
# ROLLBACK_TABLES — V9 S17.5 specifies exactly 5 fact tables
# ---------------------------------------------------------------------------

def test_rollback_tables_has_five_tables() -> None:
    assert len(ROLLBACK_TABLES) == 5, f"Expected 5, got {len(ROLLBACK_TABLES)}"


def test_rollback_tables_contains_premium_variance() -> None:
    assert "premium_variance" in ROLLBACK_TABLES


def test_rollback_tables_contains_payroll_variance_policy() -> None:
    assert "payroll_variance_policy" in ROLLBACK_TABLES


def test_rollback_tables_contains_payroll_variance_class() -> None:
    assert "payroll_variance_class" in ROLLBACK_TABLES


def test_rollback_tables_contains_zero_payroll() -> None:
    assert "zero_payroll" in ROLLBACK_TABLES


def test_rollback_tables_contains_missing_payroll() -> None:
    assert "missing_payroll" in ROLLBACK_TABLES


# ---------------------------------------------------------------------------
# Tables NOT deleted (audit history must be preserved)
# ---------------------------------------------------------------------------

def test_ingestion_runs_not_in_rollback_tables() -> None:
    """The run record itself is preserved as the audit trail."""
    assert "ingestion_runs" not in ROLLBACK_TABLES


def test_ingestion_errors_not_in_rollback_tables() -> None:
    """Error records are historical — must not be deleted."""
    assert "ingestion_errors" not in ROLLBACK_TABLES


def test_ingestion_skipped_rows_not_in_rollback_tables() -> None:
    """Skipped row records are historical — must not be deleted."""
    assert "ingestion_skipped_rows" not in ROLLBACK_TABLES


def test_policies_not_in_rollback_tables() -> None:
    """Policy master data is shared across runs — must not be deleted."""
    assert "policies" not in ROLLBACK_TABLES


def test_policyholders_not_in_rollback_tables() -> None:
    """Policyholder master data is shared across runs — must not be deleted."""
    assert "policyholders" not in ROLLBACK_TABLES
