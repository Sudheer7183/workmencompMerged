"""
Phase 4 — Integration tests: Data Sources API (Tab 1).
Tests GET/POST/PUT/DELETE /api/v1/admin/data-sources and POST .../test.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text


class TestDataSourcesCRUD:
    async def test_tenant_admin_can_list_sources(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.get(
            f"/api/v1/admin/data-sources?carrier_id={seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_auditor_cannot_list_sources(
        self, test_client: AsyncClient, mock_auditor_token, seeded_carrier_id
    ):
        response = await test_client.get(
            f"/api/v1/admin/data-sources?carrier_id={seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_auditor_token}"},
        )
        assert response.status_code == 403

    async def test_create_data_source(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.post(
            "/api/v1/admin/data-sources",
            json={
                "carrier_id": seeded_carrier_id,
                "source_name": "WC Payroll Feed",
                "source_type": "xlsx",
                "anchor_string": "Policy Number",
            },
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_name"] == "WC Payroll Feed"
        assert data["source_type"] == "xlsx"
        assert data["is_active"] is True

    async def test_create_csv_source(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.post(
            "/api/v1/admin/data-sources",
            json={
                "carrier_id": seeded_carrier_id,
                "source_name": "CSV Feed",
                "source_type": "csv",
                "delimiter": ",",
            },
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 201
        assert response.json()["source_type"] == "csv"

    async def test_invalid_source_type_returns_422(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        response = await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "Bad", "source_type": "pdf"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 422

    async def test_update_data_source(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        # Create first
        create_res = await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "Original", "source_type": "xlsx"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        source_id = create_res.json()["source_id"]

        # Update
        update_res = await test_client.put(
            f"/api/v1/admin/data-sources/{source_id}",
            json={"source_name": "Updated Name"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["source_name"] == "Updated Name"

    async def test_delete_sets_is_active_false(
        self, test_client: AsyncClient, mock_tenant_admin_token,
        seeded_carrier_id, async_session
    ):
        create_res = await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "ToDelete", "source_type": "xlsx"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        source_id = create_res.json()["source_id"]

        del_res = await test_client.delete(
            f"/api/v1/admin/data-sources/{source_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert del_res.status_code == 204

        # Verify is_active = FALSE in DB
        result = await async_session.execute(
            text("SELECT is_active FROM ingestion_sources WHERE source_id = :sid"),
            {"sid": source_id},
        )
        assert result.scalar() is False

    async def test_deleted_source_not_in_list(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        create_res = await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "WillVanish", "source_type": "csv"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        source_id = create_res.json()["source_id"]
        await test_client.delete(
            f"/api/v1/admin/data-sources/{source_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )

        list_res = await test_client.get(
            f"/api/v1/admin/data-sources?carrier_id={seeded_carrier_id}",
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        ids = [s["source_id"] for s in list_res.json()]
        assert source_id not in ids

    async def test_test_endpoint_detects_xlsx_columns(
        self, test_client: AsyncClient, mock_tenant_admin_token, seeded_carrier_id
    ):
        create_res = await test_client.post(
            "/api/v1/admin/data-sources",
            json={"carrier_id": seeded_carrier_id, "source_name": "XLSX Test", "source_type": "xlsx"},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        source_id = create_res.json()["source_id"]

        # Create a minimal XLSX in memory
        import io, openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Policy Number", "Insured Name", "Est Premium", "Actual Premium"])
        ws.append(["POL-001", "Acme Corp", 10000, 9500])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        response = await test_client.post(
            f"/api/v1/admin/data-sources/{source_id}/test",
            files={"file": ("test.xlsx", buf.read(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"Authorization": f"Bearer {mock_tenant_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "detected_columns" in data
        assert "Policy Number" in data["detected_columns"]
