"""
Phase 4 — Integration tests: Field Maps API (Tab 2).
Tests GET/PUT/DELETE /api/v1/admin/field-maps.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text


class TestFieldMapsAPI:
    async def test_tenant_admin_can_list_field_maps(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.get(
            f"/api/v1/admin/field-maps?carrier_id={seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_bulk_upsert_creates_field_maps(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json={
                "mappings": [
                    {"source_field": "Policy Number", "target_column": "policy_number"},
                    {"source_field": "Insured Name", "target_column": "insured_name"},
                    {"source_field": "Earned Prem.", "target_column": "actual_premium", "file_type": "xlsx"},
                ]
            },
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        source_fields = {m["source_field"] for m in data}
        assert "Policy Number" in source_fields
        assert "Insured Name" in source_fields

    async def test_bulk_upsert_is_idempotent(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        payload = {
            "mappings": [
                {"source_field": "Policy #", "target_column": "policy_number"},
            ]
        }
        r1 = await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json=payload,
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        r2 = await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json=payload,
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

    async def test_delete_field_map_sets_inactive(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        seeded_carrier_id, async_session
    ):
        # Create a mapping
        create_res = await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json={"mappings": [{"source_field": "ToRemove", "target_column": "policy_number"}]},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        map_id = create_res.json()[0]["map_id"]

        # Delete
        del_res = await test_client.delete(
            f"/api/v1/admin/field-maps/{map_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert del_res.status_code == 204

        # Verify is_active = FALSE
        result = await async_session.execute(
            text("SELECT is_active FROM ingestion_field_maps WHERE map_id = :mid"),
            {"mid": map_id},
        )
        assert result.scalar() is False

    async def test_auditor_cannot_manage_field_maps(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id
    ):
        response = await test_client.get(
            f"/api/v1/admin/field-maps?carrier_id={seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 403

    async def test_field_map_has_file_type_when_specified(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        await test_client.put(
            f"/api/v1/admin/field-maps/{seeded_carrier_id}",
            json={"mappings": [{"source_field": "CheckDate", "target_column": "as_of_date", "file_type": "csv"}]},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        list_res = await test_client.get(
            f"/api/v1/admin/field-maps?carrier_id={seeded_carrier_id}&file_type=csv",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        data = list_res.json()
        csv_maps = [m for m in data if m["source_field"] == "CheckDate"]
        assert len(csv_maps) >= 1
        assert csv_maps[0]["file_type"] == "csv"
