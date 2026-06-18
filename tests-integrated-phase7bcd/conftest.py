"""
Shared test fixtures for Phase 7B–7D test package.

Extends the existing Phase 1–7A conftest by providing:
  - tenant_auth_headers: JWT headers for a TENANT_ADMIN test user
  - test_carrier_id: a known carrier_id in the test tenant
  - client: AsyncClient for HTTP tests
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Allow tests to reference the main app
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


@pytest.fixture(scope="session")
def test_carrier_id() -> int:
    """Known carrier_id in the test tenant (seeded during provisioning)."""
    return int(os.getenv("TEST_CARRIER_ID", "1"))


@pytest.fixture(scope="session")
def tenant_auth_headers() -> dict[str, str]:
    """
    JWT bearer token for a TENANT_ADMIN test user.
    When SKIP_JWT_VERIFICATION=true, any well-formed token is accepted.
    """
    import base64
    import json

    # Build a minimal test JWT payload
    payload = {
        "sub": "test-tenant-admin",
        "role": "TENANT_ADMIN",
        "schema_name": "tenant_test",
        "email": "admin@test.tenant.com",
    }
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    fake_token = f"test.{encoded}.sig"

    return {"Authorization": f"Bearer {fake_token}"}


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client pointed at the FastAPI test app.
    Uses ASGI transport for in-process testing.
    """
    from app.main import app as fastapi_app
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://testserver",
    ) as ac:
        yield ac
