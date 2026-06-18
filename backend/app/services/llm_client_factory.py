"""
LLM provider client implementations for Phase 7C.

Architecture:
  - BaseLLMClient: abstract interface — all providers implement generate()
  - Six concrete implementations: Anthropic, OpenAI, Azure OpenAI, Google, Ollama, OpenAI-compatible
  - LLMClientFactory: creates the correct client from provider_name

RULES:
  - No LangChain. No LangGraph.
  - api_key may be None for self-hosted providers — handle gracefully.
  - All clients implement the same async generate(prompt) → str interface.
  - Timeout is always honoured — no hanging requests.
  - All exceptions must be caught by the caller (AInarrativeService).
"""
from __future__ import annotations

import abc
import time
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Default completion timeout in seconds
_DEFAULT_TIMEOUT: float = 30.0

# Ollama runs locally — model loading on first call can take 60-120s
_OLLAMA_TIMEOUT: float = 120.0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseLLMClient(abc.ABC):
    """
    Abstract LLM client interface.

    All provider implementations must inherit from this class and implement
    the generate() method. The method may raise any exception — callers
    (AInarrativeService) are responsible for catching and falling back.
    """

    @abc.abstractmethod
    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        """
        Sends prompt to the LLM and returns the text response.
        Raises on any error (timeout, auth failure, etc.).
        """
        ...

    async def test_connection(self) -> tuple[bool, int, str | None]:
        """
        Makes a minimal test call ('Say: ok') to verify the configuration.
        Returns (success, latency_ms, error_message).
        """
        start = time.monotonic()
        try:
            await self.generate("Say: ok", max_tokens=10)
            latency_ms = int((time.monotonic() - start) * 1000)
            return True, latency_ms, None
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return False, latency_ms, str(exc)


# ---------------------------------------------------------------------------
# Anthropic (claude-*)
# ---------------------------------------------------------------------------

class AnthropicClient(BaseLLMClient):
    """
    Anthropic API client using the anthropic SDK.
    Falls back to raw httpx if anthropic SDK is unavailable.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return str(content[0]["text"])
            raise ValueError("Anthropic returned empty content")


# ---------------------------------------------------------------------------
# OpenAI (gpt-*)
# ---------------------------------------------------------------------------

class OpenAIClient(BaseLLMClient):
    """
    OpenAI Chat Completions API client.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------

