from __future__ import annotations

"""
ReportJobService — Phase 5.

Manages the async report generation lifecycle per V9 S21.2.

Job status lifecycle:
  QUEUED → PROCESSING → COMPLETE | FAILED

Idempotency:
  If a job for the same (carrier_id, policy_id, report_type, output_format, run_id)
  already exists at status='COMPLETE' and was created within the last 24 hours,
  create_job() returns the existing job_id without re-generating.

S3 atomicity guarantee:
  file_url is written to report_jobs ONLY after S3 upload confirms.
  Steps 2–4 (generate → upload → presign) all happen BEFORE step 5 (write file_url).
  A failed upload leaves file_url=NULL and status='FAILED'.

Structural template:
  Follows the same transactional-with-status-writes pattern as RollbackService
  (search_path re-assertion, structured logging, exception safety).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.report_generation_service import ReportGenerationService
from app.services.s3_service import S3Service

logger = structlog.get_logger(__name__)

_report_generation_svc = ReportGenerationService()
_s3_svc = S3Service()

# 24-hour idempotency window — matches pre-signed URL TTL
IDEMPOTENCY_WINDOW_HOURS = 24


class ReportJobService:
    """
    Orchestrates async report generation: job creation, background execution,
    S3 upload, and status polling.

    Usage:
        svc = ReportJobService()
        job_id = await svc.create_job(...)
        # In FastAPI BackgroundTasks:
        background_tasks.add_task(svc.run_job, job_id, ...)
        # Polling:
        status = await svc.get_status(job_id, carrier_id, db)
    """

    async def create_job(
        self,
        carrier_id: int,
        policy_id: Optional[int],
        report_type: str,
        output_format: str,
        run_id: Optional[int],
        requested_by: str,
        schema_name: str,
        db: AsyncSession,
    ) -> uuid.UUID:
        """
        Creates a new report_jobs record with status='QUEUED' and returns its job_id.

        Idempotency check:
          If an identical request (same carrier_id, policy_id, report_type,
          output_format, run_id) completed successfully within the last 24h,
          returns the existing job_id without inserting a new row.

        Returns:
            UUID of the job (new or existing).
        """
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))

        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)

        # Build idempotency query — handle NULL comparisons explicitly
        policy_clause = (
            "AND policy_id = :policy_id " if policy_id is not None
            else "AND policy_id IS NULL "
        )
        run_clause = (
            "AND run_id = :run_id " if run_id is not None
            else "AND run_id IS NULL "
        )

        existing_result = await db.execute(
            text(
                "SELECT job_id FROM report_jobs "
                "WHERE carrier_id = :carrier_id "
                + policy_clause
                + run_clause
                + "AND report_type = :report_type "
                "AND output_format = :output_format "
                "AND status = 'COMPLETE' "
                "AND requested_at >= :cutoff "
                "ORDER BY requested_at DESC LIMIT 1"
            ),
            {
                "carrier_id": carrier_id,
                "policy_id": policy_id,
                "run_id": run_id,
                "report_type": report_type,
                "output_format": output_format,
                "cutoff": cutoff,
            },
        )
        existing_row = existing_result.fetchone()
        if existing_row is not None:
            existing_job_id: uuid.UUID = existing_row[0]
            logger.info(
                "report_job.idempotent_return",
                job_id=str(existing_job_id),
                carrier_id=carrier_id,
                report_type=report_type,
            )
            return existing_job_id

        # Insert new QUEUED job
        new_job_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        await db.execute(
            text(
                "INSERT INTO report_jobs "
                "(job_id, carrier_id, policy_id, report_type, output_format, "
                "run_id, status, requested_by, requested_at) "
                "VALUES (:job_id, :carrier_id, :policy_id, :report_type, "
                ":output_format, :run_id, 'QUEUED', :requested_by, :requested_at)"
            ),
            {
                "job_id": new_job_id,
                "carrier_id": carrier_id,
                "policy_id": policy_id,
                "report_type": report_type,
                "output_format": output_format,
                "run_id": run_id,
                "requested_by": requested_by,
                "requested_at": now,
            },
        )
        await db.commit()

        logger.info(
            "report_job.created",
            job_id=str(new_job_id),
            carrier_id=carrier_id,
            report_type=report_type,
            output_format=output_format,
        )
        return new_job_id

    async def run_job(
        self,
        job_id: uuid.UUID,
        carrier_id: int,
        policy_id: Optional[int],
        report_type: str,
        output_format: str,
        run_id: Optional[int],
        schema_name: str,
        db: AsyncSession,
    ) -> None:
        """
        Background task: generates the report, uploads to S3, updates status.

        Steps (S3 atomicity is enforced — file_url written ONLY after S3 confirms):
          1. UPDATE status = 'PROCESSING'
          2. Generate report bytes (ReportGenerationService)
          3. Upload bytes to S3
          4. Generate pre-signed URL (24h TTL)
          5. UPDATE status = 'COMPLETE', file_url = presigned_url

        On any exception in steps 2–5:
          UPDATE status = 'FAILED', error_detail = str(exc)
          file_url is NOT written.
        """
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Step 1 — Mark as PROCESSING
        await db.execute(
            text(
                "UPDATE report_jobs SET status = 'PROCESSING' WHERE job_id = :jid"
            ),
            {"jid": job_id},
        )
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))

        logger.info(
            "report_job.processing",
            job_id=str(job_id),
            report_type=report_type,
            output_format=output_format,
        )

        try:
            # Step 2 — Generate report bytes
            report_bytes, content_type, extension = await self._dispatch_generation(
                report_type=report_type,
                output_format=output_format,
                policy_id=policy_id,
                carrier_id=carrier_id,
                run_id=run_id,
                db=db,
            )

            # Step 3 — Upload to S3 (raises on failure — do NOT write DB before this)
            s3_key = (
                f"reports/{schema_name}/{carrier_id}/{report_type}/{job_id}.{extension}"
            )
            _s3_svc.upload_bytes(key=s3_key, data=report_bytes, content_type=content_type)

            # Step 4 — Generate pre-signed URL (24h TTL)
            presigned_url = _s3_svc.presign_url(key=s3_key, expiry_seconds=86400)

            # Step 5 — Write file_url and mark COMPLETE (only reached if S3 succeeded)
            completed_at = datetime.now(tz=timezone.utc)
            await db.execute(
                text(
                    "UPDATE report_jobs "
                    "SET status = 'COMPLETE', file_url = :url, completed_at = :at "
                    "WHERE job_id = :jid"
                ),
                {"url": presigned_url, "at": completed_at, "jid": job_id},
            )
            await db.commit()

            logger.info(
                "report_job.complete",
                job_id=str(job_id),
                s3_key=s3_key,
                size_bytes=len(report_bytes),
            )

        except Exception as exc:
            # S3 or generation failure — mark FAILED, do NOT set file_url
            logger.error(
                "report_job.failed",
                job_id=str(job_id),
                error=str(exc),
                exc_info=True,
            )
            try:
                await db.rollback()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.commit()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.execute(
                    text(
                        "UPDATE report_jobs "
                        "SET status = 'FAILED', error_detail = :err "
                        "WHERE job_id = :jid"
                    ),
                    {"err": str(exc)[:2000], "jid": job_id},
                )
                await db.commit()
            except Exception as inner_exc:
                logger.error(
                    "report_job.failed.status_update_error",
                    job_id=str(job_id),
                    inner_error=str(inner_exc),
                )

    async def get_status(
        self,
        job_id: uuid.UUID,
        carrier_id: int,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Returns the current status and metadata for a report job.
        Enforces carrier_id scope — raises ValueError if job belongs to another carrier.

        Returns dict with:
          job_id, status, file_url, report_type, output_format,
          requested_at, completed_at, error_detail
        """
        result = await db.execute(
            text(
                "SELECT job_id, carrier_id, status, file_url, report_type, "
                "output_format, requested_at, completed_at, error_detail "
                "FROM report_jobs WHERE job_id = :jid"
            ),
            {"jid": job_id},
        )
        row = result.fetchone()
        if row is None:
            raise ValueError(f"Report job {job_id} not found")

        # Carrier scope enforcement — prevent cross-carrier data access
        if row[1] != carrier_id:
            raise PermissionError(
                f"Report job {job_id} does not belong to carrier {carrier_id}"
            )

        return {
            "job_id": str(row[0]),
            "status": row[2],
            "file_url": row[3],
            "report_type": row[4],
            "output_format": row[5],
            "requested_at": row[6].isoformat() if row[6] else None,
            "completed_at": row[7].isoformat() if row[7] else None,
            "error_detail": row[8],
        }

    # ── Private dispatch ───────────────────────────────────────────────────────

    async def _dispatch_generation(
        self,
        report_type: str,
        output_format: str,
        policy_id: Optional[int],
        carrier_id: int,
        run_id: Optional[int],
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """Routes to the correct ReportGenerationService method by report_type."""
        if report_type == "policy_audit":
            assert policy_id is not None  # validated in API layer
            return await _report_generation_svc.generate_policy_audit(
                policy_id=policy_id,
                carrier_id=carrier_id,
                output_format=output_format,
                run_id=run_id,
                db=db,
            )
        elif report_type == "book_summary":
            return await _report_generation_svc.generate_book_summary(
                carrier_id=carrier_id,
                output_format=output_format,
                db=db,
            )
        elif report_type == "class_code_variance":
            return await _report_generation_svc.generate_class_code_variance(
                carrier_id=carrier_id,
                run_id=run_id,
                db=db,
            )
        elif report_type == "ingestion_audit_trail":
            return await _report_generation_svc.generate_ingestion_audit_trail(
                carrier_id=carrier_id,
                run_id=run_id,
                db=db,
            )
        elif report_type == "exception_report":
            assert run_id is not None  # validated in API layer
            return await _report_generation_svc.generate_exception_report(
                carrier_id=carrier_id,
                run_id=run_id,
                db=db,
            )
        else:
            raise ValueError(f"Unknown report_type: {report_type}")
