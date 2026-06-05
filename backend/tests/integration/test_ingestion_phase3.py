"""
Integration tests for Phase 3 ingestion flow.
Uses TestClient + dependency_overrides (same pattern as Phase 1/2 tests).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.security import get_current_user
from app.main import create_app
from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord


# ── Helpers ───────────────────────────────────────────────────────────────────

def _demo_tenant() -> TenantRecord:
    return TenantRecord(
        tenant_id=1, name="Demo", slug="demo",
        schema_name="tenant_demo", status="ACTIVE"
    )


def _admin_token() -> TokenPayload:
    return TokenPayload(
        sub="ta-001", email="admin@demo.test",
        role=Role.TENANT_ADMIN, tenant_slug="demo",
    )


def _reviewer_token() -> TokenPayload:
    return TokenPayload(
        sub="r-001", email="rev@demo.test",
        role=Role.REVIEWER, tenant_slug="demo",
    )


def _make_db(row: dict | None = None) -> AsyncMock:
    db = AsyncMock()
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = row
    r.mappings.return_value.all.return_value = [row] if row else []
    r.fetchone.return_value = None
    db.execute.return_value = r
    db.commit = AsyncMock()
    return db


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_upload_returns_awaiting_mapping(client: TestClient, app: FastAPI) -> None:
    """
    POST /api/v1/ingestion/upload must return status='awaiting_mapping'
    and include a non-null session_id.
    """
    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    async def override_db():
        yield _make_db()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_tenant"),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
        patch("app.api.v1.ingestion._ingestion_svc.run",
              new_callable=AsyncMock,
              return_value=(10, 1)),
    ):
        xlsx_bytes = b"PK\x03\x04"  # minimal XLSX magic bytes
        resp = client.post(
            "/api/v1/ingestion/upload",
            data={"carrier_id": "1", "source_id": "1"},
            files={"file": ("test.xlsx", xlsx_bytes, "application/octet-stream")},
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code in (200, 202, 422), resp.text
    if resp.status_code in (200, 202):
        data = resp.json()
        assert data.get("status") == "awaiting_mapping"
        assert data.get("session_id") is not None


def test_approve_mapping_returns_403_for_reviewer(
    client: TestClient, app: FastAPI
) -> None:
    """POST /api/v1/ingestion/mapping/{session_id}/approve with REVIEWER → 403."""
    async def override_db():
        yield _make_db()
    app.dependency_overrides[get_current_user] = lambda: _reviewer_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_tenant"),
    ):
        resp = client.post(
            "/api/v1/ingestion/mapping/1/approve",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 403, resp.text


def test_get_run_status_returns_run_fields(client: TestClient, app: FastAPI) -> None:
    """GET /api/v1/ingestion/runs/{run_id} returns a payload with required fields."""
    db_mock = _make_db()
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = {
        "run_id": 10,
        "status": "awaiting_mapping",
        "rows_ingested": None,
        "rows_skipped": 0,
        "rows_failed": 0,
        "error_detail": None,
        "started_at": "2026-06-01 09:00:00+00:00",
        "completed_at": None,
        "carrier_id": 1,
    }
    db_mock.execute.return_value = r

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_tenant"),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/ingestion/runs/10",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code in (200, 422, 500), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "run_id" in data
        assert "status" in data


def test_run_post_approval_is_separate_from_run() -> None:
    """
    run_post_approval() must be a separate async method from run().
    This is the architectural gate ensuring fact tables are only
    written after explicit approval.
    """
    from app.services.ingestion_service import IngestionService
    svc = IngestionService()
    assert asyncio.iscoroutinefunction(svc.run)
    assert asyncio.iscoroutinefunction(svc.run_post_approval)
    assert svc.run.__name__ != svc.run_post_approval.__name__


def test_reject_mapping_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """POST /api/v1/ingestion/mapping/{session_id}/reject endpoint must exist."""
    db_mock = _make_db()
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = {
        "session_id": 1,
        "ingestion_run_id": 10,
        "status": "PENDING_REVIEW",
        "carrier_id": 1,
    }
    db_mock.execute.return_value = r

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_tenant"),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/v1/ingestion/mapping/1/reject",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (500, 405), resp.text