class AzureOpenAIClient(BaseLLMClient):
    """
    Azure OpenAI Service client.
    api_base_url must be the Azure endpoint (e.g. https://{resource}.openai.azure.com/).
    model is the deployment name.
    """

    _API_VERSION = "2024-02-01"

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base_url: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = api_base_url.rstrip("/")
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        url = (
            f"{self._base_url}/openai/deployments/{self._model}"
            f"/chat/completions?api-version={self._API_VERSION}"
        )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                headers={
                    "api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Google Generative AI (Gemini)
# ---------------------------------------------------------------------------

class GoogleClient(BaseLLMClient):
    """
    Google Generative AI (Gemini) client.
    Uses the REST API directly to avoid import-time dependency on the SDK.
    """

    _BASE_URL = "https://generativelanguage.googleapis.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        url = f"{self._BASE_URL}/models/{self._model}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return str(parts[0].get("text", ""))
            raise ValueError("Google returned empty candidates")


# ---------------------------------------------------------------------------
# Ollama (self-hosted, no API key required)
# ---------------------------------------------------------------------------

class OllamaClient(BaseLLMClient):
    """
    Ollama self-hosted LLM client.
    api_key is not required and is ignored if provided.
    api_base_url defaults to http://localhost:11434.
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        model: str = "llama3",
        api_base_url: Optional[str] = None,
        timeout: float = _OLLAMA_TIMEOUT,
    ) -> None:
        self._model = model
        self._base_url = (api_base_url or self._DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))


# ---------------------------------------------------------------------------
# OpenAI-compatible (generic — covers LocalAI, vLLM, LM Studio, etc.)
# ---------------------------------------------------------------------------

class OpenAICompatibleClient(BaseLLMClient):
    """
    Generic OpenAI-compatible client for self-hosted providers.
    api_key is optional — set to "none" or empty for local servers that skip auth.
    api_base_url must point to the server root (e.g. http://localhost:1234/v1).
    """

    def __init__(
        self,
        model: str,
        api_base_url: str,
        api_key: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model
        self._base_url = api_base_url.rstrip("/")
        self._api_key = api_key or "none"
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])



# ---------------------------------------------------------------------------
# Groq (groq.com — OpenAI-compatible, ultra-fast inference)
# ---------------------------------------------------------------------------

class GroqClient(BaseLLMClient):
    """
    Groq API client.
    Groq exposes an OpenAI-compatible Chat Completions endpoint at
    https://api.groq.com/openai/v1 — no extra SDK needed.
    API key is required (generate at https://console.groq.com/keys).
    """

    _BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, *, max_tokens: int = 800) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({
    "anthropic",
    "openai",
    "azure_openai",
    "google",
    "groq",
    "ollama",
    "openai_compatible",
})


class LLMClientFactory:
    """
    Creates the correct BaseLLMClient subclass from a provider_name string.

    Raises ValueError for unsupported provider names — the caller should
    fall back to the platform default.
    """

    @staticmethod
    def create(
        *,
        provider_name: str,
        model_name: str,
        api_key: str | None,
        api_base_url: str | None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> BaseLLMClient:
        """
        Factory method.

        Parameters
        ----------
        provider_name : str
            One of the SUPPORTED_PROVIDERS values.
        model_name : str
            The model identifier for the chosen provider.
        api_key : str | None
            Decrypted (plaintext) API key. May be None for self-hosted providers.
        api_base_url : str | None
            Required for azure_openai, ollama, and openai_compatible.
        timeout : float
            Request timeout in seconds.

        Returns
        -------
        BaseLLMClient
            An initialised client ready for use.

        Raises
        ------
        ValueError
            If provider_name is not in SUPPORTED_PROVIDERS, or if required
            parameters for the chosen provider are missing.
        """
        pname = provider_name.lower().strip()

        if pname not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider: '{provider_name}'. "
                f"Supported: {sorted(SUPPORTED_PROVIDERS)}"
            )

        if pname == "anthropic":
            if not api_key:
                raise ValueError("Anthropic requires an API key.")
            return AnthropicClient(api_key=api_key, model=model_name, timeout=timeout)

        if pname == "openai":
            if not api_key:
                raise ValueError("OpenAI requires an API key.")
            return OpenAIClient(api_key=api_key, model=model_name, timeout=timeout)

        if pname == "azure_openai":
            if not api_key:
                raise ValueError("Azure OpenAI requires an API key.")
            if not api_base_url:
                raise ValueError("Azure OpenAI requires api_base_url (the Azure endpoint).")
            return AzureOpenAIClient(
                api_key=api_key,
                model=model_name,
                api_base_url=api_base_url,
                timeout=timeout,
            )

        if pname == "google":
            if not api_key:
                raise ValueError("Google Generative AI requires an API key.")
            return GoogleClient(api_key=api_key, model=model_name, timeout=timeout)

        if pname == "groq":
            if not api_key:
                raise ValueError("Groq requires an API key.")
            return GroqClient(api_key=api_key, model=model_name, timeout=timeout)

        if pname == "ollama":
            # Ollama needs a longer timeout — local model loading can take 60-120s
            ollama_timeout = max(timeout, _OLLAMA_TIMEOUT)
            return OllamaClient(
                model=model_name,
                api_base_url=api_base_url,
                timeout=ollama_timeout,
            )

        if pname == "openai_compatible":
            if not api_base_url:
                raise ValueError("openai_compatible requires api_base_url.")
            return OpenAICompatibleClient(
                model=model_name,
                api_base_url=api_base_url,
                api_key=api_key,
                timeout=timeout,
            )

        # Should never reach here due to the membership check above
        raise ValueError(f"Unhandled provider: {provider_name}")