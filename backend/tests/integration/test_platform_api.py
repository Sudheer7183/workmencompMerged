"""
Integration tests for /platform/* SUPER_ADMIN endpoints — Phase 2.

All tests use dependency overrides — no live DB or Keycloak required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_public_db
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


def _super_admin_token() -> TokenPayload:
    return TokenPayload(
        sub="sa-001",
        email="superadmin@platform.test",
        role=Role.SUPER_ADMIN,
        tenant_slug=None,
    )


def _tenant_admin_token() -> TokenPayload:
    return TokenPayload(
        sub="ta-001",
        email="admin@demo.test",
        role=Role.TENANT_ADMIN,
        tenant_slug="demo",
    )


def _make_mock_db(fetchone=None, fetchall=None, scalar_one=0) -> AsyncMock:
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.scalar_one.return_value = scalar_one
    mock_db = AsyncMock()
    mock_db.execute.return_value = cursor
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    return mock_db


def _apply_super_admin(app, mock_db: AsyncMock) -> None:
    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _super_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_platform_tenants_not_subject_to_tenant_middleware(client, app):
    """
    /platform/tenants must not require X-Tenant-Slug header.
    TenantMiddleware exempts /platform/* paths.
    """
    mock_db = _make_mock_db(fetchall=[])
    _apply_super_admin(app, mock_db)

    # Deliberately send NO X-Tenant-Slug header
    resp = client.get("/platform/tenants")
    # Should not return 400 (missing tenant) — should succeed
    assert resp.status_code != 400, f"Got 400 — /platform/* should be middleware-exempt"
    assert resp.status_code in (200,), f"Expected 200, got {resp.status_code}: {resp.text}"


def test_post_platform_tenants_requires_super_admin(client, app):
    """TENANT_ADMIN token → POST /platform/tenants → 403."""
    mock_db = _make_mock_db()

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _tenant_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db

    resp = client.post(
        "/platform/tenants",
        json={
            "name": "Gamma Corp",
            "slug": "gamma",
            "tenant_type": "AUDIT_COMPANY",
            "admin_email": "admin@gamma.test",
            "admin_first_name": "Gamma",
            "admin_last_name": "Admin",
        },
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_post_platform_tenants_creates_schema(client, app, mock_keycloak_service, mock_subprocess_alembic):
    """
    POST /platform/tenants with SUPER_ADMIN token and mocked provisioning
    must trigger TenantProvisioningService.provision_tenant.
    """
    mock_db = _make_mock_db(fetchone=None)

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _super_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db

    with patch(
        "app.api.v1.platform.TenantProvisioningService.provision_tenant",
        new=AsyncMock(return_value="newcorp"),
    ) as mock_provision:
        # Mock get_tenant to return the created tenant
        with patch(
            "app.api.v1.platform.get_tenant",
            new=AsyncMock(
                return_value={
                    "slug": "newcorp",
                    "name": "New Corp",
                    "tenant_type": "AUDIT_COMPANY",
                    "status": "ACTIVE",
                    "schema_name": "tenant_newcorp",
                    "config": None,
                }
            ),
        ):
            resp = client.post(
                "/platform/tenants",
                json={
                    "name": "New Corp",
                    "slug": "newcorp",
                    "tenant_type": "AUDIT_COMPANY",
                    "admin_email": "admin@newcorp.test",
                    "admin_first_name": "New",
                    "admin_last_name": "Admin",
                    "carrier_ids": [],
                },
            )

    assert resp.status_code in (201,), f"Expected 201, got {resp.status_code}: {resp.text}"
    mock_provision.assert_awaited_once()


def test_post_platform_carriers_creates_public_carrier(client, app):
    """POST /platform/carriers must INSERT into public.carriers and return the new record."""
    carrier_row = (42, "New Carrier Inc", "new-carrier", False)
    mock_db = _make_mock_db(fetchone=carrier_row)

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _super_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db

    resp = client.post(
        "/platform/carriers",
        json={"carrier_name": "New Carrier Inc", "slug": "new-carrier", "ai_narrative_enabled": False},
    )

    assert resp.status_code in (201,), f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["carrier_id"] == 42
    assert data["carrier_name"] == "New Carrier Inc"


def test_post_platform_tenant_carriers_writes_to_tenant_schema(client, app):
    """
    POST /platform/tenant-carriers must switch search_path to the tenant schema
    before inserting into tenant_carriers.
    """
    # Mock: first execute to get schema_name, then the tenant_carriers insert
    tenant_row = ("tenant_demo",)
    mock_db = _make_mock_db(fetchone=tenant_row)

    schema_switched = []

    async def _capture_execute(stmt, params=None, **kwargs):
        stmt_str = str(stmt)
        if "search_path" in stmt_str.lower():
            schema_switched.append(stmt_str)
        cursor = MagicMock()
        cursor.fetchone.return_value = tenant_row
        return cursor

    mock_db.execute = _capture_execute

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _super_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db

    resp = client.post(
        "/platform/tenant-carriers",
        json={"tenant_slug": "demo", "carrier_id": 1},
    )

    assert resp.status_code in (201,), f"Expected 201, got {resp.status_code}: {resp.text}"
    assert any("tenant_demo" in s for s in schema_switched), (
        f"search_path was not switched to tenant_demo. SQL executed: {schema_switched}"
    )


def test_tenant_detail_shows_correct_response(client, app):
    """GET /platform/tenants/{slug} returns the tenant detail."""
    tenant_row = ("demo", "Demo Tenant", "AUDIT_COMPANY", "ACTIVE", "tenant_demo", None)
    mock_db = _make_mock_db(fetchone=tenant_row)

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _super_admin_token()
    app.dependency_overrides[get_public_db] = override_public_db

    resp = client.get("/platform/tenants/demo")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["slug"] == "demo"
    assert data["status"] == "ACTIVE"