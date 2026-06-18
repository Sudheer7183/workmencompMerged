from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenancy import PublicCarrier
from app.repositories.base import BaseRepository


@dataclass
class DashboardSummaryRow:
    """All columns returned by v_dashboard_summary + extras computed here."""

    carrier_id: int
    total_book_premium: Decimal
    total_est_earned_premium: Decimal
    total_actual_earned_premium: Decimal
    total_variance_amount: Decimal
    risk_high_count: int
    risk_medium_count: int
    risk_low_count: int
    active_count: int
    cancelled_count: int


@dataclass
class StateRiskRow:
    state_code: str
    high_count: int
    medium_count: int
    low_count: int


@dataclass
class TargetVarianceRow:
    policies_above_threshold: int
    total_variance_above_threshold: Decimal
    threshold_pct: int


class CarrierRepository(BaseRepository[PublicCarrier]):
    """Data-access methods for carrier-level dashboard aggregations."""

    async def get_dashboard_summary(
        self, carrier_id: int
    ) -> Optional[DashboardSummaryRow]:
        """Reads v_dashboard_summary for one carrier."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT
                    total_book_premium, total_est_earned_premium,
                    total_actual_earned_premium, total_variance_amount,
                    risk_high_count, risk_medium_count, risk_low_count,
                    active_policies, cancelled_policies
                FROM v_dashboard_summary
                WHERE carrier_id = :cid
                """
            ),
            {"cid": carrier_id},
        )
        row = result.fetchone()
        if row is None:
            return None

        return DashboardSummaryRow(
            carrier_id=carrier_id,
            total_book_premium=row[0] or Decimal("0"),
            total_est_earned_premium=row[1] or Decimal("0"),
            total_actual_earned_premium=row[2] or Decimal("0"),
            total_variance_amount=row[3] or Decimal("0"),
            risk_high_count=row[4] or 0,
            risk_medium_count=row[5] or 0,
            risk_low_count=row[6] or 0,
            active_count=row[7] or 0,
            cancelled_count=row[8] or 0,
        )

    async def list_state_risk_profiles(
        self, carrier_id: int
    ) -> list[StateRiskRow]:
        """Grouped state + risk distribution for the grouped bar chart."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT
                    state_code,
                    COUNT(*) FILTER (WHERE risk_level = 'High')   AS high_count,
                    COUNT(*) FILTER (WHERE risk_level = 'Medium') AS med_count,
                    COUNT(*) FILTER (WHERE risk_level = 'Low')    AS low_count
                FROM policies
                WHERE carrier_id = :cid
                  AND deleted_at IS NULL
                  AND state_code IS NOT NULL
                GROUP BY state_code
                ORDER BY state_code
                """
            ),
            {"cid": carrier_id},
        )
        return [
            StateRiskRow(
                state_code=r[0],
                high_count=r[1] or 0,
                medium_count=r[2] or 0,
                low_count=r[3] or 0,
            )
            for r in result.fetchall()
        ]

    async def get_target_variance(
        self, carrier_id: int, threshold_pct: int = 30
    ) -> TargetVarianceRow:
        """Policies above the variance threshold — uses GENERATED variance_amount."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT
                    COUNT(DISTINCT pv.policy_id),
                    COALESCE(SUM(pv.variance_amount), 0)
                FROM premium_variance pv
                JOIN policies p ON p.policy_id = pv.policy_id
                WHERE pv.carrier_id = :cid
                  AND p.deleted_at IS NULL
                  AND pv.est_premium_end > 0
                  AND ABS(pv.variance_amount / pv.est_premium_end) > :threshold
                  AND pv.ingestion_run_id = (
                      SELECT MAX(ir.run_id)
                      FROM ingestion_runs ir
                      WHERE ir.carrier_id = :cid AND ir.status = 'complete'
                  )
                """
            ),
            {"cid": carrier_id, "threshold": Decimal(threshold_pct) / Decimal("100")},
        )
        row = result.fetchone()
        return TargetVarianceRow(
            policies_above_threshold=row[0] if row else 0,
            total_variance_above_threshold=row[1] if row else Decimal("0"),
            threshold_pct=threshold_pct,
        )
