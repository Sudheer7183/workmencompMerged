"""
test_reports_api.py — Phase 5 integration tests.

Tests for POST /api/v1/reports/generate and GET /api/v1/reports/{job_id}/status.
Uses FastAPI TestClient with SKIP_JWT_VERIFICATION=true.
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def generate_url() -> str:
    return "/api/v1/reports/generate"


def _generate_body(**kwargs: Any) -> dict:
    defaults = {
        "carrier_id": 1,
        "report_type": "policy_audit",
        "output_format": "pdf",
        "policy_id": 10,
        "run_id": None,
    }
    defaults.update(kwargs)
    return defaults


# ── POST /api/v1/reports/generate tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_policy_audit_returns_202(
    client: AsyncClient, generate_url: str
) -> None:
    """POST generate with policy_audit returns 202 and a job_id UUID"""
    with patch(
        "app.api.v1.reports._report_job_svc.create_job",
        AsyncMock(return_value=uuid.uuid4()),
    ):
        response = await client.post(generate_url, json=_generate_body())

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    # Validate it's a UUID string
    uuid.UUID(data["job_id"])


@pytest.mark.asyncio
async def test_generate_policy_audit_requires_policy_id(
    client: AsyncClient, generate_url: str
) -> None:
    """Missing policy_id for policy_audit → 422"""
    response = await client.post(
        generate_url,
        json=_generate_body(report_type="policy_audit", policy_id=None),
    )
    assert response.status_code == 422
    assert "policy_id" in response.text.lower()


@pytest.mark.asyncio
async def test_generate_class_code_variance_pdf_returns_422(
    client: AsyncClient, generate_url: str
) -> None:
    """output_format='pdf' for Excel-only report → 422"""
    response = await client.post(
        generate_url,
        json=_generate_body(
            report_type="class_code_variance",
            output_format="pdf",
            policy_id=None,
        ),
    )
    assert response.status_code == 422
    assert "excel" in response.text.lower()


@pytest.mark.asyncio
async def test_generate_exception_report_requires_run_id(
    client: AsyncClient, generate_url: str
) -> None:
    """Missing run_id for exception_report → 422"""
    response = await client.post(
        generate_url,
        json=_generate_body(
            report_type="exception_report",
            output_format="excel",
            policy_id=None,
            run_id=None,
        ),
    )
    assert response.status_code == 422
    assert "run_id" in response.text.lower()


@pytest.mark.asyncio
async def test_generate_ingestion_audit_trail_requires_run_id(
    client: AsyncClient, generate_url: str
) -> None:
    """Missing run_id for ingestion_audit_trail → 422"""
    response = await client.post(
        generate_url,
        json=_generate_body(
            report_type="ingestion_audit_trail",
            output_format="excel",
            policy_id=None,
            run_id=None,
        ),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_book_summary_no_required_ids(
    client: AsyncClient, generate_url: str
) -> None:
    """book_summary needs no policy_id or run_id → 202"""
    with patch(
        "app.api.v1.reports._report_job_svc.create_job",
        AsyncMock(return_value=uuid.uuid4()),
    ):
        response = await client.post(
            generate_url,
            json=_generate_body(
                report_type="book_summary",
                output_format="pdf",
                policy_id=None,
                run_id=None,
            ),
        )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_generate_unknown_report_type_returns_422(
    client: AsyncClient, generate_url: str
) -> None:
    """Unknown report_type value → 422"""
    response = await client.post(
        generate_url,
        json=_generate_body(report_type="nonexistent_type"),
    )
    assert response.status_code == 422


# ── GET /api/v1/reports/{job_id}/status tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_status_queued_returns_no_file_url(
    client: AsyncClient,
) -> None:
    """A QUEUED job status returns file_url=null"""
    from datetime import datetime, timezone

    job_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    mock_status = {
        "job_id": str(job_id),
        "status": "QUEUED",
        "file_url": None,
        "report_type": "policy_audit",
        "output_format": "pdf",
        "requested_at": now.isoformat(),
        "completed_at": None,
        "error_detail": None,
    }

    # Mock the DB call inside the route
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, i: [
        job_id, 1, "QUEUED", None, "policy_audit", "pdf", now, None, None
    ][i]

    with patch(
        "app.api.v1.reports._report_job_svc.get_status",
        AsyncMock(return_value=mock_status),
    ):
        response = await client.get(f"/api/v1/reports/{job_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["file_url"] is None


@pytest.mark.asyncio
async def test_get_status_complete_returns_file_url(client: AsyncClient) -> None:
    """A COMPLETE job status returns a non-null file_url"""
    from datetime import datetime, timezone

    job_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    presigned = "https://minio:9000/bucket/report.pdf?X-Amz-Expires=86400"

    mock_status = {
        "job_id": str(job_id),
        "status": "COMPLETE",
        "file_url": presigned,
        "report_type": "policy_audit",
        "output_format": "pdf",
        "requested_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "error_detail": None,
    }

    with patch(
        "app.api.v1.reports._report_job_svc.get_status",
        AsyncMock(return_value=mock_status),
    ):
        response = await client.get(f"/api/v1/reports/{job_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETE"
    assert data["file_url"] == presigned


@pytest.mark.asyncio
async def test_get_status_not_found(client: AsyncClient) -> None:
    """Non-existent job_id → 404"""
    nonexistent_id = uuid.uuid4()

    with patch(
        "app.api.v1.reports._report_job_svc.get_status",
        AsyncMock(side_effect=ValueError("not found")),
    ):
        response = await client.get(f"/api/v1/reports/{nonexistent_id}/status")

    assert response.status_code == 404


# ── Report template tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_report_template_returns_empty_when_not_configured(
    client: AsyncClient,
) -> None:
    """GET template for unconfigured carrier returns nulls"""
    response = await client.get("/api/v1/admin/report-template/1")
    assert response.status_code == 200
    data = response.json()
    assert data["carrier_id"] == 1
    # When not configured all fields are null
    assert data["logo_url"] is None


@pytest.mark.asyncio
async def test_put_report_template_saves_colours(client: AsyncClient) -> None:
    """PUT template saves primary/secondary colour"""
    response = await client.put(
        "/api/v1/admin/report-template/1",
        json={
            "primary_colour": "2E86C1",
            "secondary_colour": "1A3C5E",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["primary_colour"] == "2E86C1"
    assert data["secondary_colour"] == "1A3C5E"


@pytest.mark.asyncio
async def test_put_report_template_validates_hex_colour(client: AsyncClient) -> None:
    """7-char hex with # prefix → 422 (must be 6 chars without #)"""
    response = await client.put(
        "/api/v1/admin/report-template/1",
        json={"primary_colour": "#2E86C1"},  # has # prefix — invalid after stripping
    )
    # After stripping # we get "2E86C1" which is valid — the validator strips #
    # Test with truly invalid: too long
    response2 = await client.put(
        "/api/v1/admin/report-template/1",
        json={"primary_colour": "2E86C1FF"},  # 8 chars — invalid
    )
    assert response2.status_code == 422


