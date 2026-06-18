from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.facts import PremiumVariance


@dataclass
class PremiumVarianceRow:
    est_premium_end: Decimal
    actual_premium: Decimal
    variance_amount: Decimal
    variance_pct: Optional[Decimal]
    as_of_date: date


@dataclass
class PayrollVariancePolicyRow:
    est_payroll: Decimal
    actual_payroll_reported: Decimal
    reported_over_under: Decimal
    reported_pct: Optional[Decimal]
    actual_payroll_classified: Decimal
    classified_over_under: Decimal
    classified_pct: Optional[Decimal]
    as_of_date: date


@dataclass
class ClassCodeVarianceRow:
    class_code: str
    description: Optional[str]
    state_code: str
    est_payroll: Decimal
    actual_reported: Decimal
    reported_over_under: Decimal
    reported_pct: Optional[Decimal]
    actual_classified: Decimal
    classified_over_under: Decimal
    classified_pct: Optional[Decimal]


@dataclass
class ZeroPayrollRow:
    zp_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    report_date: Optional[date]
    payroll_frequency: Optional[str]
    ingestion_run_id: int


@dataclass
class MissingPayrollRow:
    mp_id: int
    policyholder_name: Optional[str]
    policy_number: Optional[str]
    state_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    payroll_frequency: Optional[str]
    days_since_last_run: Optional[int]
    ingestion_run_id: int


@dataclass
class SubmissionMetricsRow:
    actual_received: int
    zero_payroll_count: int
    missing_payroll_count: int
    expected_submissions: Optional[int]
    submission_rate: Optional[Decimal]


class VarianceRepository(BaseRepository[PremiumVariance]):
    """Data-access methods for all fact tables (variance, zero, missing payroll)."""

    async def get_premium_variance(
        self, policy_id: int, carrier_id: int
    ) -> Optional[PremiumVarianceRow]:
        """Latest premium variance row for a policy."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT est_premium_end, actual_premium, variance_amount,
                       variance_pct, as_of_date
                FROM premium_variance
                WHERE policy_id = :pid AND carrier_id = :cid
                ORDER BY ingestion_run_id DESC
                LIMIT 1
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return PremiumVarianceRow(
            est_premium_end=row[0],
            actual_premium=row[1],
            variance_amount=row[2],
            variance_pct=row[3],
            as_of_date=row[4],
        )

    async def get_payroll_variance_policy(
        self, policy_id: int, carrier_id: int
    ) -> Optional[PayrollVariancePolicyRow]:
        """Latest policy-level payroll variance row."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT est_payroll, actual_payroll_reported, reported_over_under,
                       reported_pct, actual_payroll_classified, classified_over_under,
                       classified_pct, as_of_date
                FROM payroll_variance_policy
                WHERE policy_id = :pid AND carrier_id = :cid
                ORDER BY ingestion_run_id DESC
                LIMIT 1
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return PayrollVariancePolicyRow(
            est_payroll=row[0],
            actual_payroll_reported=row[1],
            reported_over_under=row[2],
            reported_pct=row[3],
            actual_payroll_classified=row[4],
            classified_over_under=row[5],
            classified_pct=row[6],
            as_of_date=row[7],
        )

    async def list_class_code_variance(
        self, policy_id: int, carrier_id: int
    ) -> list[ClassCodeVarianceRow]:
        """All class-code-level variance rows for the latest run."""
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT
                    cc.code, cc.description, pvc.state_code,
                    pvc.est_payroll, pvc.actual_reported, pvc.reported_over_under,
                    pvc.reported_pct, pvc.actual_classified, pvc.classified_over_under,
                    pvc.classified_pct
                FROM payroll_variance_class pvc
                JOIN public.class_codes cc ON cc.class_code_id = pvc.class_code_id
                WHERE pvc.policy_id = :pid
                  AND pvc.carrier_id = :cid
                  AND pvc.ingestion_run_id = (
                      SELECT MAX(run_id) FROM ingestion_runs
                      WHERE carrier_id = :cid AND status = 'complete'
                  )
                ORDER BY pvc.state_code, cc.code
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        return [
            ClassCodeVarianceRow(
                class_code=r[0],
                description=r[1],
                state_code=r[2],
                est_payroll=r[3],
                actual_reported=r[4],
                reported_over_under=r[5],
                reported_pct=r[6],
                actual_classified=r[7],
                classified_over_under=r[8],
                classified_pct=r[9],
            )
            for r in result.fetchall()
        ]

    async def list_zero_payroll(
        self, policy_id: int, carrier_id: int
    ) -> list[ZeroPayrollRow]:
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT zp_id, policyholder_name, policy_number, state_code,
                       report_date, payroll_frequency, ingestion_run_id
                FROM zero_payroll
                WHERE policy_id = :pid AND carrier_id = :cid
                ORDER BY report_date DESC NULLS LAST
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        return [
            ZeroPayrollRow(
                zp_id=r[0],
                policyholder_name=r[1],
                policy_number=r[2],
                state_code=r[3],
                report_date=r[4],
                payroll_frequency=r[5],
                ingestion_run_id=r[6],
            )
            for r in result.fetchall()
        ]

    async def list_missing_payroll(
        self, policy_id: int, carrier_id: int
    ) -> list[MissingPayrollRow]:
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT mp_id, policyholder_name, policy_number, state_code,
                       period_start, period_end, payroll_frequency,
                       days_since_last_run, ingestion_run_id
                FROM missing_payroll
                WHERE policy_id = :pid AND carrier_id = :cid
                ORDER BY period_start DESC NULLS LAST
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        return [
            MissingPayrollRow(
                mp_id=r[0],
                policyholder_name=r[1],
                policy_number=r[2],
                state_code=r[3],
                period_start=r[4],
                period_end=r[5],
                payroll_frequency=r[6],
                days_since_last_run=r[7],
                ingestion_run_id=r[8],
            )
            for r in result.fetchall()
        ]

    async def get_submission_metrics(
        self, policy_id: int, carrier_id: int
    ) -> SubmissionMetricsRow:
        await self._assert_carrier_accessible(carrier_id)

        received = await self._db.execute(
            text(
                "SELECT COUNT(*) FROM payroll_variance_policy "
                "WHERE policy_id = :pid AND carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        zero_ct = await self._db.execute(
            text(
                "SELECT COUNT(*) FROM zero_payroll "
                "WHERE policy_id = :pid AND carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        missing_ct = await self._db.execute(
            text(
                "SELECT COUNT(*) FROM missing_payroll "
                "WHERE policy_id = :pid AND carrier_id = :cid"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        rate_row = await self._db.execute(
            text(
                "SELECT reported_pct FROM payroll_variance_policy "
                "WHERE policy_id = :pid AND carrier_id = :cid "
                "ORDER BY ingestion_run_id DESC LIMIT 1"
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        rate_fetch = rate_row.fetchone()

        return SubmissionMetricsRow(
            actual_received=received.scalar_one() or 0,
            zero_payroll_count=zero_ct.scalar_one() or 0,
            missing_payroll_count=missing_ct.scalar_one() or 0,
            expected_submissions=None,
            submission_rate=rate_fetch[0] if rate_fetch else None,
        )
