"""
tests-integrated/backend/conftest.py
All fixtures for the complete 4-phase integrated test suite.

This file extends the fixtures from backend/tests/conftest.py with:
  - seeded_carrier_id  — carrier already linked to demo tenant
  - seeded_source_id   — ingestion_source for the seeded carrier
  - seeded_policy_id   — one policy record for rollback/exception tests
  - seeded_tenant_id   — the ID of the demo tenant
  - second_carrier_fixture   — second carrier for isolation tests

Usage:
  SKIP_JWT_VERIFICATION=true pytest tests-integrated/backend/ -v
  (Run from the phase4_v1/backend/ directory so app imports resolve.)
"""
from __future__ import annotations

import sys
import os

# Ensure the backend app is importable when running from tests-integrated/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

# Re-export all fixtures from the main conftest so tests can use them
# without importing directly (pytest auto-discovers conftest.py fixtures).
from tests.conftest import (  # noqa: F401
    async_session,
    test_client,
    mock_reviewer_token,
    mock_auditor_token,
    mock_tenant_admin_token,
    mock_super_admin_token,
)

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def seeded_tenant_id(async_session: AsyncSession) -> int:
    """
    Returns the tenant_id of the 'demo' tenant seeded by the main conftest.
    Falls back to creating one if missing.
    """
    result = await async_session.execute(
        text("SELECT tenant_id FROM public.tenants WHERE slug = 'demo' LIMIT 1")
    )
    row = result.fetchone()
    if row:
        return row[0]
    # Create minimal tenant
    ins = await async_session.execute(
        text("""
            INSERT INTO public.tenants (name, slug, schema_name, is_active)
            VALUES ('Demo Tenant', 'demo', 'tenant_demo', TRUE)
            RETURNING tenant_id
        """)
    )
    await async_session.commit()
    return ins.scalar_one()


@pytest.fixture
async def seeded_carrier_id(async_session: AsyncSession, seeded_tenant_id: int) -> int:
    """
    Returns carrier_id for 'Test Carrier', creating it and linking to demo tenant if absent.
    """
    result = await async_session.execute(
        text("SELECT tc.carrier_id FROM public.tenant_carriers tc WHERE tc.tenant_id = :tid LIMIT 1"),
        {"tid": seeded_tenant_id},
    )
    row = result.fetchone()
    if row:
        return row[0]

    ins = await async_session.execute(
        text("""
            INSERT INTO public.carriers (carrier_name, is_active)
            VALUES ('Test Carrier', TRUE)
            RETURNING carrier_id
        """)
    )
    carrier_id = ins.scalar_one()
    await async_session.execute(
        text("INSERT INTO public.tenant_carriers (tenant_id, carrier_id) VALUES (:tid, :cid)"),
        {"tid": seeded_tenant_id, "cid": carrier_id},
    )
    await async_session.commit()
    return carrier_id


@pytest.fixture
async def seeded_source_id(async_session: AsyncSession, seeded_carrier_id: int) -> int:
    """
    Returns source_id of an ingestion_source for the seeded carrier.
    Creates one if absent.
    """
    result = await async_session.execute(
        text("SELECT source_id FROM ingestion_sources WHERE carrier_id = :cid AND is_active = TRUE LIMIT 1"),
        {"cid": seeded_carrier_id},
    )
    row = result.fetchone()
    if row:
        return row[0]

    ins = await async_session.execute(
        text("""
            INSERT INTO ingestion_sources
              (carrier_id, source_name, source_type, is_active, created_at)
            VALUES (:cid, 'Default Test Source', 'xlsx', TRUE, now())
            RETURNING source_id
        """),
        {"cid": seeded_carrier_id},
    )
    await async_session.commit()
    return ins.scalar_one()


@pytest.fixture
async def seeded_policy_id(async_session: AsyncSession, seeded_carrier_id: int) -> int:
    """
    Returns a policy_id for a policy belonging to seeded_carrier_id.
    Creates policyholder + policy if absent.
    """
    result = await async_session.execute(
        text("SELECT policy_id FROM policies WHERE carrier_id = :cid LIMIT 1"),
        {"cid": seeded_carrier_id},
    )
    row = result.fetchone()
    if row:
        return row[0]

    ph = await async_session.execute(
        text("""
            INSERT INTO policyholders (carrier_id, name, fein)
            VALUES (:cid, 'Integration Test Corp', '12-3456789')
            ON CONFLICT (carrier_id, fein) DO UPDATE SET name = EXCLUDED.name
            RETURNING policyholder_id
        """),
        {"cid": seeded_carrier_id},
    )
    ph_id = ph.scalar_one()

    pol = await async_session.execute(
        text("""
            INSERT INTO policies
              (carrier_id, policyholder_id, policy_number, policy_status, audit_status)
            VALUES (:cid, :phid, 'POL-INT-SEED', 'Active', 'Pending')
            ON CONFLICT (carrier_id, policy_number) DO UPDATE SET policy_status = EXCLUDED.policy_status
            RETURNING policy_id
        """),
        {"cid": seeded_carrier_id, "phid": ph_id},
    )
    await async_session.commit()
    return pol.scalar_one()
