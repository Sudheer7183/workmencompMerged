from __future__ import annotations

from decimal import Decimal
from typing import Optional

import httpx
import structlog
from pydantic import BaseModel

from app.core.config import get_settings

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


class AINarrativeService:
    """
    Generates a plain-English audit narrative using the Anthropic API.
    Falls back to a deterministic template if the API call fails for any reason.
    The fallback MUST NEVER raise an exception — it is the last line of defence.
    """

    async def generate(self, ctx: AuditNarrativeContext) -> str:
        """
        Calls the Anthropic API to generate a narrative.
        On ANY exception (timeout, HTTP error, parse error), calls _deterministic_fallback().
        """
        settings = get_settings()

        prompt = self._build_prompt(ctx)

        try:
            async with httpx.AsyncClient(timeout=settings.ANTHROPIC_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": settings.ANTHROPIC_MODEL,
                        "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("content", [])
                if content and content[0].get("type") == "text":
                    narrative: str = content[0]["text"]
                    logger.info("ai_narrative.generated", policy=ctx.policy_number)
                    return narrative

                logger.warning("ai_narrative.empty_response", policy=ctx.policy_number)
                return self._deterministic_fallback(ctx)

        except Exception as exc:
            logger.warning(
                "ai_narrative.fallback",
                policy=ctx.policy_number,
                error=str(exc),
            )
            return self._deterministic_fallback(ctx)

    def _deterministic_fallback(self, ctx: AuditNarrativeContext) -> str:
        """
        Template-based narrative.  Uses only string formatting — no external calls,
        no arithmetic that could raise.  MUST NEVER RAISE an exception under any input,
        including all-None inputs.
        """
        try:
            policy = ctx.policy_number or "Unknown"
            insured = ctx.insured_name or "Unknown Insured"
            risk = ctx.risk_level or "Not Assessed"

            # Format variance safely
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
                "Enable the Calculation Engine and re-run to generate a full AI narrative."
            )
        except Exception:
            # Absolute last resort — return a safe static string
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
        Phase 3: Generic raw prompt → raw text response.
        Used by the AI-suggest expression endpoint in carrier_config.py.
        Falls back to empty string on any error.
        """
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 300,
                        "temperature": 0.3,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = response.json()
                if "content" in data and data["content"]:
                    return data["content"][0].get("text", "")
        except Exception as exc:
            logger.warning("ai_narrative.generate_raw.failed", error=str(exc))
        return ""
