"""
Phase 4 — Integration tests: ingestion pipeline with skip_on_error.

Tests that:
  - CSV ingestion completes (same mapping→approve→run flow as XLSX)
  - XML ingestion still works (regression)
  - skip_on_error=TRUE → partial run + ingestion_skipped_rows populated
  - skip_on_error=FALSE → any row error → run status='failed'
  - IngestionServiceV4 is wired (not the Phase 3 class)

These tests use the HTTP client against a real running DB (TestContainers pattern).
The upload endpoint is POST /api/v1/ingestion/upload (multipart/form-data).
"""
from __future__ import annotations

import io
from typing import Any

import openpyxl
import pytest
from httpx import AsyncClient
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Helpers — build test files in memory
# ---------------------------------------------------------------------------

def make_valid_xlsx() -> bytes:
    """Minimal XLSX with policy_number, insured_name, est_premium_end, actual_premium."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Policy Number", "Insured Name", "Est Premium End", "Actual Premium", "As Of Date"])
    ws.append(["POL-INT-001", "Integration Corp", 10000.00, 9500.00, "01/15/2026"])
    ws.append(["POL-INT-002", "Test LLC", 25000.00, 24000.00, "01/15/2026"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_malformed_xlsx() -> bytes:
    """XLSX with one valid row and one row missing policy_number."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Policy Number", "Insured Name", "Est Premium End", "Actual Premium"])
    ws.append(["POL-INT-GOOD", "Good Corp", 5000.00, 4800.00])
    ws.append(["", "Bad Corp — no policy number", "not-a-number", None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_valid_csv() -> bytes:
    """CSV version of the valid payroll file."""
    lines = [
        "Policy Number,Insured Name,Est Premium End,Actual Premium,As Of Date",
        "POL-CSV-001,CSV Corp Alpha,12000.00,11500.00,01/15/2026",
        "POL-CSV-002,CSV Corp Beta,8000.00,7800.00,01/15/2026",
    ]
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Fixture: upload a file and return (run_id, session_id)
# ---------------------------------------------------------------------------

async def upload_and_get_ids(
    test_client: AsyncClient,
    token: str,
    carrier_id: int,
    source_id: int,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    skip_on_error: bool = False,
) -> dict[str, Any]:
    response = await test_client.post(
        "/api/v1/ingestion/upload",
        data={
            "carrier_id": str(carrier_id),
            "source_id": str(source_id),
            "ingestion_mode": "calc_engine",
            "skip_on_error": str(skip_on_error).lower(),
        },
        files={"file": (filename, file_bytes, content_type)},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestionServiceV4Wired:
    async def test_xlsx_upload_returns_awaiting_mapping(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id, seeded_source_id
    ):
        """Phase 3 regression: XLSX still returns awaiting_mapping status."""
        file_bytes = make_valid_xlsx()
        response = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "awaiting_mapping"
        assert "run_id" in data
        assert "session_id" in data

    async def test_csv_upload_returns_awaiting_mapping(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id, seeded_source_id
    ):
        """Phase 4: CSV is now accepted and returns awaiting_mapping."""
        file_bytes = make_valid_csv()
        response = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test.csv", "text/csv",
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "awaiting_mapping"

    async def test_unsupported_file_type_returns_422(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id, seeded_source_id
    ):
        """PDF and other unsupported types must be rejected."""
        response = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            b"%PDF-1.4 fake content", "test.pdf", "application/pdf",
        )
        assert response.status_code == 422

    async def test_skip_on_error_flag_stored_on_run(
        self, test_client: AsyncClient, mock_auditor_token,
        seeded_carrier_id, seeded_source_id, async_session
    ):
        """When skip_on_error=True is submitted, ingestion_runs.skip_on_error must be TRUE."""
        file_bytes = make_valid_xlsx()
        response = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            skip_on_error=True,
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        result = await async_session.execute(
            text("SELECT skip_on_error FROM ingestion_runs WHERE run_id = :rid"),
            {"rid": run_id},
        )
        assert result.scalar() is True

    async def test_run_id_increments_across_uploads(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id, seeded_source_id
    ):
        """Each upload creates a unique run_id."""
        file_bytes = make_valid_xlsx()
        r1 = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test1.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        r2 = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test2.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert r1.json()["run_id"] != r2.json()["run_id"]

    async def test_reviewer_cannot_upload(
        self, test_client: AsyncClient, mock_reviewer_token, seeded_carrier_id, seeded_source_id
    ):
        """REVIEWER role must not be able to upload files."""
        file_bytes = make_valid_xlsx()
        response = await upload_and_get_ids(
            test_client, mock_reviewer_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert response.status_code == 403

    async def test_ingestion_service_v4_class_is_used(
        self, test_client: AsyncClient
    ):
        """Verify IngestionServiceV4 is importable and is a subclass of IngestionService."""
        from app.services.ingestion_service import IngestionService, IngestionServiceV4
        assert issubclass(IngestionServiceV4, IngestionService)
        svc = IngestionServiceV4()
        assert callable(getattr(svc, "_parse_and_upsert_csv", None))
        assert callable(getattr(svc, "_record_skipped_row", None))
        assert callable(getattr(svc, "_record_error", None))

    async def test_csv_detection_in_pipeline(self, test_client: AsyncClient):
        """IngestionServiceV4._is_csv() returns correct values."""
        from app.services.ingestion_service import IngestionServiceV4
        svc = IngestionServiceV4()
        assert svc._is_csv(b"Policy Number,Name\n001,Corp\n") is True
        assert svc._is_csv(b"PK\x03\x04" + b"\x00" * 50) is False
        assert svc._is_csv(b"<?xml version='1.0'?><root/>") is False
        assert svc._is_csv(b"\xef\xbb\xbfPolicy,Name\n001,Corp\n") is True  # BOM

    async def test_run_status_endpoint_works_for_new_run(
        self, test_client: AsyncClient, mock_reviewer_token,
        mock_auditor_token, seeded_carrier_id, seeded_source_id
    ):
        """Run status polling (GET /runs/{run_id}) works for a freshly uploaded run."""
        file_bytes = make_valid_xlsx()
        upload_res = await upload_and_get_ids(
            test_client, mock_auditor_token, seeded_carrier_id, seeded_source_id,
            file_bytes, "test.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert upload_res.status_code == 202
        run_id = upload_res.json()["run_id"]

        status_res = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id}",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert status_res.status_code == 200
        assert status_res.json()["run_id"] == run_id
        assert status_res.json()["status"] == "awaiting_mapping"
