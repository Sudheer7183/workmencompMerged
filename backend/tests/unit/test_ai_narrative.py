"""
Unit tests for AINarrativeService — 6 cases.
Tests the deterministic fallback and API response parsing.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_narrative_service import AINarrativeService, AuditNarrativeContext


svc = AINarrativeService()


def _ctx(**kwargs) -> AuditNarrativeContext:
    defaults = dict(
        policy_number="TEST-001",
        insured_name="Acme Corp",
        carrier_name="Demo Carrier",
        risk_level="High",
        variance_amount=Decimal("15000"),
        variance_pct=Decimal("0.15"),
        missing_payroll_count=2,
        zero_payroll_count=0,
    )
    defaults.update(kwargs)
    return AuditNarrativeContext(**defaults)


# ============================================================================
# 1. Deterministic fallback returns a non-empty string
# ============================================================================
def test_fallback_returns_non_empty():
    ctx = _ctx()
    result = svc._deterministic_fallback(ctx)
    assert isinstance(result, str)
    assert len(result) > 0


# ============================================================================
# 2. Fallback includes policy number
# ============================================================================
def test_fallback_includes_policy_number():
    ctx = _ctx(policy_number="POL-12345")
    result = svc._deterministic_fallback(ctx)
    assert "POL-12345" in result


# ============================================================================
# 3. Fallback includes risk level
# ============================================================================
def test_fallback_includes_risk_level():
    ctx = _ctx(risk_level="High")
    result = svc._deterministic_fallback(ctx)
    assert "High" in result


# ============================================================================
# 4. Fallback with all-None inputs does NOT raise
# ============================================================================
def test_fallback_all_none_does_not_raise():
    ctx = AuditNarrativeContext()
    result = svc._deterministic_fallback(ctx)
    assert isinstance(result, str)
    assert len(result) > 0


# ============================================================================
# 5. generate() falls back when API raises httpx exception
# ============================================================================
@pytest.mark.asyncio
async def test_generate_falls_back_on_http_error():
    import httpx
    ctx = _ctx()

    with patch("app.services.ai_narrative_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        result = await svc.generate(ctx)

    assert isinstance(result, str)
    assert len(result) > 0  # Fallback was called


# ============================================================================
# 6. generate() returns API text on success
# ============================================================================
@pytest.mark.asyncio
async def test_generate_returns_api_text_on_success():
    ctx = _ctx()
    api_narrative = "This is an AI-generated audit narrative."

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": api_narrative}]
    }

    with patch("app.services.ai_narrative_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await svc.generate(ctx)

    assert result == api_narrative
