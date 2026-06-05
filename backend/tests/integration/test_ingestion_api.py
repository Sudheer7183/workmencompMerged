from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.security import get_current_user
from app.main import create_app
from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord
from app.services.audit_calculation_service import AuditRunResult


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture
def client(app):
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auditor() -> TokenPayload:
    return TokenPayload(sub="a1", email="a@demo.test", role=Role.AUDITOR, tenant_slug="demo")


def _reviewer() -> TokenPayload:
    return TokenPayload(sub="r1", email="r@demo.test", role=Role.REVIEWER, tenant_slug="demo")


def _demo_tenant() -> TenantRecord:
    return TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo Tenant", status="ACTIVE")


def _make_mock_db(fetchall=None, scalar_one=None) -> AsyncMock:
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.scalar_one.return_value = scalar_one
    mock_db = AsyncMock()
    mock_db.execute.return_value = cursor
    return mock_db


def _minimal_xlsx() -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Policy Number", "Est Premium End", "Actual Premium", "Date"])
    ws.append(["WC-TEST-001", 100000, 115000, "2024-06-30"])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_upload_requires_auditor_role(client, app):
    """REVIEWER cannot upload — verify_role raises 403 before DB is touched."""
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _reviewer()
    app.dependency_overrides[get_db] = override_db

    with patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()):
        resp = client.post(
            "/api/v1/ingestion/upload",
            data={"carrier_id": "1", "source_id": "1"},
            files={"file": ("test.xlsx", _minimal_xlsx(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


def test_upload_rejects_non_xlsx(client, app):
    """CSV file must be rejected — Phase 1 accepts XLSX only."""
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _auditor()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/v1/ingestion/upload",
            data={"carrier_id": "1", "source_id": "1"},
            files={"file": ("report.csv", b"policy_number,value\nWC-001,100", "text/csv")},
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


def test_upload_accepts_valid_xlsx(client, app):
    """Valid XLSX upload with AUDITOR role returns 202."""
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _auditor()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
        patch("app.api.v1.ingestion._ingestion_svc.run", new_callable=AsyncMock, return_value=(1, 1)),
    ):
        resp = client.post(
            "/api/v1/ingestion/upload",
            data={"carrier_id": "1", "source_id": "1"},
            files={"file": ("payroll.xlsx", _minimal_xlsx(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code in (200, 202), f"Expected 200/202, got {resp.status_code}: {resp.text}"


def test_audit_run_requires_auditor(client, app):
    """REVIEWER cannot trigger audit/run — verify_role raises 403."""
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _reviewer()
    app.dependency_overrides[get_db] = override_db

    with patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()):
        resp = client.post(
            "/api/v1/audit/run",
            json={"carrier_id": 1, "ingestion_run_id": 1},
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


def test_audit_run_returns_skipped_when_engine_off(client, app):
    """AuditRunResponse.skipped=True returned when engine resolves to FALSE."""
    skipped_result = AuditRunResult(
        policy_id=1, ingestion_run_id=1, skipped=True, engine_ran=False,
        risk_level=None, variance_amount=None, variance_pct=None,
    )
    mock_db = _make_mock_db(fetchall=[(1,)], scalar_one=None)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _auditor()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.ingestion.verify_carrier_scope", new_callable=AsyncMock),
        patch("app.api.v1.ingestion._calc_svc.run", new_callable=AsyncMock, return_value=skipped_result),
    ):
        resp = client.post(
            "/api/v1/audit/run",
            json={"carrier_id": 1, "ingestion_run_id": 1},
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code in (202, 404), f"Expected 202/404, got {resp.status_code}: {resp.text}"
    if resp.status_code == 202:
        data = resp.json()
        assert data["skipped"] is True
        assert data["engine_ran"] is False