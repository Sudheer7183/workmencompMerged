from __future__ import annotations

"""
RollbackService — Phase 4.

Deletes all fact rows written by a specific ingestion_run_id across
the five fact tables. The ingestion_runs row itself is NOT deleted —
it remains as an audit trail with status='rolled_back'.

Fact tables affected (V9 S17.5):
  - premium_variance
  - payroll_variance_policy
  - payroll_variance_class
  - zero_payroll
  - missing_payroll

NOT deleted:
  - ingestion_runs (status updated to 'rolled_back')
  - ingestion_errors (preserved as error history)
  - ingestion_skipped_rows (preserved as error history)
  - ingestion_rollbacks (the record of this rollback itself stays)
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# The five fact tables that hold run-specific data.
# Order matters only for logging; FK constraints are handled by ON DELETE CASCADE
# in the schema, but we delete explicitly here to track row counts.
ROLLBACK_TABLES: tuple[str, ...] = (
    "premium_variance",
    "payroll_variance_policy",
    "payroll_variance_class",
    "zero_payroll",
    "missing_payroll",
)


class RollbackService:
    """
    Rolls back all fact-table data written by a specific ingestion run.

    Usage:
        service = RollbackService()
        await service.rollback(run_id=42, initiated_by="demo-admin", schema_name="demo", db=db)
    """

    async def rollback(
        self,
        run_id: int,
        initiated_by: str,
        schema_name: str,
        db: AsyncSession,
    ) -> int:
        """
        Executes the rollback transaction for run_id.

        Steps:
          1. INSERT ingestion_rollbacks (status='IN_PROGRESS')
          2. UPDATE ingestion_runs SET status='rolling_back'
          3. DELETE FROM each fact table WHERE ingestion_run_id = run_id
             (also handles synthetic per-period rows: run_id * -1000 … run_id * -1000 - 999)
          4. UPDATE ingestion_runs SET status='rolled_back'
          5. UPDATE ingestion_rollbacks SET status='COMPLETE', rows_removed=N
          On any exception: UPDATE rollback status='FAILED', error_detail=...

        Returns:
            Total rows removed from fact tables.

        Raises:
            ValueError: If run is not in ('complete', 'partial') status.
            RuntimeError: If rollback is already in progress or completed.
        """
        # Re-assert search_path for this session.
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Validate run status — only complete/partial runs can be rolled back.
        run_row = await db.execute(
            text("SELECT status FROM ingestion_runs WHERE run_id = :rid"),
            {"rid": run_id},
        )
        run = run_row.fetchone()
        if run is None:
            raise ValueError(f"Ingestion run {run_id} not found")
        if run[0] not in ("complete", "partial"):
            raise ValueError(
                f"Run {run_id} is in status '{run[0]}'; only 'complete' or 'partial' runs can be rolled back"
            )

        # Check for existing in-progress rollback.
        existing = await db.execute(
            text(
                "SELECT rollback_id, status FROM ingestion_rollbacks "
                "WHERE run_id = :rid ORDER BY rollback_id DESC LIMIT 1"
            ),
            {"rid": run_id},
        )
        existing_row = existing.fetchone()
        if existing_row and existing_row[1] in ("IN_PROGRESS", "COMPLETE"):
            raise RuntimeError(
                f"Run {run_id} has already been rolled back (status={existing_row[1]})"
            )

        # Step 1: Create rollback record.
        now = datetime.now(tz=timezone.utc)
        rb_result = await db.execute(
            text("""
                INSERT INTO ingestion_rollbacks (run_id, initiated_by, initiated_at, status)
                VALUES (:rid, :by, :at, 'IN_PROGRESS')
                RETURNING rollback_id
            """),
            {"rid": run_id, "by": initiated_by, "at": now},
        )
        rollback_id: int = rb_result.scalar_one()
        await db.commit()

        # Re-assert after commit.
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))

        logger.info("rollback.started", run_id=run_id, rollback_id=rollback_id)

        try:
            # Step 2: Mark run as rolling_back.
            await db.execute(
                text("UPDATE ingestion_runs SET status = 'rolling_back' WHERE run_id = :rid"),
                {"rid": run_id},
            )
            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))
            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))

            # Step 3: Delete from each fact table.
            total_rows_removed = 0
            for table in ROLLBACK_TABLES:
                # Delete main run rows.
                del_result = await db.execute(
                    text(f"DELETE FROM {table} WHERE ingestion_run_id = :rid"),
                    {"rid": run_id},
                )
                rows_in_table = del_result.rowcount or 0

                # Delete synthetic per-period rows (negative run_ids created by audit report parser).
                # Synthetic row IDs: -(run_id * 1000 + i) for i in 1..N
                # Range: -((run_id * 1000) + 999) .. -(run_id * 1000 + 1)
                synthetic_min = -(run_id * 1000 + 999)
                synthetic_max = -(run_id * 1000 + 1)
                if table == "payroll_variance_policy":
                    synth_result = await db.execute(
                        text(f"""
                            DELETE FROM {table}
                            WHERE ingestion_run_id BETWEEN :smin AND :smax
                        """),
                        {"smin": synthetic_min, "smax": synthetic_max},
                    )
                    rows_in_table += synth_result.rowcount or 0

                total_rows_removed += rows_in_table
                logger.debug(
                    "rollback.table.deleted",
                    table=table,
                    run_id=run_id,
                    rows=rows_in_table,
                )

            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))
            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))

            # Step 4: Mark run as rolled_back.
            await db.execute(
                text(
                    "UPDATE ingestion_runs SET status = 'rolled_back', completed_at = now() "
                    "WHERE run_id = :rid"
                ),
                {"rid": run_id},
            )
            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))
            await db.commit()
            await db.execute(text(f'SET search_path TO "{schema_name}", public'))

            # Step 5: Mark rollback as complete.
            await db.execute(
                text("""
                    UPDATE ingestion_rollbacks
                    SET status = 'COMPLETE', rows_removed = :rows, completed_at = now()
                    WHERE rollback_id = :rbid
                """),
                {"rows": total_rows_removed, "rbid": rollback_id},
            )
            await db.commit()

            logger.info(
                "rollback.complete",
                run_id=run_id,
                rollback_id=rollback_id,
                rows_removed=total_rows_removed,
            )
            return total_rows_removed

        except Exception as exc:
            # On any failure: mark rollback as FAILED.
            logger.error("rollback.failed", run_id=run_id, rollback_id=rollback_id, error=str(exc))
            try:
                await db.rollback()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.commit()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.execute(
                    text("""
                        UPDATE ingestion_rollbacks
                        SET status = 'FAILED', error_detail = :err
                        WHERE rollback_id = :rbid
                    """),
                    {"err": str(exc)[:2000], "rbid": rollback_id},
                )
                await db.commit()
            except Exception:
                pass
            raise

    async def can_rollback(self, run_id: int, db: AsyncSession) -> bool:
        """Returns True if run is in ('complete', 'partial') status and not already rolled back."""
        result = await db.execute(
            text("SELECT status FROM ingestion_runs WHERE run_id = :rid"),
            {"rid": run_id},
        )
        row = result.fetchone()
        if row is None:
            return False
        return row[0] in ("complete", "partial")
