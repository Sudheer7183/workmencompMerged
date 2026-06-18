
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
    # These 3 keys map to PostgreSQL GENERATED columns — the DB computes them
    # at INSERT time via SQL expressions, not by the Python calc engine.
    # Their expressions are stored in carrier_calc_rules for documentation
    # and audit history only; simpleeval never evaluates them.
    "variance_amount",        # GENERATED: actual_premium - est_premium_end
    "reported_over_under",    # GENERATED: actual_payroll_reported - est_payroll
    "classified_over_under",  # GENERATED: actual_payroll_classified - est_payroll
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
        Hardcoded default expressions for ALL rules.

        These are the safety-net fallbacks — used ONLY when no ACTIVE row exists
        in carrier_calc_rules for a given rule_key.  The DB always wins.

        Three rules are LOCKED (GENERATED columns); their expressions here are
        for documentation only — they are never evaluated by simpleeval.

        The remaining 19 rules are ALL evaluated via simpleeval.  Variable names
        used in expressions must exist in SAFE_NAMES.
        """
        return {
            # ── LOCKED (GENERATED column) — never evaluated by simpleeval ────
            "variance_amount":       "actual_premium - est_premium_end",
            "reported_over_under":   "actual_payroll_reported - est_payroll",
            "classified_over_under": "actual_payroll_classified - est_payroll",

            # ── Premium rules ─────────────────────────────────────────────────
            # variance_pct: % difference between actual and estimated premium.
            # NULL-safe: returns None when est_premium_end is zero.
            "variance_pct":
                "variance_amount / est_premium_end if est_premium_end != 0 else None",

            # ── Policy-level payroll rules ────────────────────────────────────
            # reported_pct: actual reported payroll / estimated payroll.
            "reported_pct":
                "actual_payroll_reported / est_payroll if est_payroll != 0 else None",
            # classified_pct: actual classified payroll / estimated payroll.
            "classified_pct":
                "actual_payroll_classified / est_payroll if est_payroll != 0 else None",

            # ── Class-code-level payroll rules ────────────────────────────────
            # class_reported_pct: per-class reported / estimated.
            # Uses actual_reported (payroll_variance_class.actual_reported).
            "class_reported_pct":
                "actual_reported / est_payroll if est_payroll != 0 else None",
            # class_classified_pct: per-class classified / estimated.
            "class_classified_pct":
                "actual_classified / est_payroll if est_payroll != 0 else None",

            # ── Submission / completion rules ─────────────────────────────────
            # completion_ratio: how far through the policy term we are.
            "completion_ratio":
                "days_elapsed / policy_days if policy_days != 0 else None",
            # expected_submissions: how many payrolls should have been received.
            "expected_submissions":
                "policy_days / cycle_days if cycle_days != 0 else None",
            # submission_rate: actual vs expected submissions as a percentage.
            "submission_rate":
                "submitted_count / expected_submissions * 100 if expected_submissions != 0 else None",

            # ── Risk threshold rules ──────────────────────────────────────────
            # These evaluate to True/False and drive policy risk_level assignment.
            # Carriers change these to tighten or loosen their risk criteria.
            "risk_threshold_high":
                "abs(variance_pct) > 0.30 and missing_payrolls > 0",
            "risk_threshold_medium":
                "abs(variance_pct) > 0.30 or missing_payrolls > 0",
            # risk_threshold_target: numeric value shown on the dashboard widget.
            "risk_threshold_target": "30",

            # ── Officer payroll boundary rules ────────────────────────────────
            # Numeric thresholds; applied in check_officer_rules().
            "officer_max_payroll": "52000",
            "officer_min_payroll": "15600",

            # ── Detection flag rules ──────────────────────────────────────────
            "zero_payroll_flag":
                "wages == 0.0",
            "missing_payroll_flag":
                "days_since_last_run > cycle_days * 1.5",

            # ── Payroll cycle length rules ────────────────────────────────────
            # These numeric values feed into check_frequency() and
            # detect_missing_payroll() to compute expected submission counts.
            "freq_cycle_weekly":       "7",
            "freq_cycle_biweekly":     "14",
            "freq_cycle_semimonthly":  "15",
            "freq_cycle_monthly":      "30",

            # ── AI narrative threshold ────────────────────────────────────────
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

        # freq_finding must run FIRST — cycle_days feeds into detect_missing_payroll
        freq_finding    = self.check_frequency(ctx, rules)
        # calc_premium_variance and calc_payroll_variance now accept rules
        pv_result       = self.calc_premium_variance(ctx, rules=rules)
        pvp_result      = self.calc_payroll_variance(ctx, rules=rules)
        officer_finding = self.check_officer_rules(ctx, rules)
        zero_results    = await self.detect_zero_payroll(
            carrier_id, policy_id, ingestion_run_id, db, rules=rules
        )
        missing_results = await self.detect_missing_payroll(
            carrier_id, policy_id, ingestion_run_id, db,
            rules=rules,
            cycle_days_override=freq_finding.cycle_days,
        )
        risk_assessment = self.assess_risk(pv_result, len(missing_results), rules)

        await self.update_policy_summary(
            policy_id, risk_assessment, pvp_result, db, officer_finding
        )
        await self.persist_fact_tables(
            policy_id, carrier_id, ingestion_run_id, pv_result, pvp_result, db, rules=rules
        )

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

    def calc_premium_variance(
        self,
        ctx: CalculationContext,
        rules: Optional[dict[str, str]] = None,
    ) -> PremiumVarianceResult:
        """
        Computes premium variance amount (LOCKED — always Python arithmetic)
        and variance_pct (EDITABLE — evaluated via carrier rule expression).

        variance_amount is a GENERATED column in premium_variance; the Python
        arithmetic here mirrors that formula exactly and is always authoritative.

        variance_pct uses the carrier-configured expression.  The default
        "variance_amount / est_premium_end if est_premium_end != 0 else None"
        gives the standard percentage.  Carriers can customise this formula,
        e.g. to apply rounding: "round(variance_amount / est_premium_end, 4)".
        """
        if ctx.est_premium_end is None or ctx.actual_premium is None:
            return PremiumVarianceResult(variance_amount=_D("0"), variance_pct=None)

        # LOCKED: variance_amount is always Python arithmetic (mirrors GENERATED col)
        variance_amount = ctx.actual_premium - ctx.est_premium_end

        # EDITABLE: evaluate variance_pct via carrier rule
        pct_expr = (rules or {}).get(
            "variance_pct",
            "variance_amount / est_premium_end if est_premium_end != 0 else None",
        )
        eval_ctx: dict[str, Any] = {
            "variance_amount":  float(variance_amount),
            "est_premium_end":  float(ctx.est_premium_end),
            "actual_premium":   float(ctx.actual_premium),
        }
        raw_pct = self._eval_editable_rule("variance_pct", pct_expr, eval_ctx)
        if raw_pct is not None:
            try:
                variance_pct = _D(str(raw_pct))
            except Exception:
                variance_pct = None
        else:
            # Rule eval returned None (e.g. est_premium_end == 0) — correct result
            variance_pct = None

        return PremiumVarianceResult(variance_amount=variance_amount, variance_pct=variance_pct)

    # ── Step 3 — Payroll variance (LOCKED) ───────────────────────────────────

    def calc_payroll_variance(
        self,
        ctx: CalculationContext,
        rules: Optional[dict[str, str]] = None,
    ) -> PayrollVarianceResult:
        """
        Computes policy-level payroll variance.

        reported_over_under / classified_over_under: LOCKED (GENERATED columns).
        reported_pct / classified_pct: EDITABLE — use carrier rule expressions.

        Default reported_pct:   "actual_payroll_reported / est_payroll if est_payroll != 0 else None"
        Default classified_pct: "actual_payroll_classified / est_payroll if est_payroll != 0 else None"

        Carriers can adjust these, e.g. apply rounding or use a different base.
        """
        zero = _D("0")
        est        = ctx.est_payroll or zero
        reported   = ctx.actual_payroll_reported or zero
        classified = ctx.actual_payroll_classified or zero

        # LOCKED: over/under amounts mirror GENERATED columns
        reported_over_under   = reported - est
        classified_over_under = classified - est

        # EDITABLE: evaluate reported_pct via carrier rule
        eval_ctx: dict[str, Any] = {
            "actual_payroll_reported":   float(reported),
            "actual_payroll_classified": float(classified),
            "est_payroll":               float(est),
        }

        rpct_expr = (rules or {}).get(
            "reported_pct",
            "actual_payroll_reported / est_payroll if est_payroll != 0 else None",
        )
        raw_rpct = self._eval_editable_rule("reported_pct", rpct_expr, eval_ctx)
        try:
            reported_pct = _D(str(raw_rpct)) if raw_rpct is not None else None
        except Exception:
            reported_pct = None

        cpct_expr = (rules or {}).get(
            "classified_pct",
            "actual_payroll_classified / est_payroll if est_payroll != 0 else None",
        )
        raw_cpct = self._eval_editable_rule("classified_pct", cpct_expr, eval_ctx)
        try:
            classified_pct = _D(str(raw_cpct)) if raw_cpct is not None else None
        except Exception:
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
        rules: Optional[dict[str, str]] = None,
    ) -> list[ZeroPayrollResult]:
        """
        Returns all zero-payroll periods for this policy run.

        Two sources of zero-payroll rows:
          1. Rows already written to zero_payroll by the ingestion pipeline.
          2. NEW: rows in payroll_variance_class where the calc engine evaluates
             the zero_wages_flag rule as True (wages == 0 by default, but
             carriers can customise this expression via the rule config UI).

        Rule: zero_wages_flag  (default: "wages == 0.0")
          - Context variables: wages (actual_reported for that class code row)
          - Evaluates to True/False per class-code payroll row.
          - If True and no zero_payroll row exists yet, one is inserted.

        Falls back to the ingestion-written rows when no rules are provided.
        """
        # Step 1: fetch rows already written by ingestion
        existing_result = await db.execute(
            text(
                "SELECT policy_id, carrier_id, ingestion_run_id, "
                "policyholder_name, policy_number, state_code, report_date, payroll_frequency "
                "FROM zero_payroll "
                "WHERE policy_id = :pid AND carrier_id = :cid AND ingestion_run_id = :rid"
            ),
            {"pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id},
        )
        existing_rows = existing_result.fetchall()

        # Step 2: re-evaluate zero_wages_flag via the carrier rule against
        # payroll_variance_class rows for this run — catch any zeros the
        # ingestion pipeline may have missed.
        if rules is not None:
            zero_flag_expr = rules.get("zero_wages_flag", "wages == 0.0")

            pvc_result = await db.execute(
                text(
                    "SELECT pvc.state_code, pvc.actual_reported, "
                    "p.policy_number, ph.name AS policyholder_name, "
                    "p.payment_frequency, pvc.as_of_date "
                    "FROM payroll_variance_class pvc "
                    "JOIN policies p ON p.policy_id = pvc.policy_id "
                    "JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id "
                    "WHERE pvc.policy_id = :pid "
                    "  AND pvc.carrier_id = :cid "
                    "  AND pvc.ingestion_run_id = :rid"
                ),
                {"pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id},
            )
            pvc_rows = pvc_result.fetchall()

            for pvc in pvc_rows:
                state_code, actual_reported, policy_number, ph_name, payment_freq, as_of_date = pvc
                wages_val = _D(str(actual_reported)) if actual_reported is not None else _D("0")

                eval_ctx: dict[str, Any] = {"wages": float(wages_val)}
                is_zero = bool(
                    self._eval_editable_rule("zero_wages_flag", zero_flag_expr, eval_ctx)
                )

                if is_zero:
                    try:
                        await db.execute(
                            text(
                                "INSERT INTO zero_payroll "
                                "(policy_id, carrier_id, ingestion_run_id, "
                                "policyholder_name, policy_number, state_code, "
                                "report_date, payroll_frequency) "
                                "VALUES (:pid, :cid, :rid, :ph, :pn, :sc, :rd, :pf) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {
                                "pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id,
                                "ph": ph_name, "pn": policy_number, "sc": state_code,
                                "rd": as_of_date, "pf": payment_freq,
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "calc.zero_payroll.insert_failed",
                            policy_id=policy_id, error=str(exc),
                        )

            await db.commit()

            # Re-fetch after engine-detected insertions
            refreshed = await db.execute(
                text(
                    "SELECT policy_id, carrier_id, ingestion_run_id, "
                    "policyholder_name, policy_number, state_code, report_date, payroll_frequency "
                    "FROM zero_payroll "
                    "WHERE policy_id = :pid AND carrier_id = :cid AND ingestion_run_id = :rid"
                ),
                {"pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id},
            )
            existing_rows = refreshed.fetchall()

        return [
            ZeroPayrollResult(
                policy_id=row[0], carrier_id=row[1], ingestion_run_id=row[2],
                policyholder_name=row[3], policy_number=row[4], state_code=row[5],
                report_date=row[6], payroll_frequency=row[7],
            )
            for row in existing_rows
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
        rules: Optional[dict[str, str]] = None,
        cycle_days_override: int = 30,
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

        # Use cycle_days_override (from check_frequency which evaluated freq rules)
        # so carrier-configured cycle lengths feed through to missing detection.
        freq_to_days = {"Weekly": 7, "Bi-Weekly": 14, "Semi-Monthly": 15, "Monthly": 30}
        cycle_days = cycle_days_override if cycle_days_override > 0 else freq_to_days.get(payment_freq, 0)
        if cycle_days == 0:
            return []

        # Total expected periods — evaluate via carrier expected_submissions rule.
        # Falls back to policy_days // cycle_days only when the rule returns None.
        policy_days = (exp_date - eff_date).days
        exp_expr = (rules or {}).get(
            "expected_submissions",
            "policy_days / cycle_days if cycle_days != 0 else None",
        )
        raw_exp = self._eval_editable_rule(
            "expected_submissions",
            exp_expr,
            {"policy_days": policy_days, "cycle_days": cycle_days},
        )
        expected_total = max(1, int(raw_exp)) if raw_exp is not None else max(1, policy_days // cycle_days)

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

            # Evaluate missing_payroll_flag rule — default: days_since_last_run > cycle_days * 1.5
            # Carrier can customise this threshold via the rule config UI.
            missing_flag_expr = (rules or {}).get(
                "missing_payroll_flag", "days_since_last_run > cycle_days * 1.5"
            )
            flag_ctx: dict[str, Any] = {
                "days_since_last_run": days_overdue,
                "cycle_days": cycle_days,
            }
            is_missing = bool(
                self._eval_editable_rule("missing_payroll_flag", missing_flag_expr, flag_ctx)
                if days_overdue > 0
                else True   # period is in the past — unconditionally missing
            )
            if not is_missing:
                continue   # this gap doesn't meet the carrier's missing threshold — skip it

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
        """
        Evaluates officer_max_payroll and officer_min_payroll from carrier rules.

        Rule expressions must evaluate to a plain number (e.g. "52000").
        If a carrier has customised the limits, those values are used.
        Falls back to hardcoded defaults only when eval fails or returns None.

        The evaluated thresholds cap the payroll used for WC calculations:
          - actual_payroll_reported is clamped to [min_val, max_val]
          - If the policy owner_status is "Included", the officer's payroll
            should fall within these bounds; findings are noted if it doesn't.
        """
        max_payroll_expr = rules.get("officer_max_payroll", "52000")
        min_payroll_expr = rules.get("officer_min_payroll", "15600")

        try:
            max_val = _D(str(
                self._eval_editable_rule("officer_max_payroll", max_payroll_expr, {})
                or "52000"
            ))
        except Exception:
            max_val = _D("52000")

        try:
            min_val = _D(str(
                self._eval_editable_rule("officer_min_payroll", min_payroll_expr, {})
                or "15600"
            ))
        except Exception:
            min_val = _D("15600")

        # Only apply officer bounds when owner_status == "Included"
        if ctx.owner_status != "Included":
            return OfficerFinding(officer_within_bounds=True, officer_note=None)

        reported = ctx.actual_payroll_reported or _D("0")

        if reported > max_val:
            return OfficerFinding(
                officer_within_bounds=False,
                officer_note=(
                    f"Officer payroll ${reported:,.2f} exceeds the carrier maximum "
                    f"of ${max_val:,.2f}. Premium should be calculated using ${max_val:,.2f}."
                ),
            )
        if reported < min_val:
            return OfficerFinding(
                officer_within_bounds=False,
                officer_note=(
                    f"Officer payroll ${reported:,.2f} is below the carrier minimum "
                    f"of ${min_val:,.2f}. Premium should be calculated using ${min_val:,.2f}."
                ),
            )

        return OfficerFinding(officer_within_bounds=True, officer_note=None)

    # ── Step 5 — Frequency check (EDITABLE) ──────────────────────────────────

    def check_frequency(
        self,
        ctx: CalculationContext,
        rules: dict[str, str],
    ) -> FrequencyFinding:
        """
        Computes submission frequency metrics using carrier-configured rules.

        freq_cycle_* rules: carrier can adjust cycle lengths (e.g. 28 instead
          of 30 for monthly cycles in leap-year states).

        completion_ratio rule: how far through the policy term (days_elapsed/policy_days).
          Default: "days_elapsed / policy_days if policy_days != 0 else None"

        expected_submissions rule: how many payrolls should exist.
          Default: "policy_days / cycle_days if cycle_days != 0 else None"

        submission_rate rule: actual vs expected as a percentage.
          Default: "submitted_count / expected_submissions * 100 if expected_submissions != 0 else None"
        """
        # ── Step 1: resolve cycle_days from carrier freq rules ────────────────
        freq_map: dict[str, int] = {
            "Weekly":       int(self._eval_editable_rule(
                "freq_cycle_weekly", rules.get("freq_cycle_weekly", "7"), {}) or 7),
            "Bi-Weekly":    int(self._eval_editable_rule(
                "freq_cycle_biweekly", rules.get("freq_cycle_biweekly", "14"), {}) or 14),
            "Semi-Monthly": int(self._eval_editable_rule(
                "freq_cycle_semimonthly", rules.get("freq_cycle_semimonthly", "15"), {}) or 15),
            "Monthly":      int(self._eval_editable_rule(
                "freq_cycle_monthly", rules.get("freq_cycle_monthly", "30"), {}) or 30),
        }
        cycle_days = freq_map.get(ctx.payment_frequency or "", 30)

        if ctx.effective_date is None or ctx.expiration_date is None:
            return FrequencyFinding(expected_submissions=None, submission_rate=None, cycle_days=cycle_days)

        policy_days   = (ctx.expiration_date - ctx.effective_date).days
        today         = date.today()
        days_elapsed  = (today - ctx.effective_date).days if ctx.effective_date else 0

        if policy_days <= 0 or cycle_days <= 0:
            return FrequencyFinding(expected_submissions=None, submission_rate=None, cycle_days=cycle_days)

        # ── Step 2: completion_ratio via carrier rule ─────────────────────────
        cr_expr = rules.get(
            "completion_ratio",
            "days_elapsed / policy_days if policy_days != 0 else None",
        )
        cr_ctx: dict[str, Any] = {
            "days_elapsed": days_elapsed,
            "policy_days":  policy_days,
        }
        raw_cr = self._eval_editable_rule("completion_ratio", cr_expr, cr_ctx)

        # ── Step 3: expected_submissions via carrier rule ─────────────────────
        exp_expr = rules.get(
            "expected_submissions",
            "policy_days / cycle_days if cycle_days != 0 else None",
        )
        exp_ctx: dict[str, Any] = {
            "policy_days": policy_days,
            "cycle_days":  cycle_days,
        }
        raw_exp = self._eval_editable_rule("expected_submissions", exp_expr, exp_ctx)
        expected = max(1, int(raw_exp)) if raw_exp is not None else max(1, policy_days // cycle_days)

        # ── Step 4: submission_rate via carrier rule ──────────────────────────
        rate_expr = rules.get(
            "submission_rate",
            "submitted_count / expected_submissions * 100 if expected_submissions != 0 else None",
        )
        rate_ctx: dict[str, Any] = {
            "submitted_count":      ctx.submitted_count,
            "expected_submissions": expected,
        }
        raw_rate = self._eval_editable_rule("submission_rate", rate_expr, rate_ctx)
        try:
            rate = _D(str(raw_rate)) if raw_rate is not None else None
        except Exception:
            rate = None

        return FrequencyFinding(
            expected_submissions=expected,
            submission_rate=rate,
            cycle_days=cycle_days,
        )

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

        # Evaluate high threshold via carrier rule.
        # The OR fallback is intentionally REMOVED — the rule expression is now
        # authoritative. If the carrier has set risk_threshold_high to
        # "abs(variance_pct) > 0.15", that 15% threshold governs, not 30%.
        # Only falls back to 30% when evaluation returns None (syntax error etc.)
        high_expr = rules.get("risk_threshold_high", "abs(variance_pct) > 0.30")
        high_eval = self._eval_editable_rule("risk_threshold_high", high_expr, eval_ctx)
        if high_eval is not None:
            pct_exceeded_high = bool(high_eval)
        else:
            # Expression failed to evaluate — use hardcoded 30% safety fallback
            pct_exceeded_high = variance_pct is not None and abs(variance_pct) > _D("0.30")
            logger.warning(
                "calc.risk.high_eval_failed",
                expression=high_expr,
                fallback="abs(variance_pct) > 0.30",
            )

        # Evaluate medium threshold via carrier rule — same authoritative pattern.
        med_expr = rules.get("risk_threshold_medium", "abs(variance_pct) > 0.30")
        med_eval = self._eval_editable_rule("risk_threshold_medium", med_expr, eval_ctx)
        if med_eval is not None:
            pct_exceeded_med = bool(med_eval)
        else:
            pct_exceeded_med = variance_pct is not None and abs(variance_pct) > _D("0.30")
            logger.warning(
                "calc.risk.med_eval_failed",
                expression=med_expr,
                fallback="abs(variance_pct) > 0.30",
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
        officer: Optional["OfficerFinding"] = None,
    ) -> None:
        """
        Updates the policy row with:
          - risk_level (from assess_risk — driven by carrier risk threshold rules)
          - audit_status = 'In-Review'
          - officer_note (optional, when officer payroll breaches carrier limits)

        The officer_note is stored only when the policies table has an
        officer_note column (added in a later migration). Written gracefully
        so older DB schemas without the column still work.
        """
        await db.execute(
            text(
                "UPDATE policies "
                "SET risk_level = :risk, audit_status = 'In-Review' "
                "WHERE policy_id = :pid"
            ),
            {"risk": risk.risk_level, "pid": policy_id},
        )

        # Write officer note when officer payroll is out of carrier-defined bounds
        if officer is not None and not officer.officer_within_bounds and officer.officer_note:
            try:
                await db.execute(
                    text(
                        "UPDATE policies SET officer_note = :note "
                        "WHERE policy_id = :pid"
                    ),
                    {"note": officer.officer_note, "pid": policy_id},
                )
            except Exception:
                # Column doesn't exist yet — ignore gracefully
                await db.rollback()

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
        rules: Optional[dict[str, str]] = None,
    ) -> None:
        # UPDATE by policy_id only — not by ingestion_run_id.
        # The premium_variance row may have been created by a DIFFERENT run
        # (e.g., the payroll file run) than the one that triggered the calc engine.
        # Using MAX(pv_id) ensures we always find and update the correct row.
        #
        # Also compute variance_pct here directly from the DB values as a safety net,
        # in case the context builder got different est/actual than what's stored.
        pv_lookup = await db.execute(
            text("SELECT pv_id, est_premium_end, actual_premium FROM premium_variance "
                 "WHERE policy_id = :pid ORDER BY pv_id DESC LIMIT 1"),
            {"pid": policy_id},
        )
        pv_db_row = pv_lookup.fetchone()

        # ── variance_pct: use the value already computed by calc_premium_variance()
        # which evaluated the carrier-configured rule expression via simpleeval.
        #
        # IMPORTANT: do NOT recompute with hardcoded arithmetic here.
        # The carrier may have set a custom expression (e.g. est_premium_end /
        # variance_amount) and recalculating with (actual - est) / est would
        # silently overwrite their formula's result every time.
        #
        # pv.variance_pct comes from calc_premium_variance(ctx, rules=rules) which
        # already evaluated the ACTIVE rule expression for this carrier.
        # Use it directly.  Only fall back to the arithmetic default if
        # pv.variance_pct is None AND no rule expression produced a value
        # (e.g. est_premium_end == 0 in the default formula).
        final_variance_pct: Optional[float] = None

        if pv.variance_pct is not None:
            # Rule expression produced a value — use it as-is.
            final_variance_pct = float(pv.variance_pct)
        elif pv_db_row and pv_db_row[1] and pv_db_row[2]:
            # variance_pct is None (e.g. est_premium_end == 0 so rule returned None).
            # Re-read DB values as a last-resort fallback — but still evaluate
            # via the carrier rule rather than hardcoded arithmetic.
            try:
                est_db  = _D(str(pv_db_row[1]))
                act_db  = _D(str(pv_db_row[2]))
                var_db  = act_db - est_db
                pct_expr = (rules or {}).get(
                    "variance_pct",
                    "variance_amount / est_premium_end if est_premium_end != 0 else None",
                )
                fallback_ctx: dict[str, Any] = {
                    "variance_amount":  float(var_db),
                    "est_premium_end":  float(est_db),
                    "actual_premium":   float(act_db),
                }
                raw = self._eval_editable_rule("variance_pct", pct_expr, fallback_ctx)
                if raw is not None:
                    final_variance_pct = float(_D(str(raw)))
            except (DivisionByZero, InvalidOperation, Exception):
                pass

        if pv_db_row:
            await db.execute(
                text(
                    "UPDATE premium_variance "
                    "SET variance_pct = :pct "
                    "WHERE pv_id = :pv_id"
                ),
                {"pct": final_variance_pct, "pv_id": pv_db_row[0]},
            )
        await db.execute(
            text(
                "UPDATE payroll_variance_policy "
                "SET reported_pct = :rpct, classified_pct = :cpct "
                "WHERE policy_id = :pid AND carrier_id = :cid "
                "  AND ingestion_run_id = (SELECT MAX(ingestion_run_id) FROM payroll_variance_policy "
                "                          WHERE policy_id = :pid AND ingestion_run_id > 0)"
            ),
            {
                "rpct": float(pvp.reported_pct) if pvp.reported_pct is not None else None,
                "cpct": float(pvp.classified_pct) if pvp.classified_pct is not None else None,
                "pid": policy_id,
                "cid": carrier_id,
            },
        )

        # ── class_reported_pct and class_classified_pct per class-code row ────
        # Evaluate the carrier-configured expressions against each
        # payroll_variance_class row and write results back.
        if rules:
            cr_pct_expr = rules.get(
                "class_reported_pct",
                "actual_reported / est_payroll if est_payroll != 0 else None",
            )
            cc_pct_expr = rules.get(
                "class_classified_pct",
                "actual_classified / est_payroll if est_payroll != 0 else None",
            )

            pvc_rows_result = await db.execute(
                text(
                    "SELECT pvc_id, est_payroll, actual_reported, actual_classified "
                    "FROM payroll_variance_class "
                    "WHERE policy_id = :pid AND carrier_id = :cid "
                    "  AND ingestion_run_id = :rid"
                ),
                {"pid": policy_id, "cid": carrier_id, "rid": ingestion_run_id},
            )
            pvc_rows = pvc_rows_result.fetchall()

            for pvc_row in pvc_rows:
                pvc_id, est_p, actual_r, actual_c = pvc_row
                eval_ctx: dict[str, Any] = {
                    "est_payroll":      float(_D(str(est_p))) if est_p else 0.0,
                    "actual_reported":  float(_D(str(actual_r))) if actual_r else 0.0,
                    "actual_classified": float(_D(str(actual_c))) if actual_c else 0.0,
                }
                raw_cr  = self._eval_editable_rule("class_reported_pct",   cr_pct_expr, eval_ctx)
                raw_cc  = self._eval_editable_rule("class_classified_pct",  cc_pct_expr, eval_ctx)
                try:
                    cr_val = float(_D(str(raw_cr))) if raw_cr is not None else None
                    cc_val = float(_D(str(raw_cc))) if raw_cc is not None else None
                except Exception:
                    cr_val = cc_val = None

                await db.execute(
                    text(
                        "UPDATE payroll_variance_class "
                        "SET reported_pct = :rpct, classified_pct = :cpct "
                        "WHERE pvc_id = :pvc_id"
                    ),
                    {"rpct": cr_val, "cpct": cc_val, "pvc_id": pvc_id},
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