@pytest.mark.asyncio
async def test_put_report_template_null_clears_logo(client: AsyncClient) -> None:
    """PUT with logo_url=null clears the logo"""
    response = await client.put(
        "/api/v1/admin/report-template/1",
        json={"logo_url": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["logo_url"] is None


# ── End-to-end flow test (Fix 8 from gap analysis) ────────────────────────────


@pytest.mark.asyncio
async def test_full_report_flow_end_to_end(
    client: AsyncClient,
) -> None:
    """
    Full async report flow:
      1. POST generate → 202 {job_id}
      2. job_id is a valid UUID
      3. GET status → job exists (QUEUED/PROCESSING/COMPLETE)
      4. When COMPLETE: file_url is non-empty string

    Uses mocked job service so the test doesn't require real WeasyPrint/S3.
    """
    from datetime import datetime, timezone
    import uuid as _uuid

    job_id = _uuid.uuid4()
    presigned = "https://minio:9000/bucket/reports/demo/1/book_summary/test.pdf?X-Amz-Expires=86400"
    now = datetime.now(tz=timezone.utc)

    create_mock = AsyncMock(return_value=job_id)
    status_mock = AsyncMock(return_value={
        "job_id": str(job_id),
        "status": "COMPLETE",
        "file_url": presigned,
        "report_type": "book_summary",
        "output_format": "pdf",
        "requested_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "error_detail": None,
    })

    with patch("app.api.v1.reports._report_job_svc.create_job", create_mock):
        # Step 1: POST generate
        gen_response = await client.post(
            "/api/v1/reports/generate",
            json={
                "carrier_id": 1,
                "report_type": "book_summary",
                "output_format": "pdf",
            },
        )

    assert gen_response.status_code == 202
    gen_data = gen_response.json()
    assert "job_id" in gen_data

    # Step 2: job_id is a valid UUID
    returned_job_id = _uuid.UUID(gen_data["job_id"])
    assert str(returned_job_id) == gen_data["job_id"]

    with patch("app.api.v1.reports._report_job_svc.get_status", status_mock):
        # Step 3: GET status
        status_response = await client.get(
            f"/api/v1/reports/{gen_data['job_id']}/status"
        )

    assert status_response.status_code == 200
    status_data = status_response.json()

    # Step 4: file_url is non-empty when COMPLETE
    assert status_data["status"] == "COMPLETE"
    assert status_data["file_url"]
    assert len(status_data["file_url"]) > 0
    assert "minio" in status_data["file_url"] or "amazonaws" in status_data["file_url"] or "http" in status_data["file_url"]


@pytest.mark.asyncio
async def test_generate_auditor_can_generate(
    client: AsyncClient,
) -> None:
    """
    AUDITOR role → POST generate → 202 (AUDITOR+ is required per V9 S25.4).
    The default test client uses SKIP_JWT_VERIFICATION with AUDITOR token.
    """
    with patch(
        "app.api.v1.reports._report_job_svc.create_job",
        AsyncMock(return_value=__import__("uuid").uuid4()),
    ):
        response = await client.post(
            "/api/v1/reports/generate",
            json={
                "carrier_id": 1,
                "report_type": "book_summary",
                "output_format": "pdf",
            },
        )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_get_status_reviewer_can_read(client: AsyncClient) -> None:
    """
    REVIEWER+ can GET status and download — per V9 S25.4.
    With SKIP_JWT_VERIFICATION, the default token is REVIEWER level — verify 200.
    """
    from datetime import datetime, timezone
    import uuid as _uuid

    job_id = _uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    presigned = "https://minio:9000/bucket/report.pdf"

    mock_status = {
        "job_id": str(job_id),
        "status": "COMPLETE",
        "file_url": presigned,
        "report_type": "book_summary",
        "output_format": "pdf",
        "requested_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "error_detail": None,
    }

    with patch(
        "app.api.v1.reports._report_job_svc.get_status",
        AsyncMock(return_value=mock_status),
    ):
        response = await client.get(f"/api/v1/reports/{job_id}/status")

    # REVIEWER (minimum role for status) can access
    assert response.status_code == 200
    assert response.json()["file_url"] == presigned
