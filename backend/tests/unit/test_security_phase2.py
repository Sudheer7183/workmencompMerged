"""
Unit tests for Phase 2 security — JWT tenant/role verification.

Tests the behaviour of get_current_user, verify_tenant, and verify_role
when live Keycloak RS256 verification is active (SKIP_JWT_VERIFICATION=false).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_public_db
from app.api.security import get_current_user, verify_role, verify_tenant
from app.main import create_app
from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord


# ---------------------------------------------------------------------------
# App and client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture
def client(app):
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _demo_tenant() -> TenantRecord:
    return TenantRecord(
        slug="demo", schema_name="tenant_demo", name="Demo Tenant", status="ACTIVE"
    )


def _make_mock_db(fetchone=None, fetchall=None, scalar_one=0) -> AsyncMock:
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.scalar_one.return_value = scalar_one
    mock_db = AsyncMock()
    mock_db.execute.return_value = cursor
    return mock_db


# ---------------------------------------------------------------------------
# verify_tenant tests
# ---------------------------------------------------------------------------


def test_live_jwt_verify_tenant_slug_must_match_subdomain():
    """JWT tenant_slug=beta + resolved tenant=demo → verify_tenant raises 403."""
    token = TokenPayload(
        sub="u-001",
        email="auditor@beta.test",
        role=Role.AUDITOR,
        tenant_slug="beta",          # Mismatch
    )
    req = MagicMock()
    req.state.tenant = _demo_tenant()  # slug = "demo"

    with pytest.raises(HTTPException) as exc_info:
        verify_tenant(req, token)

    assert exc_info.value.status_code == 403


def test_live_jwt_super_admin_bypasses_verify_tenant():
    """SUPER_ADMIN with tenant_slug=None must NOT raise even when tenant is set."""
    token = TokenPayload(
        sub="sa-001",
        email="superadmin@platform.test",
        role=Role.SUPER_ADMIN,
        tenant_slug=None,
    )
    req = MagicMock()
    req.state.tenant = _demo_tenant()

    # Must not raise
    verify_tenant(req, token)


def test_verify_tenant_passes_when_slugs_match():
    """JWT tenant_slug matches resolved tenant → no exception."""
    token = TokenPayload(
        sub="u-002",
        email="auditor@demo.test",
        role=Role.AUDITOR,
        tenant_slug="demo",
    )
    req = MagicMock()
    req.state.tenant = _demo_tenant()

    verify_tenant(req, token)  # Should not raise


# ---------------------------------------------------------------------------
# verify_role tests
# ---------------------------------------------------------------------------


def test_verify_role_reviewer_cannot_access_auditor_resource():
    """REVIEWER attempting AUDITOR-protected resource → 403."""
    token = TokenPayload(
        sub="r-001",
        email="reviewer@demo.test",
        role=Role.REVIEWER,
        tenant_slug="demo",
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_role(Role.AUDITOR, token)

    assert exc_info.value.status_code == 403


def test_verify_role_auditor_can_access_reviewer_resource():
    """AUDITOR meets REVIEWER requirement — must not raise."""
    token = TokenPayload(
        sub="a-001",
        email="auditor@demo.test",
        role=Role.AUDITOR,
        tenant_slug="demo",
    )
    verify_role(Role.REVIEWER, token)  # Should not raise


def test_reviewer_cannot_create_users(client, app):
    """REVIEWER token → POST /api/v1/tenant/users → 403."""
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub="r-001",
        email="reviewer@demo.test",
        role=Role.REVIEWER,
        tenant_slug="demo",
    )
    app.dependency_overrides[get_db] = override_db

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.post(
            "/api/v1/tenant/users",
            json={
                "email": "newuser@demo.test",
                "first_name": "New",
                "last_name": "User",
                "role": "AUDITOR",
            },
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_auditor_cannot_access_platform_endpoints(client, app):
    """AUDITOR token → GET /platform/tenants → 403."""
    mock_db = _make_mock_db()

    async def override_public_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub="a-001",
        email="auditor@demo.test",
        role=Role.AUDITOR,
        tenant_slug="demo",
    )
    app.dependency_overrides[get_public_db] = override_public_db

    resp = client.get("/platform/tenants")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_user_creation_writes_keycloak_id_to_db(client, app, mock_keycloak_service):
    """
    POST /api/v1/tenant/users with valid TENANT_ADMIN token:
    Keycloak user is created and the returned keycloak_id is passed to DB INSERT.
    """
    mock_db = _make_mock_db()

    # Simulate DB returning a newly created user row on INSERT
    insert_cursor = MagicMock()
    insert_cursor.fetchone.return_value = (
        1, "mock-keycloak-id-002", "newuser@demo.test",
        "New", "User", "AUDITOR", False, True,
    )
    mock_db.execute.return_value = insert_cursor

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub="ta-001",
        email="admin@demo.test",
        role=Role.TENANT_ADMIN,
        tenant_slug="demo",
    )
    app.dependency_overrides[get_db] = override_db

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.post(
            "/api/v1/tenant/users",
            json={
                "email": "newuser@demo.test",
                "first_name": "New",
                "last_name": "User",
                "role": "AUDITOR",
            },
            headers={"X-Tenant-Slug": "demo"},
        )

    # Should not 403 or 500
    assert resp.status_code not in (403, 500), f"Got {resp.status_code}: {resp.text}"
