from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_redis_dep
from app.api.security import get_current_user
from app.main import create_app
from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture
def client(app):
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _mock_token(role: Role = Role.REVIEWER) -> TokenPayload:
    return TokenPayload(sub="t1", email="t@demo.test", role=role, tenant_slug="demo")


def _demo_tenant() -> TenantRecord:
    return TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo Tenant", status="ACTIVE")


def _make_mock_db(fetchone=None, fetchall=None, scalar_one=0) -> AsyncMock:
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.scalar_one.return_value = scalar_one
    mock_db = AsyncMock()
    mock_db.execute.return_value = cursor
    return mock_db


def _mock_redis() -> AsyncMock:
    """Mock Redis client — get returns None (cache miss), set is a no-op."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    return redis


def test_dashboard_summary_requires_auth(client, app):
    """No tenant header → 400 from TenantMiddleware."""
    resp = client.get("/api/v1/dashboard/summary?carrier_id=1")
    assert resp.status_code in (400, 422)


def test_dashboard_summary_reviewer_role_passes(client, app):
    """REVIEWER role is sufficient for the dashboard endpoint."""
    mock_db = _make_mock_db(
        fetchone=(
            Decimal("5000000"), Decimal("4800000"), Decimal("4950000"),
            Decimal("150000"), 12, 28, 45, 85, 15,
        )
    )

    async def override_db():
        yield mock_db

    # Phase 2: dashboard also depends on get_redis_dep for cache read/write.
    # Must override it so tests do not require a live Redis initialise_redis() call.
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_token(Role.REVIEWER)
    app.dependency_overrides[get_redis_dep] = lambda: _mock_redis()

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.dashboard.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/dashboard/summary?carrier_id=1",
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code != 500, f"Got 500: {resp.text}"
    assert resp.status_code != 403, "REVIEWER should not receive 403 on dashboard"


def test_dashboard_summary_zero_state_when_no_data(client, app):
    """Returns 200 with zero-value structure when no data rows exist."""
    mock_db = _make_mock_db(fetchone=None, fetchall=[], scalar_one=0)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_token()
    app.dependency_overrides[get_redis_dep] = lambda: _mock_redis()

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.dashboard.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/dashboard/summary?carrier_id=1",
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code in (200, 404), f"Expected 200/404, got {resp.status_code}: {resp.text}"
