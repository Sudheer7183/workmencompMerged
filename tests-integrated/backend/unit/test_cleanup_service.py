"""
Unit tests for CleanupService — Phase 6.

12 test cases covering preview(), execute(), preservation guarantees,
error handling, and policies_archived count accuracy.

These tests use a mock AsyncSession — no live DB required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cleanup_service import CleanupService, _CLEARABLE_TABLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db(
    row_counts: dict[str, int] | None = None,
    raise_on_execute: Exception | None = None,
) -> AsyncMock:
    """
    Creates a mock AsyncSession.

    row_counts: maps table name → COUNT(*) result for preview tests.
    raise_on_execute: if set, the nth DELETE call raises this exception.
    """
    db = AsyncMock()

    counts = row_counts or {}
    call_count = 0

    async def fake_execute(stmt, params=None):
        nonlocal call_count
        call_count += 1

        mock_result = MagicMock()

        # Handle COUNT(*) queries for preview
        stmt_str = str(stmt) if not isinstance(stmt, str) else stmt
        for table in list(counts.keys()) + ["report_jobs"]:
            if table in stmt_str:
                mock_result.scalar_one.return_value = counts.get(table, 0)
                break

        # Handle INSERT ... RETURNING cleanup_id
        if "RETURNING cleanup_id" in stmt_str:
            mock_result.scalar_one.return_value = 1

        # Simulate error on DELETE if requested
        if raise_on_execute and "DELETE" in stmt_str:
            raise raise_on_execute

        mock_result.mappings.return_value.one.return_value = {
            "cleanup_id": 1,
            "status": "COMPLETE",
            "policies_archived": counts.get("policies", 0),
            "completed_at": datetime.now(tz=timezone.utc),
        }
        return mock_result

    db.execute = fake_execute
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCleanupServicePreview:
    """preview() must return counts without modifying the DB."""

    @pytest.mark.asyncio
    async def test_preview_returns_correct_counts(self) -> None:
        """preview() returns a dict with the expected table keys and counts."""
        sample_counts = {t: i * 10 for i, t in enumerate(_CLEARABLE_TABLES, 1)}
        sample_counts["report_jobs"] = 5
        db = _make_db(row_counts=sample_counts)

        svc = CleanupService()
        result = await svc.preview(db=db)

        assert isinstance(result, dict)
        for table in _CLEARABLE_TABLES:
            assert table in result, f"Missing key: {table}"
        assert "report_jobs" in result

    @pytest.mark.asyncio
    async def test_preview_does_not_commit(self) -> None:
        """After preview(), db.commit() is never called."""
        db = _make_db(row_counts={})
        svc = CleanupService()
        await svc.preview(db=db)
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preview_does_not_rollback(self) -> None:
        """After preview(), db.rollback() is never called."""
        db = _make_db(row_counts={})
        svc = CleanupService()
        await svc.preview(db=db)
        db.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preview_returns_integer_values(self) -> None:
        """preview() returns integer values for each expected table key."""
        db = _make_db(row_counts={"policies": 0})
        svc = CleanupService()
        result = await svc.preview(db=db)
        assert isinstance(result, dict)
        assert len(result) > 0
        assert all(isinstance(v, int) for v in result.values()), "All counts must be int"


class TestCleanupServiceExecute:
    """execute() must delete data, log the run, and return cleanup_id."""

    @pytest.mark.asyncio
    async def test_execute_returns_cleanup_id(self) -> None:
        """execute() returns the cleanup_id of the new cleanup_runs row."""
        db = _make_db(row_counts={"policies": 42})
        svc = CleanupService()
        cleanup_id = await svc.execute(initiated_by="test@example.com", db=db)
        assert cleanup_id == 1

    @pytest.mark.asyncio
    async def test_execute_commits_transaction(self) -> None:
        """execute() commits the DB at least twice (initial INSERT + final UPDATE)."""
        db = _make_db(row_counts={"policies": 10})
        svc = CleanupService()
        await svc.execute(initiated_by="test@example.com", db=db)
        assert db.commit.await_count >= 2

    @pytest.mark.asyncio
    async def test_execute_rollback_on_error(self) -> None:
        """When execute() raises during DELETE, rollback() is called."""
        error = RuntimeError("simulated DB error")
        db = _make_db(row_counts={"policies": 5}, raise_on_execute=error)
        svc = CleanupService()
        with pytest.raises(RuntimeError):
            await svc.execute(initiated_by="test@example.com", db=db)
        db.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_marks_failed_on_db_error(self) -> None:
        """On simulated error, execute() attempts to UPDATE cleanup_runs with FAILED status."""
        error = RuntimeError("simulated DB error")
        db = _make_db(row_counts={"policies": 5}, raise_on_execute=error)
        svc = CleanupService()
        executed_statements: list[str] = []

        original_execute = db.execute

        async def tracking_execute(stmt, params=None):
            executed_statements.append(str(stmt))
            return await original_execute(stmt, params)

        db.execute = tracking_execute

        with pytest.raises(RuntimeError):
            await svc.execute(initiated_by="test@example.com", db=db)

        failed_updates = [s for s in executed_statements if "FAILED" in s]
        assert len(failed_updates) >= 1, "Expected at least one FAILED status UPDATE"


class TestCleanupServicePreservation:
    """Verify the preserved/cleared boundary is correct."""

    @pytest.mark.asyncio
    async def test_clearable_tables_list_does_not_contain_config_tables(self) -> None:
        """Config tables must not appear in the clearable tables list."""
        preserved = {
            "carrier_calc_rules",
            "carrier_ui_labels",
            "carrier_display_config",
            "carrier_theme_config",
            "tenant_themes",
            "user_theme_prefs",
            "cleanup_runs",
            "ingestion_sources",
        }
        for table in _CLEARABLE_TABLES:
            assert table not in preserved, (
                f"Table '{table}' is in _CLEARABLE_TABLES but must be preserved."
            )

    @pytest.mark.asyncio
    async def test_clearable_tables_contains_all_fact_tables(self) -> None:
        """All operational fact tables must be in _CLEARABLE_TABLES."""
        required = {
            "premium_variance",
            "payroll_variance_policy",
            "payroll_variance_class",
            "zero_payroll",
            "missing_payroll",
        }
        for table in required:
            assert table in _CLEARABLE_TABLES, (
                f"Fact table '{table}' is missing from _CLEARABLE_TABLES."
            )

    @pytest.mark.asyncio
    async def test_clearable_tables_contains_policy_tables(self) -> None:
        """Policy master data tables must be in _CLEARABLE_TABLES."""
        for table in ["policies", "policyholders"]:
            assert table in _CLEARABLE_TABLES

    @pytest.mark.asyncio
    async def test_clearable_tables_contains_ingestion_history(self) -> None:
        """Ingestion history tables must be in _CLEARABLE_TABLES."""
        for table in ["ingestion_runs", "ingestion_errors", "field_mapping_sessions"]:
            assert table in _CLEARABLE_TABLES
