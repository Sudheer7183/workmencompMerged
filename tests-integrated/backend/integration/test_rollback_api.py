"""
Phase 4 — Integration tests: rollback API endpoint.
Tests POST /api/v1/ingestion/runs/{run_id}/rollback.

V9 S17.5: Only TENANT_ADMIN can roll back. Only complete/partial runs.
After rollback: run.status = 'rolled_back', fact rows deleted, errors preserved.
"""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.fixture
async def completed_run_with_fact_rows(async_session, seeded_carrier_id, seeded_policy_id):
    """
    Creates an ingestion_run with status='complete' and one premium_variance row.
    Returns run_id.
    """
    # ingestion_source
    src = await async_session.execute(
        text("""
            INSERT INTO ingestion_sources (carrier_id, source_name, source_type, is_active, created_at)
            VALUES (:cid, 'Rollback Test Source', 'xlsx', TRUE, now())
            RETURNING source_id
        """),
        {"cid": seeded_carrier_id},
    )
    source_id = src.scalar_one()

    # ingestion_run complete
    run = await async_session.execute(
        text("""
            INSERT INTO ingestion_runs
              (carrier_id, source_id, uploaded_by, started_at, completed_at, status,
               rows_ingested, rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
            VALUES (:cid, :sid, 'test-admin', now(), now(), 'complete',
                    5, 0, 0, FALSE, NULL)
            RETURNING run_id
        """),
        {"cid": seeded_carrier_id, "sid": source_id},
    )
    run_id = run.scalar_one()

    # premium_variance fact row
    await async_session.execute(
        text("""
            INSERT INTO premium_variance
              (policy_id, carrier_id, ingestion_run_id, as_of_date, est_premium_end, actual_premium)
            VALUES (:pid, :cid, :rid, now(), 10000.00, 9500.00)
        """),
        {"pid": seeded_policy_id, "cid": seeded_carrier_id, "rid": run_id},
    )

    # Add one skipped row to verify it's preserved after rollback
    await async_session.execute(
        text("""
            INSERT INTO ingestion_skipped_rows
              (run_id, row_number, raw_data, skip_reason, error_codes, resolution_status)
            VALUES (:rid, 3, :rd::jsonb, 'Test skip', :codes, 'PENDING')
        """),
        {
            "rid": run_id,
            "rd": json.dumps({"Policy Number": "X"}),
            "codes": ["MISSING_POLICY_NUMBER"],
        },
    )
    await async_session.commit()
    return run_id


class TestRollbackAPI:
    async def test_tenant_admin_can_rollback_complete_run(
        self, test_client: AsyncClient, mock_tenant_admin_token, completed_run_with_fact_rows
    ):
        run_id = completed_run_with_fact_rows
        response = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETE"
        assert data["run_id"] == run_id

    async def test_auditor_cannot_rollback(
        self, test_client: AsyncClient, mock_auditor_token, completed_run_with_fact_rows
    ):
        run_id = completed_run_with_fact_rows
        response = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 403

    async def test_reviewer_cannot_rollback(
        self, test_client: AsyncClient, mock_reviewer_token, completed_run_with_fact_rows
    ):
        run_id = completed_run_with_fact_rows
        response = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 403

    async def test_fact_rows_deleted_after_rollback(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        completed_run_with_fact_rows, async_session
    ):
        run_id = completed_run_with_fact_rows
        await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        # premium_variance should be empty for this run
        result = await async_session.execute(
            text("SELECT COUNT(*) FROM premium_variance WHERE ingestion_run_id = :rid"),
            {"rid": run_id},
        )
        assert result.scalar() == 0

    async def test_ingestion_run_status_rolled_back(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        completed_run_with_fact_rows, async_session
    ):
        run_id = completed_run_with_fact_rows
        await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        result = await async_session.execute(
            text("SELECT status FROM ingestion_runs WHERE run_id = :rid"),
            {"rid": run_id},
        )
        assert result.scalar() == "rolled_back"

    async def test_skipped_rows_preserved_after_rollback(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        completed_run_with_fact_rows, async_session
    ):
        """V9 S17.5: ingestion_skipped_rows must NOT be deleted."""
        run_id = completed_run_with_fact_rows
        await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        result = await async_session.execute(
            text("SELECT COUNT(*) FROM ingestion_skipped_rows WHERE run_id = :rid"),
            {"rid": run_id},
        )
        assert result.scalar() >= 1

    async def test_double_rollback_returns_409(
        self, test_client: AsyncClient, mock_tenant_admin_token, completed_run_with_fact_rows
    ):
        run_id = completed_run_with_fact_rows
        # First rollback
        r1 = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert r1.status_code == 200
        # Second rollback — must return 409
        r2 = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert r2.status_code == 409

    async def test_cannot_rollback_processing_run(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        async_session, seeded_carrier_id
    ):
        """Only complete or partial runs can be rolled back."""
        src = await async_session.execute(
            text("""
                INSERT INTO ingestion_sources (carrier_id, source_name, source_type, is_active, created_at)
                VALUES (:cid, 'Processing Source', 'xlsx', TRUE, now())
                RETURNING source_id
            """),
            {"cid": seeded_carrier_id},
        )
        sid = src.scalar_one()
        run = await async_session.execute(
            text("""
                INSERT INTO ingestion_runs
                  (carrier_id, source_id, uploaded_by, started_at, status,
                   rows_ingested, rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
                VALUES (:cid, :sid, 'test', now(), 'processing', 0, 0, 0, FALSE, NULL)
                RETURNING run_id
            """),
            {"cid": seeded_carrier_id, "sid": sid},
        )
        run_id = run.scalar_one()
        await async_session.commit()

        response = await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 409

    async def test_rollback_ingestion_rollbacks_record_created(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        completed_run_with_fact_rows, async_session
    ):
        """ingestion_rollbacks table must have a COMPLETE record."""
        run_id = completed_run_with_fact_rows
        await test_client.post(
            f"/api/v1/ingestion/runs/{run_id}/rollback",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        result = await async_session.execute(
            text("SELECT status FROM ingestion_rollbacks WHERE run_id = :rid ORDER BY rollback_id DESC LIMIT 1"),
            {"rid": run_id},
        )
        assert result.scalar() == "COMPLETE"
