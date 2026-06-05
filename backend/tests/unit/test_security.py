"""
Unit tests for API security functions — 10 cases.
Tests verify_role, verify_tenant, and token privilege hierarchy.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock

from app.api.security import verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload


# ---------------------------------------------------------------------------
# verify_role
# ---------------------------------------------------------------------------

def test_verify_role_reviewer_passes_reviewer():
    token = TokenPayload(sub="u1", email="u@test.com", role=Role.REVIEWER, tenant_slug="demo")
    verify_role(Role.REVIEWER, token)  # Should not raise


def test_verify_role_auditor_passes_reviewer():
    token = TokenPayload(sub="u1", email="u@test.com", role=Role.AUDITOR, tenant_slug="demo")
    verify_role(Role.REVIEWER, token)  # AUDITOR >= REVIEWER


def test_verify_role_reviewer_fails_auditor():
    token = TokenPayload(sub="u1", email="u@test.com", role=Role.REVIEWER, tenant_slug="demo")
    with pytest.raises(HTTPException) as exc:
        verify_role(Role.AUDITOR, token)
    assert exc.value.status_code == 403


def test_verify_role_super_admin_passes_any():
    token = TokenPayload(sub="sa1", email="sa@platform.com", role=Role.SUPER_ADMIN, tenant_slug=None)
    verify_role(Role.TENANT_ADMIN, token)   # Should not raise
    verify_role(Role.SUPER_ADMIN, token)    # Should not raise


def test_verify_role_tenant_admin_fails_super_admin_requirement():
    """TENANT_ADMIN cannot reach SUPER_ADMIN-required endpoints."""
    token = TokenPayload(sub="ta1", email="ta@test.com", role=Role.TENANT_ADMIN, tenant_slug="demo")
    with pytest.raises(HTTPException) as exc:
        verify_role(Role.SUPER_ADMIN, token)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Role.has_at_least
# ---------------------------------------------------------------------------

def test_role_privilege_ordering():
    assert Role.REVIEWER.has_at_least(Role.REVIEWER)
    assert Role.AUDITOR.has_at_least(Role.REVIEWER)
    assert Role.AUDITOR.has_at_least(Role.AUDITOR)
    assert not Role.REVIEWER.has_at_least(Role.AUDITOR)
    assert Role.SUPER_ADMIN.has_at_least(Role.TENANT_ADMIN)
    assert not Role.TENANT_ADMIN.has_at_least(Role.SUPER_ADMIN)


# ---------------------------------------------------------------------------
# verify_tenant
# ---------------------------------------------------------------------------

def test_verify_tenant_matching_slug_passes():
    from app.schemas.tenant import TenantRecord
    req = MagicMock()
    req.state.tenant = TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo", status="ACTIVE")
    token = TokenPayload(sub="u1", email="u@demo.com", role=Role.AUDITOR, tenant_slug="demo")
    verify_tenant(req, token)  # Should not raise


def test_verify_tenant_mismatched_slug_raises_403():
    from app.schemas.tenant import TenantRecord
    req = MagicMock()
    req.state.tenant = TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo", status="ACTIVE")
    token = TokenPayload(sub="u1", email="u@other.com", role=Role.AUDITOR, tenant_slug="other")
    with pytest.raises(HTTPException) as exc:
        verify_tenant(req, token)
    assert exc.value.status_code == 403


def test_verify_tenant_super_admin_bypasses():
    """SUPER_ADMIN skips tenant check — operates across all tenants."""
    from app.schemas.tenant import TenantRecord
    req = MagicMock()
    req.state.tenant = TenantRecord(slug="demo", schema_name="tenant_demo", name="Demo", status="ACTIVE")
    token = TokenPayload(sub="sa1", email="sa@platform.com", role=Role.SUPER_ADMIN, tenant_slug=None)
    verify_tenant(req, token)  # Should not raise


def test_verify_tenant_no_tenant_state_raises_400():
    """Missing tenant state (exempt path bug) returns 400."""
    req = MagicMock()
    req.state.tenant = None
    token = TokenPayload(sub="u1", email="u@demo.com", role=Role.AUDITOR, tenant_slug="demo")
    with pytest.raises(HTTPException) as exc:
        verify_tenant(req, token)
    assert exc.value.status_code == 400
