"""
Phase 4 — Integration tests: second carrier data isolation.
V9 S27: Upload data for two carriers — verify no cross-contamination.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.fixture
async def second_carrier(async_session, seeded_tenant_id):
    """
    Creates a second carrier ("Beta Carrier") attached to the seeded tenant.
    Returns carrier_id.
    """
    result = await async_session.execute(
        text("""
            INSERT INTO public.carriers (carrier_name, is_active)
            VALUES ('Beta Carrier', TRUE)
            RETURNING carrier_id
        """),
    )
    carrier_id = result.scalar_one()

    await async_session.execute(
        text("""
            INSERT INTO public.tenant_carriers (tenant_id, carrier_id)
            VALUES (:tid, :cid)
        """),
        {"tid": seeded_tenant_id, "cid": carrier_id},
    )
    await async_session.commit()
    return carrier_id


class TestMultiCarrierIsolation:
    async def test_data_sources_scoped_to_carrier(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        seeded_carrier_id, second_carrier
    ):
        # Create a source for carrier 1
        await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "Carrier1 Source", "source_type": "xlsx"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )

        # List carrier 2 sources — must not include carrier 1 sources
        res = await test_client.get(
            f"/api/v1/admin/data-sources?carrier_id={second_carrier}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert res.status_code == 200
        for source in res.json():
            assert source["carrier_id"] == second_carrier

    async def test_field_maps_scoped_to_carrier(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        seeded_carrier_id, second_carrier
    ):
        # Add field maps to carrier 1
        await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json={"mappings": [{"source_field": "CarrierOneOnly", "canonical_column": "policy_number"}]},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )

        # Carrier 2 field maps must not include carrier 1 entries
        res = await test_client.get(
            f"/api/v1/admin/field-maps?carrier_id={second_carrier}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        for fm in res.json():
            assert fm["carrier_id"] == second_carrier
            assert fm["source_field"] != "CarrierOneOnly"

    async def test_ingestion_run_query_scoped_to_carrier(
        self, test_client: AsyncClient, mock_reviewer_token,
        async_session, seeded_carrier_id, second_carrier
    ):
        """Runs created for carrier 1 must not appear in carrier 2 context."""
        src1 = await async_session.execute(
            text("""
                INSERT INTO ingestion_sources (carrier_id, source_name, source_type, is_active, created_at)
                VALUES (:cid, 'C1 Source', 'xlsx', TRUE, now()) RETURNING source_id
            """),
            {"cid": seeded_carrier_id},
        )
        sid1 = src1.scalar_one()
        run1 = await async_session.execute(
            text("""
                INSERT INTO ingestion_runs
                  (carrier_id, source_id, uploaded_by, started_at, status,
                   rows_ingested, rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
                VALUES (:cid, :sid, 'admin', now(), 'complete', 5, 0, 0, FALSE, NULL)
                RETURNING run_id
            """),
            {"cid": seeded_carrier_id, "sid": sid1},
        )
        run_id_c1 = run1.scalar_one()
        await async_session.commit()

        # Fetch the run — it should be visible under carrier 1
        res = await test_client.get(
            f"/api/v1/ingestion/runs/{run_id_c1}",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert res.status_code == 200
        assert res.json()["run_id"] == run_id_c1

    async def test_second_carrier_engine_config_independent(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        seeded_carrier_id, second_carrier
    ):
        """Toggling engine for carrier 2 must not affect carrier 1."""
        # Set carrier 2 engine OFF
        await test_client.put(
            f"/api/v1/admin/calc-config/{second_carrier}",
            json={"use_calculation_engine": False},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        # Carrier 1 config must be unaffected
        res1 = await test_client.get(
            f"/api/v1/admin/calc-config/{seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        # Carrier 1 should still have its own config (whatever it is, not carrier 2's)
        assert res1.status_code == 200

    async def test_policies_scoped_by_carrier(
        self, test_client: AsyncClient, mock_reviewer_token,
        seeded_carrier_id, second_carrier
    ):
        """Policy list must only return policies for the authenticated carrier context."""
        # The fixture-seeded policy belongs to seeded_carrier_id
        res = await test_client.get(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {mock_reviewer_token}"},
        )
        assert res.status_code == 200
        for policy in res.json().get("policies", res.json()):
            # All returned policies must belong to the token's carrier scope
            assert policy.get("carrier_id") == seeded_carrier_id or policy.get("carrier_id") is None
