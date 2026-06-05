from __future__ import annotations
"""
Pytest configuration and shared fixtures — Phase 2 extended.

Phase 1 fixtures are preserved unchanged.
Phase 2 additions:
  - mock_keycloak_jwks      — minimal JWKS for RS256 tests
  - mock_keycloak_service   — patches KeycloakAdminService
  - mock_subprocess_alembic — patches subprocess.run for Alembic
  - provisioned_alpha_tenant — fixtures a second tenant schema for isolation tests
"""
# ---------------------------------------------------------------------------
# Phase 3: Set required env vars before Settings is instantiated.
# Settings.model_config reads from env_file=".env", but tests run without
# a real database/redis. We set stub values here so `create_app()` (called
# at module level in main.py) doesn't fail during collection.
# ---------------------------------------------------------------------------
import os as _os
_os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
_os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
_os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")



from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord


# ---------------------------------------------------------------------------
# NOTE: Do NOT define a custom event_loop fixture.
# pytest-asyncio 0.24+ manages the loop automatically when
# asyncio_mode = "auto" and asyncio_default_fixture_loop_scope = "function"
# are set in pyproject.toml.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mock token payloads — Phase 1 (unchanged)
# ---------------------------------------------------------------------------

@pytest.fixture
def reviewer_token() -> TokenPayload:
    return TokenPayload(
        sub="r-001",
        email="reviewer@demo.test",
        role=Role.REVIEWER,
        tenant_slug="demo",
    )


@pytest.fixture
def auditor_token() -> TokenPayload:
    return TokenPayload(
        sub="a-001",
        email="auditor@demo.test",
        role=Role.AUDITOR,
        tenant_slug="demo",
    )


@pytest.fixture
def tenant_admin_token() -> TokenPayload:
    return TokenPayload(
        sub="ta-001",
        email="admin@demo.test",
        role=Role.TENANT_ADMIN,
        tenant_slug="demo",
    )


@pytest.fixture
def super_admin_token() -> TokenPayload:
    return TokenPayload(
        sub="sa-001",
        email="superadmin@platform.test",
        role=Role.SUPER_ADMIN,
        tenant_slug=None,
    )


@pytest.fixture
def wrong_tenant_token() -> TokenPayload:
    """Token whose tenant_slug does not match the resolved tenant."""
    return TokenPayload(
        sub="x-001",
        email="other@other.test",
        role=Role.AUDITOR,
        tenant_slug="other-tenant",
    )


# ---------------------------------------------------------------------------
# Mock DB session — Phase 1 (unchanged)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> AsyncMock:
    """Returns a mock AsyncSession with all commonly used methods stubbed."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_request_with_tenant() -> MagicMock:
    """Returns a mock Starlette Request with request.state.tenant populated."""
    req = MagicMock()
    req.state.tenant = TenantRecord(
        slug="demo",
        schema_name="tenant_demo",
        name="Demo Tenant",
        status="ACTIVE",
    )
    return req


# ---------------------------------------------------------------------------
# Phase 2 — Keycloak JWKS fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_keycloak_jwks() -> dict:
    """
    Returns a minimal JWKS structure for use in RS256 verification tests.
    Tests that need a signed token should generate one using the test RSA key
    returned alongside this fixture.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import base64
    import struct

    # Generate an in-memory RSA key pair for testing
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_numbers = public_key.public_key().public_numbers() if hasattr(public_key, 'public_key') else public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        byte_length = (n.bit_length() + 7) // 8
        n_bytes = n.to_bytes(byte_length, "big")
        return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode()

    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-kid-001",
                "n": _int_to_base64url(pub_numbers.n),
                "e": _int_to_base64url(pub_numbers.e),
            }
        ]
    }
    return jwks


# ---------------------------------------------------------------------------
# Phase 2 — Mock KeycloakAdminService
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_keycloak_service(mocker):
    """
    Mocks KeycloakAdminService throughout the service layer.

    create_tenant_admin_user → returns "mock-keycloak-id-001"
    create_tenant_user       → returns "mock-keycloak-id-002"
    deactivate_user          → returns None
    get_user_by_email        → returns None (not found by default)
    """
    mock = mocker.patch(
        "app.services.keycloak_admin_service.KeycloakAdminService",
        autospec=True,
    )
    instance = mock.return_value
    instance.create_tenant_admin_user = AsyncMock(return_value="mock-keycloak-id-001")
    instance.create_tenant_user = AsyncMock(return_value="mock-keycloak-id-002")
    instance.deactivate_user = AsyncMock(return_value=None)
    instance.get_user_by_email = AsyncMock(return_value=None)
    instance.get_admin_token = AsyncMock(return_value="mock-admin-token")
    instance.verify_token = AsyncMock(return_value={
        "sub": "mock-sub",
        "email": "mock@demo.test",
        "role": "AUDITOR",
        "tenant_slug": "demo",
    })
    # Patch get_keycloak_admin_service to return the mocked instance
    mocker.patch(
        "app.services.keycloak_admin_service.get_keycloak_admin_service",
        return_value=instance,
    )
    return instance


# ---------------------------------------------------------------------------
# Phase 2 — Mock subprocess.run for Alembic migrations
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_subprocess_alembic(mocker):
    """
    Mocks subprocess.run so Alembic migration does not attempt a real DB connection.
    Returns a MagicMock with returncode=0 (success).
    """
    return mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )


# ---------------------------------------------------------------------------
# Phase 2 — Mock S3 client for logo upload tests
# ---------------------------------------------------------------------------

@pytest.fixture
def s3_mock(mocker):
    """
    Mocks boto3.client('s3') to avoid real AWS calls in tests.
    put_object succeeds by default.
    """
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    mocker.patch("boto3.client", return_value=mock_s3)
    return mock_s3


# ---------------------------------------------------------------------------
# Phase 2 — provisioned_alpha_tenant fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def provisioned_alpha_tenant(mock_keycloak_service, mock_subprocess_alembic) -> str:
    """
    Provides a second tenant slug 'alpha' for multi-tenant isolation tests.
    The schema creation and Alembic subprocess are mocked so no actual DB ops run.
    Returns the slug 'alpha'.
    """
    return "alpha"
