"""
Unit tests for LLMKeyVaultService.

These tests use a generated Fernet key — no real API keys.
All tests are synchronous (no async needed for vault service).
"""
from __future__ import annotations

import os
import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def set_fernet_key(monkeypatch):
    """Set a test Fernet key for every test in this module."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("LLM_KEY_ENCRYPTION_SECRET", key)
    yield
    # Force re-initialise the singleton after each test
    import importlib
    import app.services.llm_key_vault_service as mod
    importlib.reload(mod)


def get_vault():
    from app.services.llm_key_vault_service import LLMKeyVaultService
    return LLMKeyVaultService()


class TestLLMKeyVaultService:
    def test_encrypt_returns_non_empty_string(self):
        vault = get_vault()
        result = vault.encrypt_key("sk-test-key-12345")
        assert result is not None
        assert len(result) > 0
        assert result != "sk-test-key-12345"

    def test_decrypt_round_trip(self):
        vault = get_vault()
        original = "sk-test-abc-12345"
        encrypted = vault.encrypt_key(original)
        assert encrypted is not None
        decrypted = vault.decrypt_key(encrypted)
        assert decrypted == original

    def test_encrypt_none_returns_none(self):
        vault = get_vault()
        assert vault.encrypt_key(None) is None

    def test_decrypt_none_returns_none(self):
        vault = get_vault()
        assert vault.decrypt_key(None) is None

    def test_last4_returns_last_4_chars(self):
        assert LLMKeyVaultService.last4("sk-test-12345") == "2345"

    def test_last4_short_key_returns_none(self):
        assert LLMKeyVaultService.last4("abc") is None

    def test_last4_none_returns_none(self):
        assert LLMKeyVaultService.last4(None) is None

    def test_decrypt_invalid_token_raises_value_error(self):
        vault = get_vault()
        with pytest.raises(ValueError, match="decrypt"):
            vault.decrypt_key("not-a-valid-fernet-token")

    def test_no_secret_raises_on_encrypt(self, monkeypatch):
        monkeypatch.setenv("LLM_KEY_ENCRYPTION_SECRET", "")
        from app.services.llm_key_vault_service import LLMKeyVaultService
        vault = LLMKeyVaultService()
        with pytest.raises(RuntimeError, match="LLM_KEY_ENCRYPTION_SECRET"):
            vault.encrypt_key("some-key")

    def test_is_configured_returns_true_with_key(self):
        vault = get_vault()
        assert vault.is_configured() is True

    def test_is_configured_returns_false_without_key(self, monkeypatch):
        monkeypatch.setenv("LLM_KEY_ENCRYPTION_SECRET", "")
        from app.services.llm_key_vault_service import LLMKeyVaultService
        vault = LLMKeyVaultService()
        assert vault.is_configured() is False


# Make last4 accessible for direct test
from app.services.llm_key_vault_service import LLMKeyVaultService
