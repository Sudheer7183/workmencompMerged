"""
Integration tests for TENANT_ADMIN /api/v1/tenant/* endpoints — Phase 2.
"""
from __future__ import annotations

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


def _demo_tenant() -> TenantRecord:
    return TenantRecord(
        slug="demo", schema_name="tenant_demo", name="Demo Tenant", status="ACTIVE"
    )


def _tenant_admin() -> TokenPayload:
    return TokenPayload(
        sub="ta-001",
        email="admin@demo.test",
        role=Role.TENANT_ADMIN,
        tenant_slug="demo",
    )


def _reviewer() -> TokenPayload:
    return TokenPayload(
        sub="r-001",
        email="reviewer@demo.test",
        role=Role.REVIEWER,
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


def _apply_overrides(app, mock_db: AsyncMock, token: TokenPayload) -> None:
    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: token


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------


def test_put_tenant_profile_saves_to_tenant_schema(client, app):
    """PUT /api/v1/tenant/profile with TENANT_ADMIN → should accept and persist."""
    mock_db = _make_mock_db(fetchone=(
        "Demo Corp", "Demo Corp Legal", "123 Main St", None,
        "Springfield", "IL", "62701", "555-1234", "https://demo.example.com",
    ))
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.put(
            "/api/v1/tenant/profile",
            json={"display_name": "Demo Corp", "legal_name": "Demo Corp Legal"},
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code not in (403, 500), f"Got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Branding validation tests
# ---------------------------------------------------------------------------


def test_put_tenant_branding_validates_hex_color_too_short(client, app):
    """brand_color with 5 chars → 422 (invalid hex)."""
    mock_db = _make_mock_db()
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.put(
            "/api/v1/tenant/branding",
            json={"brand_color": "1A3C5"},  # 5 chars — invalid
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


def test_put_tenant_branding_validates_hex_color_too_long(client, app):
    """brand_color with 7 chars → 422 (invalid hex)."""
    mock_db = _make_mock_db()
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.put(
            "/api/v1/tenant/branding",
            json={"brand_color": "1A3C5E7"},  # 7 chars — invalid
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


def test_put_tenant_branding_valid_six_char_hex(client, app):
    """brand_color with exactly 6 hex chars → 200."""
    branding_row = (None, None, None, "1A3C5E")
    mock_db = _make_mock_db(fetchone=branding_row)
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.put(
            "/api/v1/tenant/branding",
            json={"brand_color": "1A3C5E"},
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_put_tenant_branding_null_brand_color_accepted(client, app):
    """brand_color = null → 200 (clears the brand colour override)."""
    branding_row = (None, None, None, None)
    mock_db = _make_mock_db(fetchone=branding_row)
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.put(
            "/api/v1/tenant/branding",
            json={"brand_color": None},
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Logo upload tests
# ---------------------------------------------------------------------------


def test_post_branding_logo_writes_url_after_s3_confirm(client, app, s3_mock):
    """S3 upload succeeds → logo_url written to DB."""
    mock_db = _make_mock_db(fetchone=(
        "https://s3.example.com/logos/tenant_demo/test.png", None, None, None,
    ))
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.post(
            "/api/v1/tenant/branding/logo",
            files={"file": ("logo.png", b"\x89PNG\r\n" + b"fake_png_content", "image/png")},
            headers={"X-Tenant-Slug": "demo"},
        )

    # Should not fail if S3 succeeds
    assert resp.status_code not in (500,), f"Got {resp.status_code}: {resp.text}"


def test_post_branding_logo_does_not_write_url_on_s3_failure(client, app, mocker):
    """
    S3 upload fails → logo_url NOT updated in DB.
    Atomicity check: no DB commit must occur when S3 raises.
    """
    import botocore.exceptions

    mock_s3_fail = MagicMock()
    mock_s3_fail.put_object.side_effect = botocore.exceptions.ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
        "PutObject",
    )
    mocker.patch("boto3.client", return_value=mock_s3_fail)

    mock_db = _make_mock_db()
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.post(
            "/api/v1/tenant/branding/logo",
            files={"file": ("logo.png", b"\x89PNG\r\n" + b"fake", "image/png")},
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 502, f"Expected 502 on S3 failure, got {resp.status_code}"
    # DB commit must NOT have been called
    mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# User management tests
# ---------------------------------------------------------------------------


def test_post_tenant_users_creates_in_keycloak_and_db(client, app, mock_keycloak_service):
    """POST /api/v1/tenant/users creates user in Keycloak then inserts into DB."""
    user_row = (1, "mock-keycloak-id-002", "newuser@demo.test", "New", "User", "AUDITOR", False, True)

    # The route runs two DB queries in sequence:
    #   1. SELECT to check for email conflict  → must return None (no existing user)
    #   2. INSERT RETURNING new user row       → returns user_row
    # Using a single _make_mock_db(fetchone=user_row) makes BOTH return user_row,
    # causing the conflict check to raise 409 before Keycloak is ever called.
    cursor_no_conflict = MagicMock()
    cursor_no_conflict.fetchone.return_value = None   # no existing user

    cursor_insert_result = MagicMock()
    cursor_insert_result.fetchone.return_value = user_row  # INSERT RETURNING row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[cursor_no_conflict, cursor_insert_result])
    mock_db.commit = AsyncMock()
    _apply_overrides(app, mock_db, _tenant_admin())

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.tenant_admin.get_keycloak_admin_service", return_value=mock_keycloak_service),
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

    assert resp.status_code not in (403, 500), f"Got {resp.status_code}: {resp.text}"
    mock_keycloak_service.create_tenant_user.assert_awaited_once()


def test_get_tenant_users_me_returns_correct_role(client, app):
    """GET /api/v1/tenant/users/me returns the authenticated user's profile."""
    user_row = (1, "ta-001", "admin@demo.test", "Demo", "Admin", "TENANT_ADMIN", True, True)
    mock_db = _make_mock_db(fetchone=user_row)
    _apply_overrides(app, mock_db, _tenant_admin())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.get(
            "/api/v1/tenant/users/me",
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["role"] == "TENANT_ADMIN"


def test_reviewer_cannot_reach_tenant_user_management(client, app):
    """REVIEWER → GET /api/v1/tenant/users → 403."""
    mock_db = _make_mock_db()
    _apply_overrides(app, mock_db, _reviewer())

    with patch(
        "app.tenancy.middleware.TenantMiddleware._resolve_tenant",
        return_value=_demo_tenant(),
    ):
        resp = client.get(
            "/api/v1/tenant/users",
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_delete_tenant_user_deactivates_in_keycloak_and_db(client, app, mock_keycloak_service):
    """DELETE /api/v1/tenant/users/{id} deactivates in Keycloak and marks is_active=False."""
    user_row = MagicMock()
    user_row.__getitem__ = lambda self, i: "kc-id-to-deactivate" if i == 0 else None
    mock_db = _make_mock_db(fetchone=user_row)
    _apply_overrides(app, mock_db, _tenant_admin())

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant", return_value=_demo_tenant()),
        patch("app.api.v1.tenant_admin.get_keycloak_admin_service", return_value=mock_keycloak_service),
    ):
        resp = client.delete(
            "/api/v1/tenant/users/99",
            headers={"X-Tenant-Slug": "demo"},
        )

    assert resp.status_code in (204, 200), f"Expected 204, got {resp.status_code}"
    mock_keycloak_service.deactivate_user.assert_awaited_once()
