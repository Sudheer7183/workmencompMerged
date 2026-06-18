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
    ctx = _ctx()
    # Phase 7C: generate() requires carrier_id, db, schema_name keyword args.
    # Patch LLMClientFactory so the carrier LLM lookup raises — service must
    # fall through to the deterministic fallback and return a NarrativeResult.
    from app.services import ai_narrative_service as svc_module

    mock_db = AsyncMock()
    # Simulate DB returning no carrier LLM config row
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_cursor)

    with patch.object(svc_module, "LLMClientFactory") as mock_factory:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("simulated LLM timeout"))
        mock_factory.create.return_value = mock_client

        result = await svc.generate(
            ctx,
            carrier_id=1,
            db=mock_db,
            schema_name="tenant_demo",
        )

    # generate() always returns a NarrativeResult — never raises
    assert hasattr(result, "text"), "Expected NarrativeResult with .text attribute"
    assert isinstance(result.text, str)
    assert len(result.text) > 0  # Fallback text was populated


# ============================================================================
# 6. generate() returns API text on success
# ============================================================================
@pytest.mark.asyncio
async def test_generate_returns_api_text_on_success():
    ctx = _ctx()
    api_narrative = "This is an AI-generated audit narrative."
    from app.services import ai_narrative_service as svc_module

    mock_db = AsyncMock()
    # Simulate DB returning a carrier LLM config row:
    # (provider_name, model_name, api_key_enc, api_base_url)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("anthropic", "claude-sonnet-4-6", None, None)
    mock_db.execute = AsyncMock(return_value=mock_cursor)

    with patch.object(svc_module, "LLMClientFactory") as mock_factory:
        mock_client = AsyncMock()
        # The carrier LLM client.generate() returns the narrative string
        mock_client.generate = AsyncMock(return_value=api_narrative)
        mock_factory.create.return_value = mock_client

        narr = await svc.generate(
            ctx,
            carrier_id=1,
            db=mock_db,
            schema_name="tenant_demo",
        )

    # generate() returns a NarrativeResult; .text holds the LLM string
    assert hasattr(narr, "text"), "Expected NarrativeResult with .text attribute"
    assert narr.text == api_narrative
    assert narr.is_fallback is False