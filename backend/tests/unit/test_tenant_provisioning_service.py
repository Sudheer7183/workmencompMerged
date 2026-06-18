"""
Unit tests for TenantProvisioningService — Phase 2 (V9 S5.2)

Tests verify:
  - Creates public.tenants record on provisioning
  - Status set to ACTIVE on success
  - Schema dropped on Alembic failure
  - Tenant soft-deleted on failure
  - Seeds 22 rules per carrier
  - Seeds carrier_theme_config with correct defaults
  - Seeds tenant_calc_config
  - Schema creation uses autocommit connection (asyncpg)
  - Alembic called with target_schema argument
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.tenant_provisioning_service import TenantProvisioningService, _DEFAULT_CALC_RULES


# ---------------------------------------------------------------------------
# Helper: build a TenantProvisioningService with mocked dependencies
# ---------------------------------------------------------------------------

def _build_service(mock_keycloak: AsyncMock | None = None) -> TenantProvisioningService:
    if mock_keycloak is None:
        mock_keycloak = AsyncMock()
        mock_keycloak.create_tenant_admin_user = AsyncMock(return_value="kc-id-001")
    return TenantProvisioningService(mock_keycloak)


def _make_mock_db() -> AsyncMock:
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=cursor)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_creates_public_tenants_record(mock_subprocess_alembic):
    """provision_tenant must INSERT a row into public.tenants on success."""
    svc = _build_service()
    db = _make_mock_db()

    with (
        patch.object(svc, "_create_schema", new=AsyncMock()),
        patch.object(svc, "_run_alembic_migration", new=AsyncMock()),
        patch.object(svc, "_seed_tenant_schema", new=AsyncMock()),
    ):
        slug = await svc.provision_tenant(
            tenant_name="Alpha Corp",
            tenant_slug="alpha",
            tenant_type="AUDIT_COMPANY",
            carrier_ids=[1],
            admin_email="admin@alpha.test",
            admin_first_name="Alpha",
            admin_last_name="Admin",
            temporary_password=None,
            send_invitation=False,
            db=db,
        )

    assert slug == "alpha"
    # First execute call must be the INSERT into public.tenants.
    # str(call_args_list[0]) shows the repr of the TextClause object, not the SQL.
    # Access .args[0] to get the TextClause, then str() it to get the SQL text.
    first_sql = str(db.execute.call_args_list[0].args[0])
    assert "INSERT" in first_sql or "tenants" in first_sql.lower()


@pytest.mark.asyncio
async def test_provision_sets_status_active_on_success(mock_subprocess_alembic):
    """
    On successful provisioning, public.tenants status must be set to ACTIVE.
    """
    svc = _build_service()
    db = _make_mock_db()

    executed_sql: list[str] = []

    async def _capture_execute(stmt, params=None, **kwargs):
        executed_sql.append(str(stmt))
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        return cursor

    db.execute = _capture_execute

    with (
        patch.object(svc, "_create_schema", new=AsyncMock()),
        patch.object(svc, "_run_alembic_migration", new=AsyncMock()),
        patch.object(svc, "_seed_tenant_schema", new=AsyncMock()),
    ):
        await svc.provision_tenant(
            tenant_name="Beta Corp",
            tenant_slug="beta",
            tenant_type="AUDIT_COMPANY",
            carrier_ids=[],
            admin_email="admin@beta.test",
            admin_first_name="Beta",
            admin_last_name="Admin",
            temporary_password=None,
            send_invitation=False,
            db=db,
        )

    # At least one SQL statement must reference ACTIVE
    active_found = any("ACTIVE" in sql for sql in executed_sql)
    assert active_found, f"No ACTIVE status update found in: {executed_sql}"


@pytest.mark.asyncio
async def test_provision_drops_schema_on_alembic_failure():
    """Alembic subprocess returns non-zero → DROP SCHEMA CASCADE is called."""
    svc = _build_service()
    db = _make_mock_db()

    drop_called = False

    async def _raise_on_alembic(schema_name: str) -> None:
        raise RuntimeError("Alembic returned exit code 1")

    async def _track_drop(schema_name: str) -> None:
        nonlocal drop_called
        drop_called = True

    with (
        patch.object(svc, "_create_schema", new=AsyncMock()),
        patch.object(svc, "_run_alembic_migration", side_effect=_raise_on_alembic),
        patch.object(svc, "_drop_schema", side_effect=_track_drop),
    ):
        with pytest.raises(Exception):  # HTTPException from the service
            await svc.provision_tenant(
                tenant_name="Gamma Inc",
                tenant_slug="gamma",
                tenant_type="AUDIT_COMPANY",
                carrier_ids=[],
                admin_email="admin@gamma.test",
                admin_first_name="Gamma",
                admin_last_name="Admin",
                temporary_password=None,
                send_invitation=False,
                db=db,
            )

    assert drop_called, "Schema DROP was not called after Alembic failure"


@pytest.mark.asyncio
async def test_provision_soft_deletes_tenant_on_failure():
    """On any failure, public.tenants status must be set to DELETED."""
    svc = _build_service()
    db = _make_mock_db()

    executed_sql: list[str] = []

    async def _capture_execute(stmt, params=None, **kwargs):
        executed_sql.append(str(stmt))
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        return cursor

    db.execute = _capture_execute

    with (
        patch.object(svc, "_create_schema", new=AsyncMock()),
        patch.object(svc, "_run_alembic_migration", side_effect=RuntimeError("fail")),
        patch.object(svc, "_drop_schema", new=AsyncMock()),
    ):
        with pytest.raises(Exception):
            await svc.provision_tenant(
                tenant_name="Delta LLC",
                tenant_slug="delta",
                tenant_type="AUDIT_COMPANY",
                carrier_ids=[],
                admin_email="admin@delta.test",
                admin_first_name="Delta",
                admin_last_name="Admin",
                temporary_password=None,
                send_invitation=False,
                db=db,
            )

    deleted_found = any("DELETED" in sql for sql in executed_sql)
    assert deleted_found, f"No DELETED status update found in rollback SQL: {executed_sql}"


@pytest.mark.asyncio
async def test_provision_seeds_22_rules_per_carrier(mock_subprocess_alembic):
    """After add_carrier_to_tenant(), exactly 22 calculation rules must be inserted.

    Phase 7A: calc rule seeding was moved from _seed_tenant_schema() to
    add_carrier_to_tenant(). This test now calls add_carrier_to_tenant() directly.
    """
    assert len(_DEFAULT_CALC_RULES) == 22, (
        f"Expected 22 default calc rules, found {len(_DEFAULT_CALC_RULES)}"
    )

    svc = _build_service()
    db = _make_mock_db()

    rule_inserts: list[str] = []

    async def _capture_execute(stmt, params=None, **kwargs):
        stmt_str = str(stmt)
        if "carrier_calc_rules" in stmt_str.lower() and "INSERT" in stmt_str.upper():
            rule_inserts.append(stmt_str)
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        return cursor

    db.execute = _capture_execute

    await svc.add_carrier_to_tenant(
        schema_name="tenant_alpha",
        carrier_id=1,
        db=db,
    )

    assert len(rule_inserts) == 22, (
        f"Expected 22 rule inserts, found {len(rule_inserts)}"
    )


@pytest.mark.asyncio
async def test_provision_seeds_carrier_theme_config(mock_subprocess_alembic):
    """add_carrier_to_tenant() must seed carrier_theme_config with theme_source='SYSTEM'.

    Phase 7A: carrier_theme_config seeding moved from _seed_tenant_schema() to
    add_carrier_to_tenant(). This test now calls add_carrier_to_tenant() directly.
    """
    svc = _build_service()
    db = _make_mock_db()

    theme_config_insert_found = False

    async def _capture_execute(stmt, params=None, **kwargs):
        nonlocal theme_config_insert_found
        stmt_str = str(stmt)
        if "carrier_theme_config" in stmt_str and "SYSTEM" in stmt_str:
            theme_config_insert_found = True
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        return cursor

    db.execute = _capture_execute

    await svc.add_carrier_to_tenant(
        schema_name="tenant_alpha",
        carrier_id=1,
        db=db,
    )

    assert theme_config_insert_found, "carrier_theme_config seeding with SYSTEM source not found"


@pytest.mark.asyncio
async def test_provision_seeds_tenant_calc_config(mock_subprocess_alembic):
    """tenant_calc_config must be seeded with use_calculation_engine=True."""
    svc = _build_service()
    db = _make_mock_db()

    calc_config_found = False

    async def _capture_execute(stmt, params=None, **kwargs):
        nonlocal calc_config_found
        stmt_str = str(stmt)
        if "tenant_calc_config" in stmt_str and "INSERT" in stmt_str:
            calc_config_found = True
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        return cursor

    db.execute = _capture_execute

    with (
        patch.object(svc, "_create_schema", new=AsyncMock()),
        patch.object(svc, "_run_alembic_migration", new=AsyncMock()),
    ):
        # Phase 7A: carrier seeding moved to add_carrier_to_tenant().
        # _seed_tenant_schema now only takes (schema_name, db).
        await svc._seed_tenant_schema("tenant_alpha", db)

    assert calc_config_found, "tenant_calc_config INSERT not found"


@pytest.mark.asyncio
async def test_schema_creation_uses_autocommit_connection():
    """
    _create_schema must use a raw asyncpg connection, not the SQLAlchemy ORM session.
    This ensures schema DDL runs outside any transaction.
    """
    svc = _build_service()

    connect_calls: list[str] = []
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    async def _mock_connect(dsn: str) -> AsyncMock:
        connect_calls.append(dsn)
        return mock_conn

    with patch("asyncpg.connect", side_effect=_mock_connect):
        await svc._create_schema("tenant_test_schema")

    assert len(connect_calls) == 1, "asyncpg.connect must be called exactly once"
    mock_conn.execute.assert_awaited_once()
    # Verify CREATE SCHEMA was the command
    create_call = str(mock_conn.execute.call_args)
    assert "CREATE SCHEMA" in create_call


@pytest.mark.asyncio
async def test_alembic_called_with_target_schema_argument(mocker):
    """
    subprocess.run must be called with the alembic -x target_schema= argument.
    """
    mock_run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="Done", stderr=""),
    )

    svc = _build_service()
    await svc._run_alembic_migration("tenant_alpha")

    assert mock_run.called
    call_args = mock_run.call_args
    # Command is passed as first positional arg
    cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args", [])
    assert "alembic" in cmd
    assert "upgrade" in cmd
    assert "head" in cmd
    # Target schema is passed via env var ALEMBIC_TARGET_SCHEMA (not -x flag)
    kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
    env = kwargs.get("env", {})
    assert env.get("ALEMBIC_TARGET_SCHEMA") == "tenant_alpha", (
        f"ALEMBIC_TARGET_SCHEMA not set in subprocess env: {env}"
    )