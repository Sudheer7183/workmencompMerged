"""
AInarrativeService — Phase 7C update.

LLM provider resolution chain (per V9 Phase 7C spec):
  1. Query carrier_llm_config WHERE carrier_id = X AND is_active = TRUE.
  2. If a row exists with provider_name set: decrypt key, instantiate client, call model.
  3. If no row / provider_name is NULL: fall back to platform ANTHROPIC_API_KEY env var.
  4. On any exception from the LLM call: fall back to deterministic f-string template.

CRITICAL: carriers.ai_narrative_enabled is NOT referenced here (Phase 7C rule 12).
The flag column is retained in public.carriers for historical records only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.llm_client_factory import LLMClientFactory
from app.services.llm_key_vault_service import llm_key_vault

logger = structlog.get_logger(__name__)


class AuditNarrativeContext(BaseModel):
    """Context passed to the AI narrative generator."""

    policy_number: Optional[str] = None
    insured_name: Optional[str] = None
    carrier_name: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    risk_level: Optional[str] = None
    variance_amount: Optional[Decimal] = None
    variance_pct: Optional[Decimal] = None
    reported_over_under: Optional[Decimal] = None
    missing_payroll_count: Optional[int] = None
    zero_payroll_count: Optional[int] = None
    submission_rate: Optional[Decimal] = None


@dataclass
class NarrativeResult:
    """Returned by AINarrativeService.generate() — carries metadata alongside text."""

    text: str
    is_fallback: bool
    provider: Optional[str] = None
    generated_at: Optional[datetime] = None


class AINarrativeService:
    """
    Generates a plain-English audit narrative using the configured LLM provider.

    Provider resolution (Phase 7C):
      1. Carrier-scoped config in carrier_llm_config (tenant schema).
      2. Platform-level ANTHROPIC_API_KEY environment variable.
      3. Deterministic template (is_fallback=True).

    carriers.ai_narrative_enabled is NOT consulted — removed per Phase 7C rule 12.
    """

    async def generate(
        self,
        ctx: AuditNarrativeContext,
        *,
        carrier_id: int,
        db: AsyncSession,
        schema_name: str,
    ) -> NarrativeResult:
        """
        Generates a narrative using the carrier-scoped or platform LLM config.
        NEVER raises — always returns a NarrativeResult (fallback if needed).
        """
        prompt = self._build_prompt(ctx)

        # ── Step 1: Try carrier-scoped LLM config ───────────────────────────
        try:
            result = await db.execute(
                text(
                    f"SELECT provider_name, model_name, api_key_enc, api_base_url "
                    f"FROM {schema_name}.carrier_llm_config "
                    f"WHERE carrier_id = :cid AND is_active = TRUE"
                ),
                {"cid": carrier_id},
            )
            row = result.fetchone()

            if row and row[0]:  # provider_name is set
                provider_name, model_name, api_key_enc, api_base_url = row
                api_key = llm_key_vault.decrypt_key(api_key_enc)

                client = LLMClientFactory.create(
                    provider_name=provider_name,
                    model_name=model_name or "",
                    api_key=api_key,
                    api_base_url=api_base_url,
                )
                narrative_text = await client.generate(prompt)
                logger.info(
                    "ai_narrative.generated",
                    policy=ctx.policy_number,
                    provider=provider_name,
                )
                return NarrativeResult(
                    text=narrative_text,
                    is_fallback=False,
                    provider=provider_name,
                    generated_at=datetime.now(timezone.utc),
                )

        except Exception as exc:
            logger.warning(
                "ai_narrative.carrier_llm_failed",
                policy=ctx.policy_number,
                error=str(exc),
            )

        # ── Step 2: Platform-level ANTHROPIC_API_KEY fallback ───────────────
        try:
            settings = get_settings()
            if settings.ANTHROPIC_API_KEY:
                from app.services.llm_client_factory import AnthropicClient
                client = AnthropicClient(
                    api_key=settings.ANTHROPIC_API_KEY,
                    model=settings.ANTHROPIC_MODEL,
                    timeout=settings.ANTHROPIC_TIMEOUT_SECONDS,
                )
                narrative_text = await client.generate(
                    prompt, max_tokens=settings.ANTHROPIC_MAX_TOKENS
                )
                logger.info(
                    "ai_narrative.generated",
                    policy=ctx.policy_number,
                    provider="anthropic_platform",
                )
                return NarrativeResult(
                    text=narrative_text,
                    is_fallback=False,
                    provider="anthropic",
                    generated_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            logger.warning(
                "ai_narrative.platform_anthropic_failed",
                policy=ctx.policy_number,
                error=str(exc),
            )

        # ── Step 3: Deterministic template ──────────────────────────────────
        return NarrativeResult(
            text=self._deterministic_fallback(ctx),
            is_fallback=True,
            provider=None,
            generated_at=datetime.now(timezone.utc),
        )

    def _deterministic_fallback(self, ctx: AuditNarrativeContext) -> str:
        """
        Template-based narrative. Uses only string formatting — no external calls.
        MUST NEVER RAISE an exception under any input, including all-None inputs.
        """
        try:
            policy = ctx.policy_number or "Unknown"
            insured = ctx.insured_name or "Unknown Insured"
            risk = ctx.risk_level or "Not Assessed"

            if ctx.variance_amount is not None:
                try:
                    amt_str = f"${float(ctx.variance_amount):,.2f}"
                except Exception:
                    amt_str = str(ctx.variance_amount)
            else:
                amt_str = "N/A"

            if ctx.variance_pct is not None:
                try:
                    pct_str = f"{float(ctx.variance_pct) * 100:.1f}%"
                except Exception:
                    pct_str = str(ctx.variance_pct)
            else:
                pct_str = "N/A"

            missing = ctx.missing_payroll_count or 0
            zero = ctx.zero_payroll_count or 0

            missing_note = (
                f" {missing} missing payroll period(s) were identified."
                if missing > 0
                else " No missing payroll periods were detected."
            )
            zero_note = (
                f" {zero} zero-wage payroll submission(s) were recorded."
                if zero > 0
                else ""
            )

            return (
                f"Audit Summary for Policy {policy} — {insured}. "
                f"Risk Level: {risk}. "
                f"Premium variance: {amt_str} ({pct_str} of estimated premium)."
                f"{missing_note}"
                f"{zero_note} "
                "This narrative was generated using a template because the AI service was unavailable."
            )
        except Exception:
            return (
                "Narrative generation is temporarily unavailable. "
                "Please review the variance data tabs for detailed findings."
            )

    @staticmethod
    def _build_prompt(ctx: AuditNarrativeContext) -> str:
        return (
            f"Generate a concise Workers Compensation audit narrative (3–4 paragraphs, "
            f"professional tone) for the following audit results:\n\n"
            f"Policy: {ctx.policy_number or 'Unknown'}\n"
            f"Insured: {ctx.insured_name or 'Unknown'}\n"
            f"Risk Level: {ctx.risk_level or 'Not assessed'}\n"
            f"Premium Variance: {ctx.variance_amount} ({ctx.variance_pct})\n"
            f"Missing Payroll Periods: {ctx.missing_payroll_count or 0}\n"
            f"Zero Payroll Submissions: {ctx.zero_payroll_count or 0}\n"
            f"Submission Rate: {ctx.submission_rate}\n\n"
            "Highlight key risk findings, explain the variance drivers, "
            "and recommend next steps. Do not include disclaimers."
        )

    async def generate_raw(self, prompt: str) -> str:
        """
        Generic raw prompt → raw text response.
        Used by the AI-suggest expression endpoint in carrier_config.py.
        Falls back to empty string on any error.
        """
        settings = get_settings()
        try:
            from app.services.llm_client_factory import AnthropicClient
            client = AnthropicClient(
                api_key=settings.ANTHROPIC_API_KEY,
                model="claude-sonnet-4-6",
                timeout=10.0,
            )
            return await client.generate(prompt, max_tokens=300)
        except Exception as exc:
            logger.warning("ai_narrative.generate_raw.failed", error=str(exc))
        return ""
