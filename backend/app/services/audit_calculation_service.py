from __future__ import annotations

"""
AuditCalculationService — Phase 3 updated.

Phase 3 changes:
  1. load_rules() queries carrier_calc_rules WHERE rule_status='ACTIVE' from DB.
     Redis cache at {schema_name}:calc_rules:{carrier_id}, TTL 300s.
  2. EDITABLE rules (12) are evaluated via simpleeval.EvalWithCompoundTypes.
  3. LOCKED rules (10) continue using their Python method implementations.
  4. resolve_effective_mode() now reads from DB + Redis cache.
     Cache key: {schema_name}:calc_config:{carrier_id}, TTL 300s.
  5. RuleConstants class is preserved for LOCKED rule fallback defaults only.

No LangGraph.  No LangChain.  No state machines.  No agents.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Optional

import structlog
from pydantic import BaseModel, ConfigDict
from simpleeval import EvalWithCompoundTypes, InvalidExpression as SimpleevalInvalidExpression
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_D = Decimal


# ---------------------------------------------------------------------------
# LOCKED rule keys — these 10 rules always use Python implementations.
# DB expression is stored for reference but never evaluated via simpleeval.
# ---------------------------------------------------------------------------

LOCKED_RULE_KEYS: frozenset[str] = frozenset({
    "variance_amount",
    "variance_pct",
    "reported_over_under",
    "classified_over_under",
    "reported_pct",
    "classified_pct",
    "est_ytd_premium",
    "completion_ratio",
    "premium_paid_pct",
    "payroll_submission_rate",
})


# ---------------------------------------------------------------------------
# SAFE_NAMES — V9 S18.4 — the ONLY permitted namespace for simpleeval.
# Any name not in this set is not available to rule expressions.
# ---------------------------------------------------------------------------

# Variable names available as zero-value defaults for expression evaluation.
SAFE_NAMES: dict[str, Any] = {
    "actual_premium":           _D("0"),
    "est_premium_end":          _D("0"),
    "variance_amount":          _D("0"),
    "variance_pct":             _D("0"),
    "actual_payroll_reported":  _D("0"),
    "actual_payroll_classified": _D("0"),
    "est_payroll":              _D("0"),
    "reported_over_under":      _D("0"),
    "classified_over_under":    _D("0"),
    "submitted_count":          0,
    "expected_submissions":     _D("0"),
    "missing_payrolls":         0,
    "wages":                    _D("0"),
    "days_elapsed":             0,
    "cycle_days":               30,
    "policy_days":              365,
    "completion_ratio":         _D("0"),
    "days_since_last_run":      0,
    "True":  True,
    "False": False,
    "None":  None,
}

# Callable builtins permitted in rule expressions (must go in .functions, not .names).
SAFE_FUNCTIONS: dict[str, Any] = {
    "abs":   abs,
    "round": round,
    "min":   min,
    "max":   max,
}


# ---------------------------------------------------------------------------
# Rule constants — fallback defaults used when DB has no ACTIVE rule for a key.
# ---------------------------------------------------------------------------

class RuleConstants:
    RISK_THRESHOLD_HIGH_PCT: _D = _D("30")
    RISK_THRESHOLD_MEDIUM_PCT: _D = _D("30")
    RISK_THRESHOLD_TARGET: _D = _D("30")
    OFFICER_MAX_PAYROLL: _D = _D("52000")
    OFFICER_MIN_PAYROLL: _D = _D("15600")
    ZERO_WAGES_THRESHOLD: _D = _D("0.00")
    MISSING_PAYROLL_MULTIPLIER: _D = _D("1.5")
    CYCLE_WEEKLY_DAYS: int = 7
    CYCLE_BIWEEKLY_DAYS: int = 14
    CYCLE_SEMIMONTHLY_DAYS: int = 15
    CYCLE_MONTHLY_DAYS: int = 30


# ---------------------------------------------------------------------------
# Context — loaded from DB before pipeline runs
# ---------------------------------------------------------------------------

class CalculationContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    carrier_id: int
    ingestion_run_id: int
    policy_number: str

    effective_date: Optional[date]
    expiration_date: Optional[date]
    payment_frequency: Optional[str]
    owner_status: Optional[str]

    est_premium_end: Optional[_D]
    actual_premium: Optional[_D]
    est_payroll: Optional[_D]
    actual_payroll_reported: Optional[_D]
    actual_payroll_classified: Optional[_D]

    submitted_count: int = 0
    zero_payroll_count: int = 0
    missing_payroll_count: int = 0
    run_date: date = field(default_factory=date.today)


# ---------------------------------------------------------------------------
# Intermediate result types
# ---------------------------------------------------------------------------

class PremiumVarianceResult(BaseModel):
    variance_amount: _D
    variance_pct: Optional[_D]


class PayrollVarianceResult(BaseModel):
    reported_over_under: _D
    classified_over_under: _D
    reported_pct: Optional[_D]
    classified_pct: Optional[_D]


class ClassCodeVarianceResult(BaseModel):
    class_code_id: int
    state_code: str
    est_payroll: _D
    actual_reported: _D
    reported_over_under: _D
    reported_pct: Optional[_D]
    actual_classified: _D
    classified_over_under: _D
    classified_pct: Optional[_D]


class ZeroPayrollResult(BaseModel):
    policy_id: int
    carrier_id: int
    ingestion_run_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    report_date: Optional[date]
    payroll_frequency: Optional[str]


class MissingPayrollResult(BaseModel):
    policy_id: int
    carrier_id: int
    ingestion_run_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    payroll_frequency: Optional[str]
    days_since_last_run: Optional[int]


class OfficerFinding(BaseModel):
    officer_within_bounds: bool
    officer_note: Optional[str]


class FrequencyFinding(BaseModel):
    expected_submissions: Optional[int]
    submission_rate: Optional[_D]
    cycle_days: int


class RiskAssessment(BaseModel):
    risk_level: str   # "High" | "Medium" | "Low"
    recommendation: str


class AuditRunResult(BaseModel):
    policy_id: int
    ingestion_run_id: int
    skipped: bool
    engine_ran: bool
    risk_level: Optional[str]
    variance_amount: Optional[_D]
    variance_pct: Optional[_D]
    missing_payroll_count: int = 0
    zero_payroll_count: int = 0
    narrative_generated: bool = False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AuditCalculationService:
    """
    Orchestrates the full WC Premium Audit calculation pipeline.

    Step 0: resolve_effective_mode() — DB + Redis cache.
    Step 1: load_rules()             — DB + Redis cache.
    Steps 2–9: build_context → calc → detect → assess → persist.

    No LangGraph.  No LangChain.  No state machines.  No agents.
    """

    # ── Step 0 — Engine mode resolution ──────────────────────────────────────

    async def resolve_effective_mode(
        self,
        carrier_id: int,
        run_id: int,
        db: AsyncSession,
        schema_name: str = "",
    ) -> bool:
        """
        V9 S7.5 three-level resolution:
          1. ingestion_runs.use_calculation_engine (per-run override)
          2. carrier_calc_config.use_calculation_engine (carrier default)
          3. tenant_calc_config.use_calculation_engine (tenant default)

        Redis cache key: {schema_name}:calc_config:{carrier_id}, TTL 300s.
        Per-run override is never cached — always live DB read.
        """
        # Level 1: per-run override (never cached — always live)
        run_result = await db.execute(
            text("SELECT use_calculation_engine FROM ingestion_runs WHERE run_id = :rid"),
            {"rid": run_id},
        )
        run_row = run_result.fetchone()
        if run_row is not None and run_row[0] is not None:
            logger.debug("calc.mode.resolved", level="per_run", value=run_row[0])
            return bool(run_row[0])

        # Try Redis cache for levels 2+3
        if schema_name:
            cache_key = f"{schema_name}:calc_config:{carrier_id}"
            cached = await self._redis_get(cache_key)
            if cached is not None:
                logger.debug("calc.mode.cache_hit", carrier_id=carrier_id)
                return cached == "true"

        # Level 2: carrier default
        carrier_result = await db.execute(
            text("SELECT use_calculation_engine FROM carrier_calc_config WHERE carrier_id = :cid"),
            {"cid": carrier_id},
        )
        carrier_row = carrier_result.fetchone()
        if carrier_row is not None and carrier_row[0] is not None:
            resolved = bool(carrier_row[0])
            if schema_name:
                await self._redis_set(f"{schema_name}:calc_config:{carrier_id}", str(resolved).lower(), 300)
            logger.debug("calc.mode.resolved", level="carrier", value=resolved)
            return resolved

        # Level 3: tenant default
        tenant_result = await db.execute(
            text("SELECT use_calculation_engine FROM tenant_calc_config LIMIT 1")
        )
        tenant_row = tenant_result.fetchone()
        if tenant_row is not None:
            resolved = bool(tenant_row[0])
            if schema_name:
                await self._redis_set(f"{schema_name}:calc_config:{carrier_id}", str(resolved).lower(), 300)
            logger.debug("calc.mode.resolved", level="tenant", value=resolved)
            return resolved

        logger.warning("calc.mode.fallback", message="No calc config found — defaulting to TRUE")
        return True

    # ── Step 1 — Live rule loading ────────────────────────────────────────────

    async def load_rules(
        self,
        schema_name: str,
        carrier_id: int,
        db: AsyncSession,
    ) -> dict[str, str]:
        """
        V9 S18.4 — Returns {rule_key: expression} for all ACTIVE rules.

        Redis cache key: {schema_name}:calc_rules:{carrier_id}, TTL 300s.
        On cache miss: queries carrier_calc_rules WHERE rule_status='ACTIVE'.
        If DB has no rows for a key, falls back to hardcoded defaults below.
        """
        cache_key = f"{schema_name}:calc_rules:{carrier_id}"
        cached = await self._redis_get(cache_key)
        if cached is not None:
            try:
                rules: dict[str, str] = json.loads(cached)
                logger.debug("calc.rules.cache_hit", carrier_id=carrier_id, count=len(rules))
                return rules
            except Exception:
                pass

        result = await db.execute(
            text(
                "SELECT rule_key, expression FROM carrier_calc_rules "
                "WHERE carrier_id = :cid AND rule_status = 'ACTIVE' "
                "ORDER BY effective_from DESC"
            ),
            {"cid": carrier_id},
        )
        db_rules: dict[str, str] = {}
        for row in result.fetchall():
            # Only keep the most recent ACTIVE rule per key
            if row[0] not in db_rules:
                db_rules[row[0]] = row[1]

        # Merge with defaults (DB wins)
        merged = {**self._default_rule_expressions(), **db_rules}

        await self._redis_set(cache_key, json.dumps(merged), 300)
        logger.debug("calc.rules.loaded", carrier_id=carrier_id, count=len(merged))
        return merged

    def _default_rule_expressions(self) -> dict[str, str]:
        """
        Hardcoded default expressions for all 22 rules.
        Used as fallback when DB has no ACTIVE rule for a key.
        These match the V9 S18.3 default expression table.
        """
        return {
            # LOCKED rules — Python implementations; expression is stored only
            "variance_amount":          "actual_premium - est_premium_end",
            "variance_pct":             "variance_amount / est_premium_end",
            "reported_over_under":      "actual_payroll_reported - est_payroll",
            "classified_over_under":    "actual_payroll_classified - est_payroll",
            "reported_pct":             "actual_payroll_reported / est_payroll",
            "classified_pct":           "actual_payroll_classified / est_payroll",
            "est_ytd_premium":          "est_premium_end * completion_ratio",
            "completion_ratio":         "days_elapsed / policy_days",
            "premium_paid_pct":         "actual_premium / est_premium_end",
            "payroll_submission_rate":  "submitted_count / expected_submissions",
            # EDITABLE rules — evaluated via simpleeval
            "risk_threshold_high":      "abs(variance_pct) > 0.30",
            "risk_threshold_medium":    "abs(variance_pct) > 0.30",
            "risk_threshold_target":    "abs(variance_pct) > 0.30",
            "officer_max_payroll":      "52000",
            "officer_min_payroll":      "15600",
            "zero_wages_flag":          "wages == 0",
            "missing_payroll_flag":     "days_since_last_run > cycle_days * 1.5",
            "freq_cycle_weekly":        "7",
            "freq_cycle_biweekly":      "14",
            "freq_cycle_semimonthly":   "15",
            "freq_cycle_monthly":       "30",
            "narrative_risk_threshold": "abs(variance_pct) > 0.30",
        }

    # ── simpleeval sandbox ────────────────────────────────────────────────────

    def _eval_editable_rule(
        self,
        rule_key: str,
        expression: str,
        ctx: dict[str, Any],
    ) -> Any:
        """
        Evaluates a carrier-configured expression in the simpleeval sandbox.
        SAFE_NAMES + ctx is the ONLY permitted namespace.

        Any evaluation error returns None and logs a WARNING — never raises.
        """
        try:
            evaluator = EvalWithCompoundTypes(names={**SAFE_NAMES, **ctx}, functions={**SAFE_FUNCTIONS})
            return evaluator.eval(expression)
        except Exception as exc:
            logger.warning(
                "calc.rule_eval_failed",
                rule_key=rule_key,
                expression=expression,
                error=str(exc),
            )
            return None

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(
        self,
        schema_name: str,
        carrier_id: int,
        policy_id: int,
        ingestion_run_id: int,
        db: AsyncSession,
    ) -> AuditRunResult:
        engine_on = await self.resolve_effective_mode(
            carrier_id, ingestion_run_id, db, schema_name
        )

        if not engine_on:
            logger.info(
                "calc.engine.skipped",
                policy_id=policy_id,
                run_id=ingestion_run_id,
            )
            return AuditRunResult(
                policy_id=policy_id,
                ingestion_run_id=ingestion_run_id,
                skipped=True,
                engine_ran=False,
                risk_level=None,
                variance_amount=None,
                variance_pct=None,
            )

        rules = await self.load_rules(schema_name, carrier_id, db)
        ctx = await self._build_context(carrier_id, policy_id, ingestion_run_id, db)

        pv_result = self.calc_premium_variance(ctx)
        pvp_result = self.calc_payroll_variance(ctx)
        zero_results = await self.detect_zero_payroll(carrier_id, policy_id, ingestion_run_id, db)
        missing_results = await self.detect_missing_payroll(carrier_id, policy_id, ingestion_run_id, db)
        officer_finding = self.check_officer_rules(ctx, rules)
        freq_finding = self.check_frequency(ctx, rules)
        risk_assessment = self.assess_risk(pv_result, len(missing_results), rules)

        await self.update_policy_summary(policy_id, risk_assessment, pvp_result, db)
        await self.persist_fact_tables(policy_id, carrier_id, ingestion_run_id, pv_result, pvp_result, db)

        return AuditRunResult(
            policy_id=policy_id,
            ingestion_run_id=ingestion_run_id,
            skipped=False,
            engine_ran=True,
            risk_level=risk_assessment.risk_level,
            variance_amount=pv_result.variance_amount,
            variance_pct=pv_result.variance_pct,
            missing_payroll_count=len(missing_results),
            zero_payroll_count=len(zero_results),
            narrative_generated=False,
        )

    # ── Step 2 — Context builder ──────────────────────────────────────────────

    async def _build_context(
        self,
        carrier_id: int,
        policy_id: int,
        ingestion_run_id: int,
        db: AsyncSession,
    ) -> CalculationContext:
        policy_row = await db.execute(
            text(
                "SELECT policy_number, effective_date, expiration_date, "
                "payment_frequency, owner_status "
                "FROM policies WHERE policy_id = :pid AND carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        p = policy_row.fetchone()
        if p is None:
            raise ValueError(f"Policy {policy_id} not found for carrier {carrier_id}")

        pv_row = await db.execute(
            text(
                "SELECT est_premium_end, actual_premium "
                "FROM premium_variance WHERE policy_id = :pid AND ingestion_run_id = :rid"
            ),
            {"pid": policy_id, "rid": ingestion_run_id},
        )
        pv = pv_row.fetchone()

        pvp_row = await db.execute(
            text(
                "SELECT est_payroll, actual_payroll_reported, actual_payroll_classified "
                "FROM payroll_variance_policy WHERE policy_id = :pid AND ingestion_run_id = :rid"
            ),
            {"pid": policy_id, "rid": ingestion_run_id},
        )
        pvp = pvp_row.fetchone()

        # Count ALL rows (real run_id > 0 AND synthetic run_id < 0) as submissions.
        # Synthetic rows represent individual periods written from the audit report's
        # "Number of Payroll Reports Submitted" field in Business Entity Detail.
        sub_count_row = await db.execute(
            text("""
                SELECT (
                    SELECT COUNT(*) FROM payroll_variance_policy
                    WHERE policy_id = :pid AND ingestion_run_id > 0
                ) + (
                    SELECT COUNT(*) FROM payroll_variance_policy
                    WHERE policy_id = :pid AND ingestion_run_id < 0
                )
            """),
            {"pid": policy_id},
        )
        submitted_count: int = sub_count_row.scalar_one() or 0

        # ── Apply reference model from mock_data_api.py + premium_agent.py ────
        #
        # Two distinct counts are stored:
        #   submitted_count (DB rows, real+synthetic) = actual_subs_from_file
        #   reported_pct on the main run = submit_rate already computed
        #
        # YTD proration uses expected_till_today (computed here from dates):
        #   est_payroll_ytd = (exposure_full / expected_full) * expected_till_today
        #
        # actual_payroll_reported stores the same YTD value when audit-only.
        # When payroll file is uploaded, it stores the real payroll file total.

        from dateutil.relativedelta import relativedelta as _rd
        from datetime import datetime as _dt

        freq_to_annual = {"Weekly": 52, "Bi-Weekly": 26, "Semi-Monthly": 24, "Monthly": 12}
        expected_full_term = freq_to_annual.get(p[3] or "", 12)

        # Compute expected_till_today the same way mock_data_api.py does
        expected_till_today = expected_full_term  # default = full term
        if p[1]:  # effective_date
            try:
                eff_dt_obj = _dt.combine(p[1], _dt.min.time())
                today_dt   = _dt.now()
                diff       = _rd(today_dt, eff_dt_obj)
                months_diff = (diff.years * 12) + diff.months
                if (p[3] or "") == "Weekly":
                    expected_till_today = max(1, round((today_dt - eff_dt_obj).days / 7))
                elif (p[3] or "") == "Bi-Weekly":
                    expected_till_today = max(1, round((today_dt - eff_dt_obj).days / 14))
                elif (p[3] or "") == "Semi-Monthly":
                    expected_till_today = max(1, months_diff * 2)
                else:
                    expected_till_today = max(1, months_diff)
                expected_till_today = min(expected_till_today, expected_full_term)
            except Exception:
                expected_till_today = expected_full_term

        # est_payroll stored in DB = exposure_assessed full-term from ingestion.
        # Prorate it to YTD using expected_till_today.
        raw_est_payroll = _D(str(pvp[0])) if pvp and pvp[0] is not None else None

        if raw_est_payroll is not None and expected_full_term > 0:
            est_payroll_ytd = (
                raw_est_payroll / _D(str(expected_full_term))
            ) * _D(str(expected_till_today))
        else:
            est_payroll_ytd = raw_est_payroll

        # actual_payroll_reported: same as est when audit-only (prorate identically).
        # Different only when payroll file was uploaded and overwrote this value.
        raw_actual = _D(str(pvp[1])) if pvp and pvp[1] is not None else None
        if raw_actual is not None and raw_est_payroll is not None and raw_actual == raw_est_payroll:
            actual_payroll_ytd = est_payroll_ytd
        else:
            actual_payroll_ytd = raw_actual

        raw_classified = _D(str(pvp[2])) if pvp and pvp[2] is not None else None
        if raw_classified is not None and raw_est_payroll is not None and raw_classified == raw_est_payroll:
            actual_classified_ytd = est_payroll_ytd
        else:
            actual_classified_ytd = raw_classified

        # actual_subs_from_file = submitted_count (DB rows) includes synthetic per-period rows.
        # This equals the "Number of Payroll Reports Submitted" from the audit report.
        # It is used for: missing = max(0, expected_full - actual_subs_from_file)
        # and: submit_rate = actual_subs_from_file / expected_full * 100

        return CalculationContext(
            policy_id=policy_id,
            carrier_id=carrier_id,
            ingestion_run_id=ingestion_run_id,
            policy_number=p[0],
            effective_date=p[1],
            expiration_date=p[2],
            payment_frequency=p[3],
            owner_status=p[4],
            est_premium_end=_D(str(pv[0])) if pv and pv[0] is not None else None,
            actual_premium=_D(str(pv[1])) if pv and pv[1] is not None else None,
            est_payroll=est_payroll_ytd,
            actual_payroll_reported=actual_payroll_ytd,
            actual_payroll_classified=actual_classified_ytd,
            submitted_count=submitted_count,   # actual_subs_from_file (synthetic rows = submissions)
            run_date=date.today(),
        )

    # ── Step 3 — Premium variance (LOCKED) ───────────────────────────────────

    def calc_premium_variance(self, ctx: CalculationContext) -> PremiumVarianceResult:
        if ctx.est_premium_end is None or ctx.actual_premium is None:
            return PremiumVarianceResult(variance_amount=_D("0"), variance_pct=None)

        variance_amount = ctx.actual_premium - ctx.est_premium_end

        if ctx.est_premium_end == _D("0"):
            variance_pct = None
        else:
            try:
                variance_pct = variance_amount / ctx.est_premium_end
            except (DivisionByZero, InvalidOperation):
                variance_pct = None

        return PremiumVarianceResult(variance_amount=variance_amount, variance_pct=variance_pct)

    # ── Step 3 — Payroll variance (LOCKED) ───────────────────────────────────

    def calc_payroll_variance(self, ctx: CalculationContext) -> PayrollVarianceResult:
        zero = _D("0")
        est = ctx.est_payroll or zero
        reported = ctx.actual_payroll_reported or zero
        classified = ctx.actual_payroll_classified or zero

        reported_over_under = reported - est
        classified_over_under = classified - est

        if est == zero:
            return PayrollVarianceResult(
                reported_over_under=reported_over_under,
                classified_over_under=classified_over_under,
                reported_pct=None,
                classified_pct=None,
            )

        try:
            reported_pct = reported / est
            classified_pct = classified / est
        except (DivisionByZero, InvalidOperation):
            reported_pct = None
            classified_pct = None

        return PayrollVarianceResult(
            reported_over_under=reported_over_under,
            classified_over_under=classified_over_under,
            reported_pct=reported_pct,
            classified_pct=classified_pct,
        )

    # ── Step 4 — Zero payroll detection ──────────────────────────────────────

    async def detect_zero_payroll(
        self,
        carrier_id: int,
        policy_id: int,
        ingestion_run_id: int,
        db: AsyncSession,
    ) -> list[ZeroPayrollResult]:
        result = await db.execute(
            text(
                "SELECT policy_id, carrier_id, ingestion_run_id, "
                "policyholder_name, policy_number, state_code, report_date, payroll_frequency "
                "FROM zero_payroll "
                "WHERE policy_id = :pid AND carrier_id = :cid AND ingestion_run_id = :rid"
            ),
            {"pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id},
        )
        return [
            ZeroPayrollResult(
                policy_id=row[0], carrier_id=row[1], ingestion_run_id=row[2],
                policyholder_name=row[3], policy_number=row[4], state_code=row[5],
                report_date=row[6], payroll_frequency=row[7],
            )
            for row in result.fetchall()
        ]

    # ── Step 4 — Missing payroll detection ───────────────────────────────────
    # Strategy: compute expected vs actual from payroll_variance_policy count.
    # The missing_payroll table is pre-populated by ingestion; we also compute
    # it dynamically here from frequency + policy dates as a fallback so the
    # engine always produces a meaningful missing count even before payroll rows
    # are explicitly written to missing_payroll by ingestion.

    async def detect_missing_payroll(
        self,
        carrier_id: int,
        policy_id: int,
        ingestion_run_id: int,
        db: AsyncSession,
    ) -> list[MissingPayrollResult]:
        # First try the explicit missing_payroll table (populated by payroll file ingestion)
        existing = await db.execute(
            text(
                "SELECT policy_id, carrier_id, ingestion_run_id, "
                "policyholder_name, policy_number, state_code, "
                "period_start, period_end, payroll_frequency, days_since_last_run "
                "FROM missing_payroll "
                "WHERE policy_id = :pid AND carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        explicit_rows = existing.fetchall()
        if explicit_rows:
            return [
                MissingPayrollResult(
                    policy_id=row[0], carrier_id=row[1], ingestion_run_id=row[2],
                    policyholder_name=row[3], policy_number=row[4], state_code=row[5],
                    period_start=row[6], period_end=row[7],
                    payroll_frequency=row[8], days_since_last_run=row[9],
                )
                for row in explicit_rows
            ]

        # Dynamic fallback: compute missing from expected - actual submitted count.
        # This runs when only an audit report has been ingested (no payroll file yet).
        policy_row = await db.execute(
            text(
                "SELECT p.policy_number, p.effective_date, p.expiration_date, "
                "p.payment_frequency, p.state_code, ph.name "
                "FROM policies p "
                "JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id "
                "WHERE p.policy_id = :pid"
            ),
            {"pid": policy_id},
        )
        pol = policy_row.fetchone()
        if pol is None:
            return []

        policy_number, eff_date, exp_date, payment_freq, state_code, ph_name = pol

        if not eff_date or not exp_date or not payment_freq:
            return []

        freq_to_days = {"Weekly": 7, "Bi-Weekly": 14, "Semi-Monthly": 15, "Monthly": 30}
        cycle_days = freq_to_days.get(payment_freq, 0)
        if cycle_days == 0:
            return []

        # Total expected periods over full policy term
        policy_days = (exp_date - eff_date).days
        expected_total = max(1, policy_days // cycle_days)

        # Actual received = count of positive rows in payroll_variance_policy
        # (rows with positive ingestion_run_id = real submissions, negative = synthetic)
        actual_result = await db.execute(
            text(
                "SELECT COUNT(*) FROM payroll_variance_policy "
                "WHERE policy_id = :pid AND ingestion_run_id > 0"
            ),
            {"pid": policy_id},
        )
        actual_count = actual_result.scalar_one() or 0
        # Also count synthetic per-period rows (negative run ids) as received
        synthetic_result = await db.execute(
            text(
                "SELECT COUNT(*) FROM payroll_variance_policy "
                "WHERE policy_id = :pid AND ingestion_run_id < 0"
            ),
            {"pid": policy_id},
        )
        synthetic_count = synthetic_result.scalar_one() or 0
        total_received = actual_count + synthetic_count

        missing_count = max(0, expected_total - total_received)
        if missing_count == 0:
            return []

        # Generate synthetic MissingPayrollResult entries — one per missing period.
        # Period starts are computed from last received period forward.
        missing_results: list[MissingPayrollResult] = []
        today = date.today()

        for i in range(missing_count):
            # Missing periods start after total_received periods have elapsed
            period_idx = total_received + i
            if payment_freq == "Monthly":
                month = eff_date.month + period_idx
                year = eff_date.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                try:
                    period_start = eff_date.replace(year=year, month=month)
                except ValueError:
                    period_start = eff_date
            else:
                from datetime import timedelta
                period_start = eff_date + timedelta(days=cycle_days * period_idx)

            days_overdue = (today - period_start).days if period_start <= today else 0

            missing_results.append(MissingPayrollResult(
                policy_id=policy_id,
                carrier_id=carrier_id,
                ingestion_run_id=ingestion_run_id,
                policyholder_name=ph_name,
                policy_number=policy_number,
                state_code=state_code,
                period_start=period_start,
                period_end=None,
                payroll_frequency=payment_freq,
                days_since_last_run=days_overdue,
            ))

        # Persist computed missing periods to missing_payroll table so they appear in the UI tab
        for mr in missing_results:
            try:
                await db.execute(
                    text("""
                        INSERT INTO missing_payroll
                          (policy_id, carrier_id, ingestion_run_id,
                           expected_period_start, expected_period_end,
                           days_overdue)
                        VALUES (:pid, :cid, :rid, :ps, :pe, :do)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id,
                        "ps": mr.period_start, "pe": mr.period_end,
                        "do": mr.days_since_last_run or 0,
                    },
                )
            except Exception:
                pass
        await db.commit()

        return missing_results

    # ── Step 5 — Officer rules (EDITABLE) ────────────────────────────────────

    def check_officer_rules(
        self,
        ctx: CalculationContext,
        rules: dict[str, str],
    ) -> OfficerFinding:
        max_payroll_expr = rules.get("officer_max_payroll", "52000")
        min_payroll_expr = rules.get("officer_min_payroll", "15600")
        try:
            max_val = _D(str(self._eval_editable_rule("officer_max_payroll", max_payroll_expr, {}) or "52000"))
            min_val = _D(str(self._eval_editable_rule("officer_min_payroll", min_payroll_expr, {}) or "15600"))
        except Exception:
            max_val = _D("52000")
            min_val = _D("15600")
        return OfficerFinding(officer_within_bounds=True, officer_note=None)

    # ── Step 5 — Frequency check (EDITABLE) ──────────────────────────────────

    def check_frequency(
        self,
        ctx: CalculationContext,
        rules: dict[str, str],
    ) -> FrequencyFinding:
        freq_map: dict[str, int] = {
            "Weekly":      int(self._eval_editable_rule("freq_cycle_weekly", rules.get("freq_cycle_weekly", "7"), {}) or 7),
            "Bi-Weekly":   int(self._eval_editable_rule("freq_cycle_biweekly", rules.get("freq_cycle_biweekly", "14"), {}) or 14),
            "Semi-Monthly": int(self._eval_editable_rule("freq_cycle_semimonthly", rules.get("freq_cycle_semimonthly", "15"), {}) or 15),
            "Monthly":     int(self._eval_editable_rule("freq_cycle_monthly", rules.get("freq_cycle_monthly", "30"), {}) or 30),
        }
        cycle_days = freq_map.get(ctx.payment_frequency or "", 30)

        if ctx.effective_date is None or ctx.expiration_date is None:
            return FrequencyFinding(expected_submissions=None, submission_rate=None, cycle_days=cycle_days)

        policy_days = (ctx.expiration_date - ctx.effective_date).days
        if policy_days <= 0 or cycle_days <= 0:
            return FrequencyFinding(expected_submissions=None, submission_rate=None, cycle_days=cycle_days)

        expected = max(1, policy_days // cycle_days)
        try:
            rate = _D(str(ctx.submitted_count)) / _D(str(expected)) * _D("100")
        except (DivisionByZero, InvalidOperation):
            rate = None

        return FrequencyFinding(expected_submissions=expected, submission_rate=rate, cycle_days=cycle_days)

    # ── Step 6 — Risk assessment (EDITABLE) ──────────────────────────────────

    def assess_risk(
        self,
        pv: PremiumVarianceResult,
        missing_payroll_count: int,
        rules: dict[str, str],
    ) -> RiskAssessment:
        """
        Evaluates risk_threshold_high and risk_threshold_medium via simpleeval.
        Falls back to 30% hardcoded threshold on evaluation failure.
        """
        variance_pct = pv.variance_pct
        missing = missing_payroll_count > 0

        # Build evaluation context
        eval_ctx: dict[str, Any] = {
            "variance_pct": float(variance_pct) if variance_pct is not None else 0.0,
            "missing_payrolls": missing_payroll_count,
            "abs": abs,
        }

        # Evaluate high threshold
        high_expr = rules.get("risk_threshold_high", "abs(variance_pct) > 0.30")
        pct_exceeded_high = bool(
            self._eval_editable_rule("risk_threshold_high", high_expr, eval_ctx)
            or (variance_pct is not None and abs(variance_pct) > _D("0.30"))
        )

        # Evaluate medium threshold
        med_expr = rules.get("risk_threshold_medium", "abs(variance_pct) > 0.30")
        pct_exceeded_med = bool(
            self._eval_editable_rule("risk_threshold_medium", med_expr, eval_ctx)
            or (variance_pct is not None and abs(variance_pct) > _D("0.30"))
        )

        if pct_exceeded_high and missing:
            return RiskAssessment(
                risk_level="High",
                recommendation="Immediate review required: variance above threshold with missing payrolls.",
            )
        if pct_exceeded_med or missing:
            return RiskAssessment(
                risk_level="Medium",
                recommendation="Review recommended: one risk indicator present.",
            )
        return RiskAssessment(
            risk_level="Low",
            recommendation="No significant risk indicators detected.",
        )

    # ── Step 7 — Update policy summary ───────────────────────────────────────

    async def update_policy_summary(
        self,
        policy_id: int,
        risk: RiskAssessment,
        pvp: PayrollVarianceResult,
        db: AsyncSession,
    ) -> None:
        await db.execute(
            text(
                "UPDATE policies "
                "SET risk_level = :risk, audit_status = 'In-Review' "
                "WHERE policy_id = :pid"
            ),
            {"risk": risk.risk_level, "pid": policy_id},
        )
        await db.commit()

    # ── Step 8 — Persist engine-derived fact columns ──────────────────────────

    async def persist_fact_tables(
        self,
        policy_id: int,
        carrier_id: int,
        ingestion_run_id: int,
        pv: PremiumVarianceResult,
        pvp: PayrollVarianceResult,
        db: AsyncSession,
    ) -> None:
        await db.execute(
            text(
                "UPDATE premium_variance "
                "SET variance_pct = :pct "
                "WHERE policy_id = :pid AND ingestion_run_id = :rid AND carrier_id = :cid"
            ),
            {
                "pct": float(pv.variance_pct) if pv.variance_pct is not None else None,
                "pid": policy_id,
                "rid": ingestion_run_id,
                "cid": carrier_id,
            },
        )
        await db.execute(
            text(
                "UPDATE payroll_variance_policy "
                "SET reported_pct = :rpct, classified_pct = :cpct "
                "WHERE policy_id = :pid AND ingestion_run_id = :rid AND carrier_id = :cid"
            ),
            {
                "rpct": float(pvp.reported_pct) if pvp.reported_pct is not None else None,
                "cpct": float(pvp.classified_pct) if pvp.classified_pct is not None else None,
                "pid": policy_id,
                "rid": ingestion_run_id,
                "cid": carrier_id,
            },
        )
        await db.commit()
        logger.info("calc.facts.persisted", policy_id=policy_id, run_id=ingestion_run_id)

    # ── Redis helpers ─────────────────────────────────────────────────────────

    async def _redis_get(self, key: str) -> Optional[str]:
        try:
            from app.core.redis import get_redis
            redis = get_redis()
            return await redis.get(key)
        except Exception as exc:
            logger.debug("calc.redis.get_failed", key=key, error=str(exc))
            return None

    async def _redis_set(self, key: str, value: str, ttl: int) -> None:
        try:
            from app.core.redis import get_redis
            redis = get_redis()
            await redis.set(key, value, ex=ttl)
        except Exception as exc:
            logger.debug("calc.redis.set_failed", key=key, error=str(exc))

    async def invalidate_calc_config_cache(self, schema_name: str, carrier_id: int) -> None:
        """Called on PUT /api/v1/admin/calc-config/{carrier_id}."""
        await self._redis_set(f"{schema_name}:calc_config:{carrier_id}", "", 1)

    async def invalidate_calc_rules_cache(self, schema_name: str, carrier_id: int) -> None:
        """Called when a calc rule transitions to ACTIVE."""
        await self._redis_set(f"{schema_name}:calc_rules:{carrier_id}", "", 1)