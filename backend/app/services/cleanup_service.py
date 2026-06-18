"""
CleanupService — Phase 6.

Implements the two-step monthly cleanup workflow described in V9 S22.

Workflow:
  1. preview()  — counts rows that WOULD be deleted. Read-only; no writes.
  2. execute()  — deletes operational data in a single transaction, then
                  logs the outcome to cleanup_runs.

What gets cleared (V9 S22.2):
  Operational fact tables:
    premium_variance, payroll_variance_policy,
    payroll_variance_class, zero_payroll, missing_payroll.
  Policy master data:
    policies, policyholders.
  Ingestion history:
    ingestion_runs, ingestion_errors, ingestion_skipped_rows,
    ingestion_rollbacks, field_mapping_sessions, field_mapping_proposals.
  Completed report jobs:
    report_jobs (status = 'COMPLETE' or 'FAILED' only).

What is ALWAYS preserved (V9 S22.3):
  Configuration:
    carrier_calc_rules, carrier_ui_labels, carrier_display_config,
    carrier_theme_config, tenant_themes, carrier_report_templates,
    user_theme_prefs.
  Tenant identity:
    users, tenant_profiles, tenant_contacts, tenant_branding, tenant_carriers.
  Ingestion config:
    ingestion_sources, ingestion_field_maps,
    carrier_calc_config, tenant_calc_config.
  Audit trail:
    cleanup_runs (NEVER deleted by the cleanup process itself).
  Public schema:
    never touched.
"""

from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tables cleared in dependency order (children before parents).
# Each entry is a plain SQL table name within the tenant schema.
# ---------------------------------------------------------------------------
_FACT_TABLES: list[str] = [
    "premium_variance",
    "payroll_variance_class",   # child of payroll_variance_policy
    "payroll_variance_policy",
    "zero_payroll",
    "missing_payroll",
]

_POLICY_TABLES: list[str] = [
    "policies",
    "policyholders",
]

_INGESTION_TABLES: list[str] = [
    "ingestion_errors",
    "ingestion_skipped_rows",
    "ingestion_rollbacks",
    "ingestion_runs",
    "field_mapping_proposals",
    "field_mapping_sessions",
]

# Report jobs — only terminal states are cleared; IN_PROGRESS rows are kept.
_REPORT_JOB_TERMINAL_STATUSES: tuple[str, ...] = ("COMPLETE", "FAILED", "CANCELLED")

# Combined ordered list for preview counts (report_jobs handled separately).
_CLEARABLE_TABLES: list[str] = _FACT_TABLES + _POLICY_TABLES + _INGESTION_TABLES


class CleanupService:
    """
    Service encapsulating the two-step database cleanup workflow.

    All operations are scoped to a single tenant schema via the
    session's search_path (already set by the DB dependency layer).
    """

    # ------------------------------------------------------------------
    # preview
    # ------------------------------------------------------------------

    async def preview(
        self,
        db: AsyncSession,
    ) -> dict[str, int]:
        """
        Returns a mapping of table name → row count for every table that
        WOULD be deleted by execute().

        This method performs only SELECT COUNT(*) queries and never modifies
        the database.

        Returns:
            dict[str, int] — e.g.
            {
                "premium_variance": 156,
                "payroll_variance_class": 88,
                ...
                "report_jobs": 12,
            }
        """
        counts: dict[str, int] = {}

        for table_name in _CLEARABLE_TABLES:
            result = await db.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
            )
            counts[table_name] = int(result.scalar_one())

        # report_jobs — only terminal states are counted
        rj_result = await db.execute(
            text(
                "SELECT COUNT(*) FROM report_jobs "
                "WHERE status = ANY(:statuses)"
            ),
            {"statuses": list(_REPORT_JOB_TERMINAL_STATUSES)},
        )
        counts["report_jobs"] = int(rj_result.scalar_one())

        logger.info("cleanup.preview.complete", counts=counts)
        return counts

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        initiated_by: str,
        db: AsyncSession,
    ) -> int:
        """
        Deletes all operational data within the tenant schema in a single
        transaction, then records the outcome in cleanup_runs.

        Steps (V9 S22.5):
          1. INSERT into cleanup_runs with status='IN_PROGRESS' → get cleanup_id
          2. DELETE operational data in dependency order
          3. UPDATE cleanup_runs: status='COMPLETE', policies_archived=N

        On any exception:
          - ROLLBACK the delete transaction
          - UPDATE cleanup_runs status='FAILED' with error_detail
          - Re-raise the exception so the API layer returns HTTP 500

        Returns:
            int — cleanup_id of the newly created cleanup_runs row.
        """
        now = datetime.now(tz=timezone.utc)

        # Step 1 — create the in-progress cleanup run record.
        # This INSERT is committed immediately so that a subsequent failure
        # can still update it to FAILED even after a rollback.
        insert_result = await db.execute(
            text(
                """
                INSERT INTO cleanup_runs (initiated_by, initiated_at, status)
                VALUES (:initiated_by, :initiated_at, 'IN_PROGRESS')
                RETURNING cleanup_id
                """
            ),
            {"initiated_by": initiated_by, "initiated_at": now},
        )
        cleanup_id: int = int(insert_result.scalar_one())
        await db.commit()

        logger.info(
            "cleanup.execute.started",
            cleanup_id=cleanup_id,
            initiated_by=initiated_by,
        )

        policies_archived: int = 0

        try:
            # Step 2 — delete operational data in dependency order.
            for table_name in _FACT_TABLES:
                await db.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608

            # Count policy rows before deleting (for policies_archived).
            count_result = await db.execute(text("SELECT COUNT(*) FROM policies"))
            policies_archived = int(count_result.scalar_one())

            for table_name in _POLICY_TABLES:
                await db.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608

            for table_name in _INGESTION_TABLES:
                await db.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608

            # Delete terminal-state report jobs only.
            await db.execute(
                text(
                    "DELETE FROM report_jobs WHERE status = ANY(:statuses)"
                ),
                {"statuses": list(_REPORT_JOB_TERMINAL_STATUSES)},
            )

            # Step 3 — mark the cleanup run as COMPLETE.
            completed_at = datetime.now(tz=timezone.utc)
            await db.execute(
                text(
                    """
                    UPDATE cleanup_runs
                    SET status = 'COMPLETE',
                        policies_archived = :policies_archived,
                        completed_at = :completed_at
                    WHERE cleanup_id = :cleanup_id
                    """
                ),
                {
                    "policies_archived": policies_archived,
                    "completed_at": completed_at,
                    "cleanup_id": cleanup_id,
                },
            )
            await db.commit()

            logger.info(
                "cleanup.execute.complete",
                cleanup_id=cleanup_id,
                policies_archived=policies_archived,
            )
            return cleanup_id

        except Exception as exc:
            await db.rollback()

            # Record the failure — use a fresh execution after rollback.
            try:
                await db.execute(
                    text(
                        """
                        UPDATE cleanup_runs
                        SET status = 'FAILED',
                            completed_at = :completed_at,
                            error_detail = :error_detail
                        WHERE cleanup_id = :cleanup_id
                        """
                    ),
                    {
                        "completed_at": datetime.now(tz=timezone.utc),
                        "error_detail": str(exc),
                        "cleanup_id": cleanup_id,
                    },
                )
                await db.commit()
            except Exception as update_exc:
                logger.error(
                    "cleanup.execute.failed_to_record_failure",
                    cleanup_id=cleanup_id,
                    original_error=str(exc),
                    update_error=str(update_exc),
                )

            logger.error(
                "cleanup.execute.failed",
                cleanup_id=cleanup_id,
                error=str(exc),
            )
            raise
