"""
LLMKeyVaultService — symmetric encryption for LLM API keys.

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the cryptography library.
The encryption key is loaded from LLM_KEY_ENCRYPTION_SECRET in environment.

Generate a Fernet key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

CRITICAL RULES (enforced by design):
  - encrypt_key()  → called in LLM config write endpoints only
  - decrypt_key()  → called ONLY inside AInarrativeService and LLM test endpoint
  - last4()        → called in response serialisation (safe — not the full key)
  - The raw plaintext key is NEVER written to any response schema
  - The api_key_enc column is NEVER returned by any endpoint
"""
from __future__ import annotations

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class LLMKeyVaultService:
    """
    Handles symmetric encryption and decryption of LLM API keys.

    Self-hosted providers (Ollama, OpenAI-compatible without auth) may have
    no API key. encrypt_key(None) and decrypt_key(None) are both handled
    gracefully — the vault returns None / empty string respectively.
    """

    def __init__(self) -> None:
        raw_secret: str = get_settings().LLM_KEY_ENCRYPTION_SECRET
        if raw_secret:
            try:
                self._fernet = Fernet(raw_secret.encode())
            except Exception as exc:
                logger.warning(
                    "llm_key_vault.invalid_secret",
                    error=str(exc),
                )
                self._fernet = None
        else:
            # No secret configured — encryption unavailable.
            # The platform can still function without LLM config.
            self._fernet = None

    def encrypt_key(self, raw_key: str | None) -> str | None:
        """
        Encrypts a plaintext API key.
        Returns the Fernet token as a UTF-8 string, or None if raw_key is None/empty.
        Raises RuntimeError if encryption is unavailable (no secret configured).
        """
        if not raw_key:
            return None

        if self._fernet is None:
            raise RuntimeError(
                "LLM_KEY_ENCRYPTION_SECRET is not configured. "
                "Cannot encrypt API keys. Set this environment variable "
                "before configuring LLM providers."
            )

        encrypted: bytes = self._fernet.encrypt(raw_key.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt_key(self, encrypted_key: str | None) -> str | None:
        """
        Decrypts a Fernet-encrypted API key.
        Returns the plaintext key, or None if encrypted_key is None/empty.
        Raises ValueError if the token is invalid (tampered or wrong key).

        MUST only be called from AInarrativeService and the test-connection endpoint.
        """
        if not encrypted_key:
            return None

        if self._fernet is None:
            raise RuntimeError(
                "LLM_KEY_ENCRYPTION_SECRET is not configured. "
                "Cannot decrypt stored API keys."
            )

        try:
            decrypted: bytes = self._fernet.decrypt(encrypted_key.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(
                "Failed to decrypt LLM API key. "
                "The key may have been encrypted with a different secret."
            ) from exc

    @staticmethod
    def last4(raw_key: str | None) -> str | None:
        """
        Returns the last 4 characters of a plaintext key for display-only purposes.
        Safe to include in API responses — not the full key.
        Returns None if raw_key is None or shorter than 4 characters.
        """
        if not raw_key or len(raw_key) < 4:
            return None
        return raw_key[-4:]

    def is_configured(self) -> bool:
        """Returns True if the vault has a working encryption key."""
        return self._fernet is not None


# Module-level singleton — initialised once per process.
llm_key_vault = LLMKeyVaultService()
