"""
Unit tests for KeycloakAdminService — Phase 2 (V9 S4.3, S25.2)

Tests verify:
  - JWT tenant_slug claim extraction
  - SUPER_ADMIN null tenant_slug handling
  - Single-string role claim (not array)
  - Invalid signature rejection
  - Expired token rejection
  - Redis JWKS caching behaviour
  - kid-miss cache invalidation and refetch
  - create_tenant_admin_user sets tenant_slug attribute (not tenant)
  - create_tenant_user assigns correct role
  - get_admin_token uses client_credentials grant
"""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.auth import Role
from app.services.keycloak_admin_service import KeycloakAdminService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_service() -> KeycloakAdminService:
    """Creates a KeycloakAdminService with test settings."""
    svc = KeycloakAdminService.__new__(KeycloakAdminService)
    from app.core.config import get_settings
    svc._settings = get_settings()
    svc._http_client = AsyncMock()
    return svc


def _make_mock_jwks() -> tuple[dict, object]:
    """Generates a test RSA key pair and returns (jwks_dict, private_key)."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    import base64

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_numbers = private_key.public_key().public_numbers()

    def _i2b64(n: int) -> str:
        byte_length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()

    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-kid-001",
                "n": _i2b64(pub_numbers.n),
                "e": _i2b64(pub_numbers.e),
            }
        ]
    }
    return jwks, private_key


def _sign_token(private_key: object, claims: dict) -> str:
    """Creates a real RS256-signed JWT for testing."""
    from jose import jwt as jose_jwt
    from cryptography.hazmat.primitives import serialization

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    return jose_jwt.encode(
        {**claims, "exp": int(time.time()) + 3600},
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid-001"},
    )


# ---------------------------------------------------------------------------
# verify_token tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_decodes_tenant_slug_claim():
    """JWT with tenant_slug claim → TokenPayload.tenant_slug set correctly."""
    jwks, private_key = _make_mock_jwks()
    token = _sign_token(
        private_key,
        {"sub": "u-001", "email": "auditor@demo.test", "role": "AUDITOR", "tenant_slug": "demo"},
    )

    svc = _build_service()
    with patch.object(svc, "get_jwks", new=AsyncMock(return_value=jwks)):
        payload = await svc.verify_token(token)

    assert payload["tenant_slug"] == "demo"
    assert payload["role"] == "AUDITOR"


@pytest.mark.asyncio
async def test_verify_token_super_admin_has_null_tenant_slug():
    """SUPER_ADMIN JWT with no tenant_slug attribute → tenant_slug absent."""
    jwks, private_key = _make_mock_jwks()
    token = _sign_token(
        private_key,
        {"sub": "sa-001", "email": "superadmin@platform.test", "role": "SUPER_ADMIN"},
    )

    svc = _build_service()
    with patch.object(svc, "get_jwks", new=AsyncMock(return_value=jwks)):
        payload = await svc.verify_token(token)

    assert payload.get("tenant_slug") is None
    assert payload["role"] == "SUPER_ADMIN"


@pytest.mark.asyncio
async def test_verify_token_role_is_single_string_not_array():
    """
    V9 rule: role claim must be a single string, not an array.
    The TokenPayload role field accepts a single Role enum value.
    """
    jwks, private_key = _make_mock_jwks()
    token = _sign_token(
        private_key,
        {"sub": "u-002", "email": "reviewer@demo.test", "role": "REVIEWER", "tenant_slug": "demo"},
    )

    svc = _build_service()
    with patch.object(svc, "get_jwks", new=AsyncMock(return_value=jwks)):
        payload = await svc.verify_token(token)

    role = payload["role"]
    assert isinstance(role, str), "role claim must be a plain string, not a list"
    assert role == "REVIEWER"


@pytest.mark.asyncio
async def test_verify_token_rejects_invalid_signature():
    """Tampered JWT → HTTPException(401)."""
    jwks, private_key = _make_mock_jwks()
    token = _sign_token(
        private_key,
        {"sub": "u-003", "email": "tampered@demo.test", "role": "AUDITOR"},
    )
    # Tamper with the signature (last segment)
    parts = token.split(".")
    parts[2] = parts[2][:-4] + "AAAA"
    tampered_token = ".".join(parts)

    svc = _build_service()
    with patch.object(svc, "get_jwks", new=AsyncMock(return_value=jwks)):
        with pytest.raises(HTTPException) as exc_info:
            await svc.verify_token(tampered_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_rejects_expired_token():
    """Expired JWT → HTTPException(401)."""
    jwks, private_key = _make_mock_jwks()

    from cryptography.hazmat.primitives import serialization
    from jose import jwt as jose_jwt

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    expired_token = jose_jwt.encode(
        {
            "sub": "u-004",
            "email": "expired@demo.test",
            "role": "REVIEWER",
            "tenant_slug": "demo",
            "exp": int(time.time()) - 3600,  # In the past
        },
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid-001"},
    )

    svc = _build_service()
    with patch.object(svc, "get_jwks", new=AsyncMock(return_value=jwks)):
        with pytest.raises(HTTPException) as exc_info:
            await svc.verify_token(expired_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_caches_jwks_in_redis():
    """
    First call fetches JWKS from Keycloak and writes to Redis.
    Second call uses Redis cache (no HTTP request).
    """
    jwks, private_key = _make_mock_jwks()
    mock_redis = AsyncMock()
    # First call: cache miss; second call: cache hit
    mock_redis.get.side_effect = [None, json.dumps(jwks)]
    mock_redis.setex = AsyncMock(return_value=True)

    svc = _build_service()
    with (
        patch("app.services.keycloak_admin_service.get_redis_client", new=AsyncMock(return_value=mock_redis)),
        patch.object(svc, "_fetch_jwks_from_keycloak", new=AsyncMock(return_value=jwks)),
    ):
        # First call — should fetch from Keycloak and cache
        result1 = await svc.get_jwks()
        # Second call — should use Redis cache
        result2 = await svc.get_jwks()

        # Assertions must be inside the with block — patch is removed on exit
        assert result1 == jwks
        assert result2 == jwks
        svc._fetch_jwks_from_keycloak.assert_awaited_once()
        mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_jwks_cache_refreshed_on_kid_not_found():
    """
    If kid is absent from cached JWKS, the cache is invalidated and JWKS is refetched.
    """
    stale_jwks = {"keys": [{"kid": "old-kid", "kty": "RSA", "alg": "RS256"}]}
    fresh_jwks, private_key = _make_mock_jwks()
    token = _sign_token(
        private_key,
        {"sub": "u-005", "email": "user@demo.test", "role": "AUDITOR", "tenant_slug": "demo"},
    )

    get_jwks_calls = [stale_jwks, fresh_jwks]
    call_index = 0

    async def _mock_get_jwks() -> dict:
        nonlocal call_index
        result = get_jwks_calls[call_index]
        call_index += 1
        return result

    svc = _build_service()
    invalidate_spy = AsyncMock()
    with (
        patch.object(svc, "get_jwks", side_effect=_mock_get_jwks),
        patch.object(svc, "_invalidate_jwks_cache", invalidate_spy),
    ):
        payload = await svc.verify_token(token)

    invalidate_spy.assert_awaited_once()
    assert payload["sub"] == "u-005"


# ---------------------------------------------------------------------------
# Admin service tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_admin_user_sets_tenant_slug_attribute():
    """
    create_tenant_admin_user must send tenant_slug in the user attributes,
    NOT the prototype's 'tenant' key.
    """
    svc = _build_service()

    # Mock get_admin_token
    svc.get_admin_token = AsyncMock(return_value="mock-admin-token")

    # Capture the payload sent to Keycloak POST /users
    captured_payload: dict = {}

    async def _mock_post(url: str, *, json: dict, headers: dict) -> MagicMock:
        nonlocal captured_payload
        if "/users" in url and "role-mappings" not in url and "reset-password" not in url:
            captured_payload = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"Location": "http://keycloak/admin/realms/audit-platform/users/new-kc-id"}
        return resp

    async def _mock_role_get(url: str, *, headers: dict) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"id": "role-id", "name": "TENANT_ADMIN"})
        return resp

    async def _mock_role_post(url: str, *, json: dict, headers: dict) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    svc._http_client.post = _mock_post
    svc._http_client.get = _mock_role_get

    # Patch _assign_realm_role to avoid second HTTP calls
    with patch.object(svc, "_assign_realm_role", new=AsyncMock()):
        keycloak_id = await svc.create_tenant_admin_user(
            email="admin@demo.test",
            first_name="Demo",
            last_name="Admin",
            tenant_slug="demo",
            temporary_password=None,
            send_invitation=False,
        )

    assert "tenant_slug" in captured_payload.get("attributes", {})
    assert "tenant" not in captured_payload.get("attributes", {})
    assert keycloak_id == "new-kc-id"


@pytest.mark.asyncio
async def test_create_tenant_user_assigns_correct_role():
    """AUDITOR role → Keycloak user is assigned the AUDITOR realm role."""
    svc = _build_service()
    svc.get_admin_token = AsyncMock(return_value="mock-token")

    assigned_role_name: str = ""

    async def _mock_create(url: str, *, json: dict, headers: dict) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"Location": ".../users/auditor-kc-id"}
        return resp

    async def _track_role_assign(admin_token: str, kc_id: str, role) -> None:
        nonlocal assigned_role_name
        assigned_role_name = role.value

    svc._http_client.post = _mock_create

    with patch.object(svc, "_assign_realm_role", side_effect=_track_role_assign):
        await svc.create_tenant_user(
            email="auditor@demo.test",
            first_name="Test",
            last_name="Auditor",
            tenant_slug="demo",
            role=Role.AUDITOR,
        )

    assert assigned_role_name == "AUDITOR"


@pytest.mark.asyncio
async def test_get_admin_token_uses_client_credentials():
    """Admin token fetch must use client_credentials grant, not user credentials."""
    svc = _build_service()

    captured_data: dict = {}

    async def _mock_post(url: str, *, data: dict) -> MagicMock:
        nonlocal captured_data
        captured_data = data
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"access_token": "admin-token-abc"})
        return resp

    svc._http_client.post = _mock_post

    token = await svc.get_admin_token()

    assert token == "admin-token-abc"
    assert captured_data.get("grant_type") == "client_credentials"
    assert "client_id" in captured_data
    assert "client_secret" in captured_data
    assert "password" not in captured_data
    assert "username" not in captured_data
