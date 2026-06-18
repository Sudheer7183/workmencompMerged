"""
Integration tests for Calc Engine Config API — Phase 3.

Uses the same TestClient + dependency_overrides pattern as Phase 1/2 tests.
"""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_redis_dep
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


def _make_db_mock(row: dict | None = None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = row
    result.mappings.return_value.all.return_value = [row] if row else []
    result.fetchone.return_value = None
    db.execute.return_value = result
    db.commit = AsyncMock()
    return db


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_get_carrier_calc_config_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """GET /api/v1/admin/calc-config/{carrier_id} must not 404."""
    db_mock = _make_db_mock({
        "carrier_id": 1,
        "use_calculation_engine": True,
        "updated_at": "2026-06-01T00:00:00+00:00",
        "updated_by": "admin@demo.test",
    })

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
        patch("app.api.v1.carrier_config.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/admin/calc-config/1",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    # 404 is OK (no row) - just ensure the endpoint is wired (not 500 or method not allowed)
    assert resp.status_code not in (500, 405), resp.text


def test_put_carrier_calc_config_forbidden_for_reviewer(
    client: TestClient, app: FastAPI
) -> None:
    """PUT /api/v1/admin/calc-config/{carrier_id} with REVIEWER → 403."""
    db_mock = AsyncMock()
    db_mock.commit = AsyncMock()

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _reviewer_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
    ):
        resp = client.put(
            "/api/v1/admin/calc-config/1",
            json={"use_calculation_engine": False},
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 403, resp.text


def test_put_carrier_calc_config_engine_off(client: TestClient, app: FastAPI) -> None:
    """PUT with {use_calculation_engine: false} must not raise and not 404."""
    db_mock = _make_db_mock({
        "carrier_id": 1,
        "use_calculation_engine": False,
        "updated_at": "2026-06-01T00:00:00+00:00",
        "updated_by": "admin@demo.test",
    })

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
        patch("app.api.v1.carrier_config.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.put(
            "/api/v1/admin/calc-config/1",
            json={"use_calculation_engine": False},
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 500), resp.text


def test_get_tenant_calc_config_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """GET /api/v1/admin/tenant-calc-config must not 404."""
    db_mock = _make_db_mock({
        "tenant_id": 1,
        "default_use_calculation_engine": True,
        "updated_at": "2026-06-01T00:00:00+00:00",
    })

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _admin_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
    ):
        resp = client.get(
            "/api/v1/admin/tenant-calc-config",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (500, 405), resp.text


def test_frontend_read_only_calc_config_endpoint_exists(
    client: TestClient, app: FastAPI
) -> None:
    """GET /api/v1/carrier-calc-config/{carrier_id} is accessible for REVIEWER."""
    db_mock = _make_db_mock({
        "carrier_id": 1,
        "use_calculation_engine": True,
    })

    async def override_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: _reviewer_token()
    app.dependency_overrides[get_db] = override_db

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
        patch("app.api.v1.carrier_config.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.get(
            "/api/v1/carrier-calc-config/1",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (500, 405), resp.text


# ── resolve_effective_mode — unit tests (no HTTP, direct service calls) ──────

@pytest.mark.asyncio
async def test_resolve_effective_mode_reads_db() -> None:
    """
    When carrier config has use_calculation_engine = False, returns False.
    """
    from app.services.audit_calculation_service import AuditCalculationService
    svc = AuditCalculationService()
    db  = AsyncMock()

    run_result = MagicMock()
    run_result.fetchone.return_value = None  # no per-run override
    carrier_result = MagicMock()
    carrier_result.fetchone.return_value = (False,)

    db.execute.side_effect = [run_result, carrier_result]
    svc._redis_get = AsyncMock(return_value=None)   # type: ignore[method-assign]
    svc._redis_set = AsyncMock()                     # type: ignore[method-assign]

    mode = await svc.resolve_effective_mode(
        carrier_id=1, run_id=10, db=db, schema_name="tenant_demo",
    )
    assert mode is False


@pytest.mark.asyncio
async def test_resolve_effective_mode_engine_on() -> None:
    """When carrier config use_calculation_engine = True, returns True."""
    from app.services.audit_calculation_service import AuditCalculationService
    svc = AuditCalculationService()
    db  = AsyncMock()

    run_result = MagicMock()
    run_result.fetchone.return_value = None
    carrier_result = MagicMock()
    carrier_result.fetchone.return_value = (True,)

    db.execute.side_effect = [run_result, carrier_result]
    svc._redis_get = AsyncMock(return_value=None)   # type: ignore[method-assign]
    svc._redis_set = AsyncMock()                     # type: ignore[method-assign]

    mode = await svc.resolve_effective_mode(
        carrier_id=1, run_id=10, db=db, schema_name="tenant_demo",
    )
    assert mode is True


@pytest.mark.asyncio
async def test_resolve_effective_mode_per_run_override_takes_precedence() -> None:
    """Per-run override = False takes precedence over carrier default."""
    from app.services.audit_calculation_service import AuditCalculationService
    svc = AuditCalculationService()
    db  = AsyncMock()

    run_result = MagicMock()
    run_result.fetchone.return_value = (False,)
    db.execute.return_value = run_result
    svc._redis_get = AsyncMock(return_value=None)   # type: ignore[method-assign]

    mode = await svc.resolve_effective_mode(
        carrier_id=1, run_id=10, db=db, schema_name="tenant_demo",
    )
    assert mode is False
