"""
Phase 4 — Integration tests: exception tracking API endpoints.
Tests GET /errors, GET /skipped, PUT /skipped/correct, POST /skipped/reingest,
POST /skipped/dismiss against a real PostgreSQL database via TestContainers.

These extend the conftest.py fixtures from backend/tests/conftest.py.
Run from backend/ directory:
  SKIP_JWT_VERIFICATION=true pytest tests-integrated/backend/integration/ -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def ingestion_run_with_skipped(async_session, seeded_carrier_id):
    """
    Creates an ingestion_run record with status='partial' and
    one ingestion_skipped_rows + one ingestion_errors row attached to it.
    Returns run_id and skip_id.
    """
    from sqlalchemy import text

    # Insert ingestion_source
    src = await async_session.execute(
        text("""
            INSERT INTO ingestion_sources
              (carrier_id, source_name, source_type, is_active, created_at)
            VALUES (:cid, 'Test Source', 'xlsx', TRUE, now())
            RETURNING source_id
        """),
        {"cid": seeded_carrier_id},
    )
    source_id = src.scalar_one()

    # Insert ingestion_run with status=partial
    run = await async_session.execute(
        text("""
            INSERT INTO ingestion_runs
              (carrier_id, source_id, uploaded_by, started_at, status,
               rows_ingested, rows_skipped, rows_failed, skip_on_error,
               use_calculation_engine)
            VALUES (:cid, :sid, 'test-admin', now(), 'partial',
                    10, 2, 0, TRUE, NULL)
            RETURNING run_id
        """),
        {"cid": seeded_carrier_id, "sid": source_id},
    )
    run_id = run.scalar_one()

    # Insert skipped row
    skip = await async_session.execute(
        text("""
            INSERT INTO ingestion_skipped_rows
              (run_id, row_number, raw_data, skip_reason, error_codes, resolution_status)
            VALUES (:rid, 5, :rdata::jsonb, 'No policy_number', :codes, 'PENDING')
            RETURNING skip_id
        """),
        {
            "rid": run_id,
            "rdata": json.dumps({"Policy Number": "", "Insured Name": "Acme Corp"}),
            "codes": ["MISSING_POLICY_NUMBER"],
        },
    )
    skip_id = skip.scalar_one()

    # Insert ingestion_error
    await async_session.execute(
        text("""
            INSERT INTO ingestion_errors
              (run_id, row_number, field_name, error_type, error_message, created_at)
            VALUES (:rid, 5, 'policy_number', 'MISSING_POLICY_NUMBER',
                    'Row 5 has no policy_number', now())
        """),
        {"rid": run_id},
    )
    await async_session.commit()

    return run_id, skip_id


# ---------------------------------------------------------------------------
# Tests: GET /runs/{run_id}/errors
# ---------------------------------------------------------------------------

class TestListRunErrors:
    async def test_reviewer_can_list_errors(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, _ = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/errors",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["error_type"] == "MISSING_POLICY_NUMBER"

    async def test_errors_filtered_by_error_code(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, _ = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/errors?error_code=MISSING_POLICY_NUMBER",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["error_type"] == "MISSING_POLICY_NUMBER" for e in data)

    async def test_unknown_run_returns_404(
        self, test_client: AsyncClient, mock_reviewer_token
    ):
        response = await test_client.get(
            "/api/v1/ingestion/runs/999999/errors",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 404

    async def test_errors_response_has_required_fields(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, _ = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/errors",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 200
        err = response.json()[0]
        assert "error_id" in err
        assert "run_id" in err
        assert "error_type" in err
        assert "error_message" in err
        assert "created_at" in err


# ---------------------------------------------------------------------------
# Tests: GET /runs/{run_id}/skipped
# ---------------------------------------------------------------------------

class TestListSkippedRows:
    async def test_reviewer_can_list_skipped(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, skip_id = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/skipped",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["skip_id"] == skip_id
        assert data[0]["resolution_status"] == "PENDING"

    async def test_skipped_filtered_by_resolution(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, _ = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/skipped?resolution_status=PENDING",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert all(r["resolution_status"] == "PENDING" for r in data)

    async def test_skipped_row_has_raw_data_jsonb(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        run_id, _ = ingestion_run_with_skipped
        response = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}/skipped",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        row = response.json()[0]
        assert isinstance(row["raw_data"], dict)
        assert "Insured Name" in row["raw_data"]


# ---------------------------------------------------------------------------
# Tests: PUT /skipped/{skip_id}/correct
# ---------------------------------------------------------------------------

class TestCorrectSkippedRow:
    async def test_auditor_can_correct_skipped_row(
        self, test_client: AsyncClient, mock_auditor_token, ingestion_run_with_skipped
    ):
        _, skip_id = ingestion_run_with_skipped
        response = await test_client.put(
            f"/api/v1/ingestion/skipped/{skip_id}/correct",
            json={"corrected_data": {"Policy Number": "POL-12345", "Insured Name": "Acme Corp"}},
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["corrected_data"]["Policy Number"] == "POL-12345"
        assert data["resolution_status"] == "PENDING"  # stays PENDING until reingest

    async def test_reviewer_cannot_correct_skipped_row(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        _, skip_id = ingestion_run_with_skipped
        response = await test_client.put(
            f"/api/v1/ingestion/skipped/{skip_id}/correct",
            json={"corrected_data": {"Policy Number": "POL-99999"}},
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /skipped/{skip_id}/reingest
# ---------------------------------------------------------------------------

class TestReingestSkippedRow:
    async def test_auditor_can_reingest(
        self, test_client: AsyncClient, mock_auditor_token, ingestion_run_with_skipped
    ):
        _, skip_id = ingestion_run_with_skipped
        # First correct the row
        await test_client.put(
            f"/api/v1/ingestion/skipped/{skip_id}/correct",
            json={"corrected_data": {"Policy Number": "POL-12345"}},
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        # Then reingest
        response = await test_client.post(
            f"/api/v1/ingestion/skipped/{skip_id}/reingest",
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Tests: POST /skipped/{skip_id}/dismiss
# ---------------------------------------------------------------------------

class TestDismissSkippedRow:
    async def test_auditor_can_dismiss(
        self, test_client: AsyncClient, mock_auditor_token, ingestion_run_with_skipped
    ):
        _, skip_id = ingestion_run_with_skipped
        response = await test_client.post(
            f"/api/v1/ingestion/skipped/{skip_id}/dismiss",
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["resolution_status"] == "DISMISSED"
        assert data["resolved_by"] is not None

    async def test_reviewer_cannot_dismiss(
        self, test_client: AsyncClient, mock_reviewer_token, ingestion_run_with_skipped
    ):
        _, skip_id = ingestion_run_with_skipped
        response = await test_client.post(
            f"/api/v1/ingestion/skipped/{skip_id}/dismiss",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert response.status_code == 403
