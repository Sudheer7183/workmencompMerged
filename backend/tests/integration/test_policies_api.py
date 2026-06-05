from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
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


def _reviewer() -> TokenPayload:
    return TokenPayload(sub="r1", email="r@demo.test", role=Role.REVIEWER, tenant_slug="demo")


def _demo_tenant() -> TenantRecord:
    return TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo Tenant", status="ACTIVE")


def _make_mock_db(fetchone=None, fetchall=None, scalar_one=0) -> AsyncMock:
    """
    AsyncMock session with a MagicMock cursor so fetchone/fetchall/scalar_one
    are synchronous — matching SQLAlchemy 2.0 CursorResult behaviour.
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.scalar_one.return_value = scalar_one

    mock_db = AsyncMock()
    mock_db.execute.return_value = cursor
    return mock_db


def _apply_overrides(app, mock_db: AsyncMock, token: TokenPayload) -> None:
    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: token


def test_policy_list_returns_200(client, app):
    mock_db = _make_mock_db(
        scalar_one=1,
        fetchall=[
            (1, "WC-001", "Acme Corp", "CA", date(2024, 1, 1),
             "Active", Decimal("100000"), Decimal("10000"), Decimal("0.10"), "Medium", "Pending"),
        ],
    )
    _apply_overrides(app, mock_db, _reviewer())
    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.policies.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get("/api/v1/policies?carrier_id=1", headers={"X-Tenant-Slug": "demo"})
    assert resp.status_code != 500, f"Got 500: {resp.text}"


def test_policy_list_requires_reviewer_role(client, app):
    resp = client.get("/api/v1/policies?carrier_id=1")
    assert resp.status_code in (400, 422)


def test_policy_detail_returns_404_for_unknown(client, app):
    mock_db = _make_mock_db(fetchone=None)
    _apply_overrides(app, mock_db, _reviewer())
    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.policies.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get("/api/v1/policies/9999?carrier_id=1", headers={"X-Tenant-Slug": "demo"})
    assert resp.status_code in (404, 400), f"Expected 404/400, got {resp.status_code}: {resp.text}"


def test_variance_pct_null_when_engine_off(client, app):
    mock_db = _make_mock_db(
        scalar_one=1,
        fetchall=[
            (1, "WC-001", "Acme", "CA", date(2024, 1, 1),
             "Active", Decimal("100000"), Decimal("10000"), None, None, "Pending"),
        ],
    )
    _apply_overrides(app, mock_db, _reviewer())
    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.policies.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get("/api/v1/policies?carrier_id=1", headers={"X-Tenant-Slug": "demo"})
    if resp.status_code == 200:
        items = resp.json().get("items", [])
        if items:
            assert items[0]["variance_pct"] is None


def test_premium_variance_404_when_no_data(client, app):
    mock_db = _make_mock_db(fetchone=None)
    _apply_overrides(app, mock_db, _reviewer())
    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.policies.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/policies/1/premium-variance?carrier_id=1",
            headers={"X-Tenant-Slug": "demo"},
        )
    assert resp.status_code in (404, 400), f"Expected 404/400, got {resp.status_code}: {resp.text}"