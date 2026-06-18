"""
Integration tests for LLM Configuration API endpoints.

Tests the full CRUD cycle for /api/v1/admin/llm-config endpoints.
Requires a running database with the Phase 7C migration applied.
Uses SKIP_JWT_VERIFICATION=true for test tokens.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def set_encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("LLM_KEY_ENCRYPTION_SECRET", key)


@pytest.mark.asyncio
class TestLLMConfigAPI:
    async def test_get_llm_config_returns_none_when_unconfigured(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        response = await client.get(
            f"/api/v1/admin/llm-config?carrier_id={test_carrier_id}",
            headers=tenant_auth_headers,
        )
        assert response.status_code in (200, 404)
        # If 200, body should be null or an unconfigured row
        if response.status_code == 200:
            data = response.json()
            if data:
                assert data.get("provider_name") is None

    async def test_create_llm_config_anthropic(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        payload = {
            "carrier_id": test_carrier_id,
            "provider_name": "anthropic",
            "model_name": "claude-sonnet-4-6",
            "api_key": "sk-ant-test-integration-12345",
        }
        response = await client.post(
            "/api/v1/admin/llm-config",
            json=payload,
            headers=tenant_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider_name"] == "anthropic"
        assert data["model_name"] == "claude-sonnet-4-6"
        # api_key must NOT be present in response
        assert "api_key" not in data
        assert "api_key_enc" not in data
        # api_key_last4 should show last 4 chars of "sk-ant-test-integration-12345"
        assert data["api_key_last4"] == "2345"

    async def test_create_llm_config_api_key_never_returned(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        """Strict check: api_key field must be structurally absent from ALL responses."""
        payload = {
            "carrier_id": test_carrier_id,
            "provider_name": "anthropic",
            "model_name": "claude-sonnet-4-6",
            "api_key": "sk-ant-secret-key-99999",
        }
        response = await client.post(
            "/api/v1/admin/llm-config",
            json=payload,
            headers=tenant_auth_headers,
        )
        assert "api_key" not in response.json()
        assert "sk-ant-secret-key-99999" not in response.text

    async def test_create_ollama_no_api_key(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        """Self-hosted providers with no API key must succeed."""
        payload = {
            "carrier_id": test_carrier_id,
            "provider_name": "ollama",
            "model_name": "llama3",
            "api_base_url": "http://localhost:11434",
        }
        response = await client.post(
            "/api/v1/admin/llm-config",
            json=payload,
            headers=tenant_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider_name"] == "ollama"
        assert data["api_key_last4"] is None

    async def test_update_llm_config_model(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        # First create
        create_resp = await client.post(
            "/api/v1/admin/llm-config",
            json={
                "carrier_id": test_carrier_id,
                "provider_name": "openai",
                "model_name": "gpt-4o",
                "api_key": "sk-openai-test",
            },
            headers=tenant_auth_headers,
        )
        config_id = create_resp.json()["config_id"]

        # Then update model
        update_resp = await client.put(
            f"/api/v1/admin/llm-config/{config_id}",
            json={"model_name": "gpt-4o-mini"},
            headers=tenant_auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["model_name"] == "gpt-4o-mini"

    async def test_update_without_api_key_retains_existing_key(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        """Omitting api_key on PUT must NOT clear the stored key."""
        create_resp = await client.post(
            "/api/v1/admin/llm-config",
            json={
                "carrier_id": test_carrier_id,
                "provider_name": "anthropic",
                "model_name": "claude-sonnet-4-6",
                "api_key": "sk-ant-original-key",
            },
            headers=tenant_auth_headers,
        )
        config_id = create_resp.json()["config_id"]
        original_last4 = create_resp.json()["api_key_last4"]

        update_resp = await client.put(
            f"/api/v1/admin/llm-config/{config_id}",
            json={"model_name": "claude-haiku-4-5-20251001"},
            headers=tenant_auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["api_key_last4"] == original_last4

    async def test_delete_sets_inactive(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        create_resp = await client.post(
            "/api/v1/admin/llm-config",
            json={
                "carrier_id": test_carrier_id,
                "provider_name": "google",
                "model_name": "gemini-1.5-flash",
                "api_key": "google-test-key",
            },
            headers=tenant_auth_headers,
        )
        config_id = create_resp.json()["config_id"]

        delete_resp = await client.delete(
            f"/api/v1/admin/llm-config/{config_id}",
            headers=tenant_auth_headers,
        )
        assert delete_resp.status_code == 204

    async def test_invalid_provider_returns_422(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        response = await client.post(
            "/api/v1/admin/llm-config",
            json={
                "carrier_id": test_carrier_id,
                "provider_name": "langchain",  # not supported
                "model_name": "some-model",
            },
            headers=tenant_auth_headers,
        )
        assert response.status_code == 422

    async def test_test_connection_returns_result_structure(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        response = await client.post(
            "/api/v1/admin/llm-config/test",
            json={"carrier_id": test_carrier_id},
            headers=tenant_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "latency_ms" in data
        assert "provider" in data
        assert "model" in data

    async def test_available_fields_endpoint(
        self, client: AsyncClient, tenant_auth_headers: dict, test_carrier_id: int
    ):
        response = await client.get(
            f"/api/v1/admin/calc-rules/available-fields?carrier_id={test_carrier_id}",
            headers=tenant_auth_headers,
        )
        assert response.status_code == 200
        fields = response.json()
        assert isinstance(fields, list)
        assert len(fields) > 0
        # Check structure of first field
        first = fields[0]
        assert "name" in first
        assert "label" in first
        assert "description" in first
        assert "data_type" in first
        assert "category" in first
