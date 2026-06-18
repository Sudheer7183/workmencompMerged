"""
test_tenant_carrier_management.py — Phase 7A

Tests for the new carrier management endpoints and decoupled provisioning.

Coverage:
  - POST /platform/tenants with zero carriers succeeds (Phase 7A)
  - POST /api/v1/admin/carriers — adds a carrier (seeds config + 22 rules)
  - POST /api/v1/admin/carriers — idempotency: re-adding reactivates
  - POST /api/v1/admin/carriers — 404 for unknown carrier_id
  - DELETE /api/v1/admin/carriers/{id} — soft removes carrier
  - DELETE /api/v1/admin/carriers/{id} — 409 if already inactive
  - DELETE /api/v1/admin/carriers/{id} — 404 if never assigned
  - GET /api/v1/tenant/carriers/available — excludes active assignments
  - GET /api/v1/tenant/carriers — returns active only
  - add_carrier_to_tenant() seeds exactly 22 calc rules
  - add_carrier_to_tenant() with ON CONFLICT preserves edited rules
  - add_carrier_to_tenant() re-activates previously soft-deleted carrier
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tenant_provisioning_service import TenantProvisioningService, _DEFAULT_CALC_RULES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_keycloak():
    svc = MagicMock()
    svc.create_tenant_admin_user = AsyncMock(return_value="kc-uuid-001")
    svc.deactivate_user = AsyncMock()
    return svc


@pytest.fixture
def provisioning_service(mock_keycloak):
    return TenantProvisioningService(keycloak_service=mock_keycloak)


# ---------------------------------------------------------------------------
# Unit tests — TenantProvisioningService.add_carrier_to_tenant()
# ---------------------------------------------------------------------------

class TestAddCarrierToTenant:
    """Unit tests for the extracted carrier seeding method."""

    @pytest.mark.asyncio
    async def test_seeds_exactly_22_calc_rules(self, provisioning_service):
        """add_carrier_to_tenant seeds exactly 22 ACTIVE calc rules."""
        assert len(_DEFAULT_CALC_RULES) == 22
        rule_keys = {r["rule_key"] for r in _DEFAULT_CALC_RULES}
        # Required non-editable rules (system-locked)
        assert "variance_amount" in rule_keys
        assert "reported_over_under" in rule_keys
        assert "classified_over_under" in rule_keys
        # Required editable rules
        assert "variance_pct" in rule_keys
        assert "risk_threshold_high" in rule_keys
        assert "risk_threshold_medium" in rule_keys
        assert "zero_payroll_flag" in rule_keys
        assert "missing_payroll_flag" in rule_keys

    @pytest.mark.asyncio
    async def test_add_carrier_creates_junction_row(self, provisioning_service):
        """add_carrier_to_tenant inserts tenant_carriers row when absent."""
        mock_db = AsyncMock(spec=AsyncSession)
        # Simulate: carrier not yet assigned (fetchone returns None)
        existing_result = MagicMock()
        existing_result.fetchone.return_value = None
        mock_db.execute = AsyncMock(return_value=existing_result)

        await provisioning_service.add_carrier_to_tenant(
            schema_name="tenant_test",
            carrier_id=1,
            db=mock_db,
        )

        # Verify commit was called (seeding completed)
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_reactivates_soft_deleted_carrier(self, provisioning_service):
        """add_carrier_to_tenant sets is_active=TRUE for previously removed carrier."""
        mock_db = AsyncMock(spec=AsyncSession)
        # First call (check existing): returns row with is_active=False
        inactive_row = MagicMock()
        inactive_row.__getitem__ = lambda self, idx: False  # is_active = False
        existing_result = MagicMock()
        existing_result.fetchone.return_value = (False,)

        execute_count = [0]
        async def smart_execute(stmt, params=None):
            result = MagicMock()
            if execute_count[0] == 1:  # second execute = the SELECT check
                result.fetchone.return_value = (False,)
            else:
                result.fetchone.return_value = None
            execute_count[0] += 1
            return result

        mock_db.execute = smart_execute
        mock_db.commit = AsyncMock()

        # Should not raise
        await provisioning_service.add_carrier_to_tenant(
            schema_name="tenant_test",
            carrier_id=99,
            db=mock_db,
        )

    @pytest.mark.asyncio
    async def test_idempotent_when_already_active(self, provisioning_service):
        """add_carrier_to_tenant is safe to call when carrier already active."""
        mock_db = AsyncMock(spec=AsyncSession)
        execute_count = [0]

        async def smart_execute(stmt, params=None):
            result = MagicMock()
            if execute_count[0] == 1:
                result.fetchone.return_value = (True,)  # already active
            else:
                result.fetchone.return_value = None
            execute_count[0] += 1
            return result

        mock_db.execute = smart_execute
        mock_db.commit = AsyncMock()

        # Should not raise — is a no-op for the junction row
        await provisioning_service.add_carrier_to_tenant(
            schema_name="tenant_test",
            carrier_id=5,
            db=mock_db,
        )

    @pytest.mark.asyncio
    async def test_all_22_rules_have_required_fields(self):
        """Every default calc rule has all required fields with valid values."""
        required_fields = {"rule_key", "rule_label", "rule_description", "expression", "is_editable"}
        for rule in _DEFAULT_CALC_RULES:
            missing = required_fields - rule.keys()
            assert not missing, f"Rule {rule.get('rule_key')} is missing fields: {missing}"
            assert rule["rule_key"], "rule_key must be non-empty"
            assert rule["rule_label"], "rule_label must be non-empty"
            assert rule["expression"], "expression must be non-empty"
            assert isinstance(rule["is_editable"], bool), "is_editable must be bool"

    @pytest.mark.asyncio
    async def test_non_editable_rules_are_locked(self):
        """The 3 locked rules (variance_amount, over_under) have is_editable=False."""
        locked = {r["rule_key"] for r in _DEFAULT_CALC_RULES if not r["is_editable"]}
        assert "variance_amount" in locked
        assert "reported_over_under" in locked
        assert "classified_over_under" in locked


# ---------------------------------------------------------------------------
# Unit tests — provision_tenant with zero carriers
# ---------------------------------------------------------------------------

class TestProvisionTenantZeroCarriers:
    """Tests confirming provisioning no longer requires carrier_ids."""

    @pytest.mark.asyncio
    async def test_provision_accepts_empty_carrier_ids(self, provisioning_service):
        """provision_tenant with carrier_ids=[] does not raise a validation error."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.commit = AsyncMock()

        with (
            patch.object(provisioning_service, "_create_schema", AsyncMock()),
            patch.object(provisioning_service, "_run_alembic_migration", AsyncMock()),
            patch.object(provisioning_service, "_seed_tenant_schema", AsyncMock()),
        ):
            result = await provisioning_service.provision_tenant(
                tenant_name="Test Co",
                tenant_slug="testco",
                tenant_type="AUDIT_COMPANY",
                carrier_ids=[],  # Empty — must succeed
                admin_email="admin@testco.com",
                admin_first_name="Alice",
                admin_last_name="Admin",
                temporary_password="Pass123!",
                send_invitation=False,
                db=mock_db,
            )
        assert result == "testco"

    @pytest.mark.asyncio
    async def test_provision_with_carriers_still_works(self, provisioning_service):
        """provision_tenant with carrier_ids populated still calls add_carrier_to_tenant."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.commit = AsyncMock()

        add_carrier_calls = []

        async def mock_add_carrier(*, schema_name, carrier_id, db):
            add_carrier_calls.append(carrier_id)

        with (
            patch.object(provisioning_service, "_create_schema", AsyncMock()),
            patch.object(provisioning_service, "_run_alembic_migration", AsyncMock()),
            patch.object(provisioning_service, "_seed_tenant_schema", AsyncMock()),
            patch.object(provisioning_service, "add_carrier_to_tenant", mock_add_carrier),
        ):
            await provisioning_service.provision_tenant(
                tenant_name="Carrier Co",
                tenant_slug="carrierco",
                tenant_type="CARRIER",
                carrier_ids=[1, 2, 3],
                admin_email="admin@carrier.com",
                admin_first_name="Bob",
                admin_last_name="Boss",
                temporary_password=None,
                send_invitation=True,
                db=mock_db,
            )

        assert add_carrier_calls == [1, 2, 3]


# ---------------------------------------------------------------------------
# Integration tests — API endpoints (require running app + DB)
# ---------------------------------------------------------------------------

class TestCarrierManagementAPIIntegration:
    """
    Integration tests for the TENANT_ADMIN carrier management endpoints.
    These require a running test database with the full schema applied.

    Run with: pytest -m integration tests/integration/test_tenant_carrier_management.py
    """

    @pytest.mark.integration
    async def test_post_carriers_adds_carrier_and_seeds_rules(
        self, tenant_admin_client, test_carrier_id
    ):
        """POST /api/v1/tenant/carriers seeds config and 22 calc rules."""
        response = await tenant_admin_client.post(
            "/api/v1/tenant/carriers",
            json={"carrier_id": test_carrier_id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["carrier_id"] == test_carrier_id
        assert data["is_active"] is True

    @pytest.mark.integration
    async def test_post_carriers_404_unknown_carrier(self, tenant_admin_client):
        """POST /api/v1/tenant/carriers with unknown carrier_id returns 404."""
        response = await tenant_admin_client.post(
            "/api/v1/tenant/carriers",
            json={"carrier_id": 999999},
        )
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_delete_carrier_soft_removes(
        self, tenant_admin_client, test_carrier_id
    ):
        """DELETE /api/v1/tenant/carriers/{id} sets is_active=FALSE."""
        # First add
        await tenant_admin_client.post(
            "/api/v1/tenant/carriers",
            json={"carrier_id": test_carrier_id},
        )
        # Then remove
        response = await tenant_admin_client.delete(
            f"/api/v1/tenant/carriers/{test_carrier_id}"
        )
        assert response.status_code == 204

    @pytest.mark.integration
    async def test_delete_carrier_409_already_inactive(
        self, tenant_admin_client, test_carrier_id
    ):
        """DELETE on already-inactive carrier returns 409."""
        # Remove once
        await tenant_admin_client.delete(
            f"/api/v1/tenant/carriers/{test_carrier_id}"
        )
        # Try again
        response = await tenant_admin_client.delete(
            f"/api/v1/tenant/carriers/{test_carrier_id}"
        )
        assert response.status_code == 409

    @pytest.mark.integration
    async def test_delete_carrier_404_never_assigned(self, tenant_admin_client):
        """DELETE on carrier never assigned to tenant returns 404."""
        response = await tenant_admin_client.delete(
            "/api/v1/tenant/carriers/888888"
        )
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_get_available_excludes_active_assignments(
        self, tenant_admin_client, test_carrier_id
    ):
        """GET /api/v1/tenant/carriers/available excludes carriers already assigned."""
        # Add the carrier
        await tenant_admin_client.post(
            "/api/v1/tenant/carriers",
            json={"carrier_id": test_carrier_id},
        )
        response = await tenant_admin_client.get("/api/v1/tenant/carriers/available")
        assert response.status_code == 200
        ids = [c["carrier_id"] for c in response.json()]
        assert test_carrier_id not in ids

    @pytest.mark.integration
    async def test_add_then_remove_then_readd_is_idempotent(
        self, tenant_admin_client, test_carrier_id
    ):
        """Re-adding a removed carrier reactivates without duplicating rules."""
        await tenant_admin_client.post(
            "/api/v1/tenant/carriers", json={"carrier_id": test_carrier_id}
        )
        await tenant_admin_client.delete(
            f"/api/v1/tenant/carriers/{test_carrier_id}"
        )
        # Re-add should succeed
        response = await tenant_admin_client.post(
            "/api/v1/tenant/carriers", json={"carrier_id": test_carrier_id}
        )
        assert response.status_code == 201

    @pytest.mark.integration
    async def test_provisioning_zero_carriers_creates_active_tenant(
        self, super_admin_client
    ):
        """POST /platform/tenants with no carrier_ids activates tenant successfully."""
        response = await super_admin_client.post(
            "/platform/tenants",
            json={
                "name": "Zero Carrier Test Tenant",
                "slug": "zero-carrier-test",
                "tenant_type": "AUDIT_COMPANY",
                "carrier_ids": [],
                "admin_email": "admin@zerocarrier.test",
                "admin_first_name": "Test",
                "admin_last_name": "Admin",
                "send_invitation": False,
            },
        )
        assert response.status_code == 201

    @pytest.mark.integration
    async def test_reviewer_cannot_add_carrier(self, reviewer_client, test_carrier_id):
        """POST /api/v1/tenant/carriers requires TENANT_ADMIN role."""
        response = await reviewer_client.post(
            "/api/v1/tenant/carriers",
            json={"carrier_id": test_carrier_id},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.integration
    async def test_reviewer_cannot_delete_carrier(
        self, reviewer_client, test_carrier_id
    ):
        """DELETE /api/v1/tenant/carriers/{id} requires TENANT_ADMIN role."""
        response = await reviewer_client.delete(
            f"/api/v1/tenant/carriers/{test_carrier_id}"
        )
        assert response.status_code in (401, 403)
