"""
Unit tests for LLMClientFactory.

Tests that each provider creates the correct client type,
and that invalid providers raise ValueError.
No actual API calls are made.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.llm_client_factory import (
    LLMClientFactory,
    AnthropicClient,
    OpenAIClient,
    AzureOpenAIClient,
    GoogleClient,
    OllamaClient,
    OpenAICompatibleClient,
    SUPPORTED_PROVIDERS,
)


class TestLLMClientFactory:
    def test_anthropic_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="anthropic",
            model_name="claude-sonnet-4-6",
            api_key="sk-ant-test",
            api_base_url=None,
        )
        assert isinstance(client, AnthropicClient)

    def test_openai_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="openai",
            model_name="gpt-4o",
            api_key="sk-openai-test",
            api_base_url=None,
        )
        assert isinstance(client, OpenAIClient)

    def test_azure_openai_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="azure_openai",
            model_name="gpt-4o",
            api_key="azure-key",
            api_base_url="https://resource.openai.azure.com/",
        )
        assert isinstance(client, AzureOpenAIClient)

    def test_google_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="google",
            model_name="gemini-1.5-flash",
            api_key="google-key",
            api_base_url=None,
        )
        assert isinstance(client, GoogleClient)

    def test_ollama_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="ollama",
            model_name="llama3",
            api_key=None,  # No key for Ollama
            api_base_url="http://localhost:11434",
        )
        assert isinstance(client, OllamaClient)

    def test_ollama_no_api_key_no_error(self):
        """Self-hosted providers must NOT raise if api_key is None."""
        client = LLMClientFactory.create(
            provider_name="ollama",
            model_name="llama3",
            api_key=None,
            api_base_url="http://localhost:11434",
        )
        assert isinstance(client, OllamaClient)

    def test_openai_compatible_creates_correct_client(self):
        client = LLMClientFactory.create(
            provider_name="openai_compatible",
            model_name="local-model",
            api_key=None,
            api_base_url="http://localhost:1234/v1",
        )
        assert isinstance(client, OpenAICompatibleClient)

    def test_unsupported_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported"):
            LLMClientFactory.create(
                provider_name="langchain",  # not supported
                model_name="some-model",
                api_key=None,
                api_base_url=None,
            )

    def test_anthropic_without_api_key_raises(self):
        with pytest.raises(ValueError, match="API key"):
            LLMClientFactory.create(
                provider_name="anthropic",
                model_name="claude-sonnet-4-6",
                api_key=None,
                api_base_url=None,
            )

    def test_azure_without_base_url_raises(self):
        with pytest.raises(ValueError, match="api_base_url"):
            LLMClientFactory.create(
                provider_name="azure_openai",
                model_name="gpt-4o",
                api_key="some-key",
                api_base_url=None,
            )

    def test_openai_compatible_without_base_url_raises(self):
        with pytest.raises(ValueError, match="api_base_url"):
            LLMClientFactory.create(
                provider_name="openai_compatible",
                model_name="local-model",
                api_key=None,
                api_base_url=None,
            )

    def test_all_supported_providers_are_handled(self):
        """Every provider in SUPPORTED_PROVIDERS must be handleable without ValueError
        when given valid parameters."""
        valid_params = {
            "anthropic":        dict(api_key="sk", api_base_url=None, model_name="claude-sonnet-4-6"),
            "openai":           dict(api_key="sk", api_base_url=None, model_name="gpt-4o"),
            "azure_openai":     dict(api_key="sk", api_base_url="https://x.openai.azure.com/", model_name="gpt-4o"),
            "google":           dict(api_key="sk", api_base_url=None, model_name="gemini-1.5-flash"),
            "ollama":           dict(api_key=None, api_base_url="http://localhost:11434", model_name="llama3"),
            "openai_compatible": dict(api_key=None, api_base_url="http://localhost:1234/v1", model_name="x"),
        }
        for provider in SUPPORTED_PROVIDERS:
            params = valid_params[provider]
            client = LLMClientFactory.create(provider_name=provider, **params)
            assert isinstance(client, object)
