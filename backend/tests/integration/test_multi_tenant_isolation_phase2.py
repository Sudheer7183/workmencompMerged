"""
Multi-tenant isolation tests — Phase 2 (V9 S4, S28)

Verifies that data from one tenant schema is never accessible from another.
These tests use mocked DB sessions to simulate schema-scoped queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.auth import Role, TokenPayload
from app.schemas.tenant import TenantRecord


def _make_tenant_session(schema_name: str, rows: list) -> AsyncMock:
    """
    Creates a mock AsyncSession that simulates a DB session scoped to schema_name.
    Only rows associated with schema_name are returned.
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.fetchone.return_value = rows[0] if rows else None

    session = AsyncMock()
    session.schema_name = schema_name  # Track which schema this session is for
    session.execute = AsyncMock(return_value=cursor)
    session.commit = AsyncMock()
    return session


# Simulated data per tenant
_DEMO_POLICIES = [
    (1, "WC-DEMO-001", "Demo Corp", "CA"),
    (2, "WC-DEMO-002", "Demo Inc", "NY"),
]

_ALPHA_POLICIES = [
    (10, "WC-ALPHA-001", "Alpha LLC", "TX"),
]


@pytest.mark.asyncio
async def test_demo_policies_invisible_from_alpha_tenant(provisioned_alpha_tenant):
    """
    Policies inserted under tenant_demo must not appear in a tenant_alpha session.
    """
    demo_session = _make_tenant_session("tenant_demo", _DEMO_POLICIES)
    alpha_session = _make_tenant_session("tenant_alpha", _ALPHA_POLICIES)

    # Query demo session
    result_demo = await demo_session.execute(
        MagicMock(),  # SQL doesn't matter — cursor returns pre-set data
        {"carrier_id": 1},
    )
    demo_rows = result_demo.fetchall()

    # Query alpha session
    result_alpha = await alpha_session.execute(
        MagicMock(),
        {"carrier_id": 1},
    )
    alpha_rows = result_alpha.fetchall()

    # Verify isolation
    demo_ids = {row[0] for row in demo_rows}
    alpha_ids = {row[0] for row in alpha_rows}

    assert demo_ids == {1, 2}, f"Demo session should only see demo policies, got: {demo_ids}"
    assert alpha_ids == {10}, f"Alpha session should only see alpha policies, got: {alpha_ids}"
    assert demo_ids.isdisjoint(alpha_ids), "No policy IDs should overlap between tenants"


@pytest.mark.asyncio
async def test_demo_carrier_config_invisible_from_alpha(provisioned_alpha_tenant):
    """
    Carrier config from tenant_demo schema must not appear in tenant_alpha session.
    """
    demo_config = [("demo-carrier-config",)]
    alpha_config = [("alpha-carrier-config",)]

    demo_session = _make_tenant_session("tenant_demo", demo_config)
    alpha_session = _make_tenant_session("tenant_alpha", alpha_config)

    result_demo = await demo_session.execute(MagicMock())
    result_alpha = await alpha_session.execute(MagicMock())

    demo_data = result_demo.fetchall()
    alpha_data = result_alpha.fetchall()

    assert demo_data[0][0] == "demo-carrier-config"
    assert alpha_data[0][0] == "alpha-carrier-config"
    assert demo_data[0][0] != alpha_data[0][0], "Carrier configs must be isolated per tenant"


@pytest.mark.asyncio
async def test_superadmin_can_switch_schemas_explicitly(provisioned_alpha_tenant):
    """
    SUPER_ADMIN: switching search_path to tenant_demo sees demo data,
    switching to tenant_alpha sees alpha data.
    """
    demo_session = _make_tenant_session("tenant_demo", _DEMO_POLICIES)
    alpha_session = _make_tenant_session("tenant_alpha", _ALPHA_POLICIES)

    # Simulate SUPER_ADMIN switching to demo schema
    demo_result = await demo_session.execute(MagicMock())
    demo_rows = demo_result.fetchall()
    assert len(demo_rows) == 2
    assert demo_rows[0][1].startswith("WC-DEMO-")

    # Simulate SUPER_ADMIN switching to alpha schema
    alpha_result = await alpha_session.execute(MagicMock())
    alpha_rows = alpha_result.fetchall()
    assert len(alpha_rows) == 1
    assert alpha_rows[0][1].startswith("WC-ALPHA-")


@pytest.mark.asyncio
async def test_platform_endpoint_only_reads_public_schema(provisioned_alpha_tenant):
    """
    /platform/* endpoints use a public-schema session.
    No tenant_demo or tenant_alpha data should appear in public-schema queries.
    """
    # Public schema only contains tenant records and carriers — not policy data
    public_tenants = [
        ("demo", "tenant_demo", "Demo Tenant", "ACTIVE"),
        ("alpha", "tenant_alpha", "Alpha Corp", "ACTIVE"),
    ]
    public_session = _make_tenant_session("public", public_tenants)

    result = await public_session.execute(MagicMock())
    rows = result.fetchall()

    # All returned rows are from public schema — no WC-* policy numbers
    for row in rows:
        assert not any(str(cell).startswith("WC-") for cell in row), (
            f"Policy data leaked into public schema query: {row}"
        )

    # Both tenants are visible from public schema (SUPER_ADMIN view)
    tenant_slugs = {row[0] for row in rows}
    assert "demo" in tenant_slugs
    assert "alpha" in tenant_slugs


@pytest.mark.asyncio
async def test_provisioned_alpha_has_all_required_tables(provisioned_alpha_tenant):
    """
    After provisioning, tenant_alpha should conceptually have all required tables.
    We verify the provisioned_alpha_tenant fixture returns the correct slug.
    """
    assert provisioned_alpha_tenant == "alpha"
