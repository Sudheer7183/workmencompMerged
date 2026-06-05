from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis_dep
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    KpiMetrics,
    PolicyStatusDistribution,
    RiskDistribution,
    StateRiskProfile,
    TargetVarianceMetrics,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_TTL_SECONDS = 60
"""Dashboard summary is cached in Redis for 60 seconds per V9 S28."""


def _cache_key(tenant_schema: str, carrier_id: int) -> str:
    """Deterministic Redis key scoped to tenant schema + carrier."""
    return f"{tenant_schema}:dashboard:{carrier_id}"


async def _build_summary(
    carrier_id: int,
    db: AsyncSession,
) -> DashboardSummaryResponse:
    """Execute all dashboard queries and return the assembled response."""

    # ── KPI metrics (from v_dashboard_summary view) ──────────────────────────
    kpi_result = await db.execute(
        text(
            """
            SELECT
                total_book_premium,
                total_est_earned_premium,
                total_actual_earned_premium,
                total_variance_amount,
                risk_high_count,
                risk_medium_count,
                risk_low_count,
                active_policies,
                cancelled_policies
            FROM v_dashboard_summary
            WHERE carrier_id = :cid
            """
        ),
        {"cid": carrier_id},
    )
    row = kpi_result.fetchone()

    if row is None:
        return DashboardSummaryResponse(
            carrier_id=carrier_id,
            kpi=KpiMetrics(
                total_book_premium=0,
                total_est_earned_premium=0,
                total_actual_earned_premium=0,
                total_variance_amount=0,
            ),
            policy_status=PolicyStatusDistribution(active_count=0, cancelled_count=0),
            risk_distribution=RiskDistribution(
                high_count=0, medium_count=0, low_count=0, unassigned_count=0
            ),
            state_risk_profiles=[],
            target_variance=TargetVarianceMetrics(
                policies_above_threshold=0,
                total_variance_above_threshold=0,
            ),
        )

    kpi = KpiMetrics(
        total_book_premium=row[0] or 0,
        total_est_earned_premium=row[1] or 0,
        total_actual_earned_premium=row[2] or 0,
        total_variance_amount=row[3] or 0,
    )
    risk_dist = RiskDistribution(
        high_count=row[4] or 0,
        medium_count=row[5] or 0,
        low_count=row[6] or 0,
        unassigned_count=0,
    )
    status_dist = PolicyStatusDistribution(
        active_count=row[7] or 0,
        cancelled_count=row[8] or 0,
    )

    # ── Unassigned risk count ─────────────────────────────────────────────────
    total_pol_result = await db.execute(
        text("SELECT COUNT(*) FROM policies WHERE carrier_id = :cid AND deleted_at IS NULL"),
        {"cid": carrier_id},
    )
    total_policies: int = total_pol_result.scalar_one() or 0
    assigned = risk_dist.high_count + risk_dist.medium_count + risk_dist.low_count
    risk_dist = risk_dist.model_copy(update={"unassigned_count": max(0, total_policies - assigned)})

    # ── State & Risk grouped bar ──────────────────────────────────────────────
    state_result = await db.execute(
        text(
            """
            SELECT
                state_code,
                COUNT(*) FILTER (WHERE risk_level = 'High')    AS high_count,
                COUNT(*) FILTER (WHERE risk_level = 'Medium')  AS medium_count,
                COUNT(*) FILTER (WHERE risk_level = 'Low')     AS low_count
            FROM policies
            WHERE carrier_id = :cid AND deleted_at IS NULL AND state_code IS NOT NULL
            GROUP BY state_code
            ORDER BY state_code
            """
        ),
        {"cid": carrier_id},
    )
    state_profiles = [
        StateRiskProfile(
            state_code=sr[0],
            high_count=sr[1] or 0,
            medium_count=sr[2] or 0,
            low_count=sr[3] or 0,
        )
        for sr in state_result.fetchall()
    ]

    # ── Target variance 2-card callout ────────────────────────────────────────
    target_result = await db.execute(
        text(
            """
            SELECT
                COUNT(DISTINCT pv.policy_id)         AS policies_above,
                COALESCE(SUM(pv.variance_amount), 0) AS total_above
            FROM premium_variance pv
            JOIN policies p ON p.policy_id = pv.policy_id
            WHERE pv.carrier_id = :cid
              AND p.deleted_at IS NULL
              AND pv.est_premium_end > 0
              AND ABS(pv.variance_amount / pv.est_premium_end) > 0.30
              AND pv.ingestion_run_id = (
                  SELECT MAX(ir.run_id)
                  FROM ingestion_runs ir
                  WHERE ir.carrier_id = :cid AND ir.status = 'complete'
              )
            """
        ),
        {"cid": carrier_id},
    )
    t_row = target_result.fetchone()
    target = TargetVarianceMetrics(
        policies_above_threshold=t_row[0] if t_row else 0,
        total_variance_above_threshold=t_row[1] if t_row else 0,
    )

    return DashboardSummaryResponse(
        carrier_id=carrier_id,
        kpi=kpi,
        policy_status=status_dist,
        risk_distribution=risk_dist,
        state_risk_profiles=state_profiles,
        target_variance=target,
    )


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Dashboard KPIs, distributions, and target variance metrics",
)
async def get_dashboard_summary(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep), # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> DashboardSummaryResponse:
    """
    Returns all data needed to render the Dashboard screen.

    Results are cached in Redis for 60 seconds per tenant schema + carrier_id
    (V9 S28). The cache key encodes the tenant schema so cross-tenant isolation
    is maintained even if carrier_ids collide across schemas.
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    # Resolve the tenant schema from the current DB session search_path.
    # TenantMiddleware sets it; we read it back here to build a scoped key.
    schema_result = await db.execute(text("SELECT current_schema()"))
    tenant_schema: str = schema_result.scalar_one() or "public"

    cache_key = _cache_key(tenant_schema, carrier_id)

    # ── Cache read ────────────────────────────────────────────────────────────
    try:
        cached = await redis.get(cache_key)
        if cached:
            logger.debug("Dashboard cache HIT: %s", cache_key)
            return DashboardSummaryResponse.model_validate_json(cached)
    except Exception as exc:  # Redis unavailable — degrade gracefully
        logger.warning("Dashboard cache read failed: %s", exc)

    # ── Cache miss: query DB ──────────────────────────────────────────────────
    logger.debug("Dashboard cache MISS: %s", cache_key)
    response = await _build_summary(carrier_id, db)

    # ── Cache write ───────────────────────────────────────────────────────────
    try:
        await redis.set(
            cache_key,
            response.model_dump_json(),
            ex=_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("Dashboard cache write failed: %s", exc)

    return response
