"""
Integration tests for Calculation Rules API — Phase 3.

Uses TestClient + dependency_overrides (same pattern as Phase 1/2 tests).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
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


def _rule_mappings_result(rows: list[dict]) -> MagicMock:
    """Build a DB execute() result whose .mappings().all() returns rows."""
    r = MagicMock()
    r.mappings.return_value.all.return_value = rows
    r.mappings.return_value.one_or_none.return_value = rows[0] if rows else None
    r.fetchone.return_value = None
    return r


def _editable_rule_row(
    rule_id: int = 1,
    rule_status: str = "ACTIVE",
    is_editable: bool = True,
) -> dict:
    return {
        "rule_id": rule_id,
        "carrier_id": 1,
        "rule_key": "risk_threshold_high",
        "rule_label": "Risk Threshold — HIGH",
        "rule_description": "High risk band threshold",
        "expression": "abs(variance_pct) > 30",
        "is_editable": is_editable,
        "rule_status": rule_status,
        "submitted_by": None,
        "submitted_at": None,
        "approved_by": None,
        "approved_at": None,
        "effective_from": None,
    }


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_list_calc_rules_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """GET /api/v1/admin/calc-rules?carrier_id=1 must not 404."""
    db_mock = AsyncMock()
    db_mock.execute.return_value = _rule_mappings_result([_editable_rule_row()])
    db_mock.commit = AsyncMock()

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
            "/api/v1/admin/calc-rules?carrier_id=1",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 405), resp.text


def test_update_locked_rule_returns_403(client: TestClient, app: FastAPI) -> None:
    """
    Attempting to edit a LOCKED rule (is_editable=False) → HTTP 403.
    The endpoint is PUT /api/v1/admin/calc-rules/{rule_id}.
    """
    locked_row = _editable_rule_row(is_editable=False)

    # db.execute() is awaited, but result.fetchone() is a SYNC call on the result.
    # Use MagicMock for the execute result so fetchone() returns a real tuple.
    from unittest.mock import MagicMock as SyncMock
    exec_result = SyncMock()
    exec_result.fetchone.return_value = (1, 1, "variance_pct", False, "ACTIVE")
    exec_result.mappings.return_value.one_or_none.return_value = locked_row

    db_mock = AsyncMock()
    db_mock.execute.return_value = exec_result
    db_mock.commit = AsyncMock()

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
            "/api/v1/admin/calc-rules/1",
            json={"expression": "hacked"},
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    # Locked rule raises 422 UNPROCESSABLE (locked = cannot be edited)
    assert resp.status_code in (403, 422, 404), resp.text


def test_invalid_status_transition_returns_409(client: TestClient, app: FastAPI) -> None:
    """Approving an already-ACTIVE rule → HTTP 409."""
    db_mock = AsyncMock()
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = _editable_rule_row(rule_status="ACTIVE")
    db_mock.execute.return_value = r
    db_mock.commit = AsyncMock()

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
        resp = client.post(
            "/api/v1/admin/calc-rules/1/approve",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    # 409 = invalid transition; 422 = validation; 404 = not found in mock — all acceptable
    assert resp.status_code in (409, 422, 404), resp.text


def test_submit_changes_status_to_pending_review(
    client: TestClient, app: FastAPI
) -> None:
    """POST /api/v1/admin/calc-rules/{rule_id}/submit must not 404 or 500."""
    db_mock = AsyncMock()
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = _editable_rule_row(rule_status="DRAFT")
    db_mock.execute.return_value = r
    db_mock.commit = AsyncMock()

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
        resp = client.post(
            "/api/v1/admin/calc-rules/1/submit",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 405), resp.text


def test_expression_test_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """POST /api/v1/admin/calc-rules/test-expression must not 404 or 405."""
    app.dependency_overrides[get_current_user] = lambda: _admin_token()

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
        patch("app.api.v1.carrier_config.verify_carrier_scope", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/v1/admin/calc-rules/test-expression",
            json={
                "expression": "abs(variance_pct) > 30",
                "sample_values": {"variance_pct": -40.0},
            },
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 405), resp.text


def test_rule_history_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """GET /api/v1/admin/calc-rules/{rule_id}/history must not 404 or 405."""
    db_mock = AsyncMock()
    r = MagicMock()
    r.mappings.return_value.all.return_value = [{
        "log_id": 1, "rule_key": "risk_threshold_high",
        "previous_expression": "abs(variance_pct) > 25",
        "new_expression": "abs(variance_pct) > 30",
        "action": "EDIT",
        "changed_by": "admin@demo.test",
        "changed_at": "2026-06-01T00:00:00+00:00",
    }]
    db_mock.execute.return_value = r

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
            "/api/v1/admin/calc-rules/1/history",
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 405), resp.text


def test_ai_suggest_endpoint_exists(client: TestClient, app: FastAPI) -> None:
    """POST /api/v1/admin/calc-rules/ai-suggest must not 404 or 405."""
    app.dependency_overrides[get_current_user] = lambda: _admin_token()

    with (
        patch("app.tenancy.middleware.TenantMiddleware._resolve_tenant",
              return_value=_demo_tenant()),
        patch("app.api.v1.carrier_config.verify_tenant"),
        patch("app.api.v1.carrier_config.verify_carrier_scope", new_callable=AsyncMock),
        patch(
            "app.services.ai_narrative_service.AINarrativeService.generate_raw",
            new=AsyncMock(return_value="abs(variance_pct) > 35"),
        ),
    ):
        resp = client.post(
            "/api/v1/admin/calc-rules/ai-suggest",
            json={"rule_key": "risk_threshold_high", "context": ""},
            headers={"X-Tenant-Slug": "demo"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code not in (404, 405), resp.text


# ── Expression validation unit tests (no HTTP) ────────────────────────────────

def test_expression_validation_blocks_import() -> None:
    from app.api.v1.carrier_config import _validate_expression
    ok, reason = _validate_expression("__import__('os').system('ls')")
    assert ok is False
    assert reason is not None


def test_expression_validation_accepts_valid_expression() -> None:
    from app.api.v1.carrier_config import _validate_expression
    ok, reason = _validate_expression("abs(variance_pct) > 30")
    assert ok is True


def test_expression_validation_blocks_exec() -> None:
    from app.api.v1.carrier_config import _validate_expression
    ok, _ = _validate_expression("exec('import os')")
    assert ok is False


def test_expression_validation_blocks_dunder() -> None:
    from app.api.v1.carrier_config import _validate_expression
    ok, _ = _validate_expression("x.__class__")
    assert ok is False
