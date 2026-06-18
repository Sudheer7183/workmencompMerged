from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import PremiumVariance
from app.models.policies import Policyholder, Policy
from app.repositories.base import BaseRepository


@dataclass
class PolicyRow:
    """
    Flat projection used by the Policies List endpoint.
    All 11 DataTable columns.
    """

    policy_id: int
    policy_number: str
    insured_name: str
    state_code: Optional[str]
    effective_date: Optional[date]
    policy_status: str
    est_premium: Optional[Decimal]
    variance_amount: Optional[Decimal]
    variance_pct: Optional[Decimal]
    risk_level: Optional[str]
    audit_status: str


@dataclass
class PolicyDetailRow:
    """Full policy record for the Policy Detail meta card."""

    policy_id: int
    policy_number: str
    insured_name: str
    fein: Optional[str]
    state_code: Optional[str]
    effective_date: Optional[date]
    expiration_date: Optional[date]
    cancellation_date: Optional[date]
    policy_status: str
    payment_frequency: Optional[str]
    owner_status: Optional[str]
    audit_status: str
    total_est_payroll: Optional[Decimal]
    engine_on: bool
    latest_run_id: Optional[int]


class PolicyRepository(BaseRepository[Policy]):
    """Data-access methods for policies, policyholders, and basic variance joins."""

    async def list_paginated(
        self,
        carrier_id: int,
        page: int = 1,
        page_size: int = 25,
        status_filter: Optional[str] = None,
        risk_filter: Optional[str] = None,
    ) -> tuple[list[PolicyRow], int]:
        """
        Returns (rows, total_count) for the Policies List DataTable.
        Joins to premium_variance (latest run) for variance columns.
        """
        await self._assert_carrier_accessible(carrier_id)

        where_clauses = [
            "p.carrier_id = :cid",
            "p.deleted_at IS NULL",
        ]
        params: dict = {
            "cid": carrier_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }

        if status_filter:
            where_clauses.append("p.policy_status = :status")
            params["status"] = status_filter
        if risk_filter:
            where_clauses.append("p.risk_level = :risk")
            params["risk"] = risk_filter

        where_sql = " AND ".join(where_clauses)

        count_result = await self._db.execute(
            text(f"SELECT COUNT(*) FROM policies p WHERE {where_sql}"), params
        )
        total: int = count_result.scalar_one() or 0

        rows_result = await self._db.execute(
            text(
                f"""
                SELECT
                    p.policy_id,
                    p.policy_number,
                    ph.name                 AS insured_name,
                    p.state_code,
                    p.effective_date,
                    p.policy_status,
                    pv.est_premium_end      AS est_premium,
                    pv.variance_amount,
                    pv.variance_pct,
                    p.risk_level,
                    p.audit_status
                FROM policies p
                JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id
                LEFT JOIN premium_variance pv
                    ON pv.policy_id = p.policy_id
                    AND pv.carrier_id = p.carrier_id
                    AND pv.ingestion_run_id = (
                        SELECT MAX(ir.run_id)
                        FROM ingestion_runs ir
                        WHERE ir.carrier_id = p.carrier_id
                          AND ir.status = 'complete'
                    )
                WHERE {where_sql}
                ORDER BY p.policy_id
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )

        rows = [
            PolicyRow(
                policy_id=r[0],
                policy_number=r[1],
                insured_name=r[2],
                state_code=r[3],
                effective_date=r[4],
                policy_status=r[5],
                est_premium=r[6],
                variance_amount=r[7],
                variance_pct=r[8],
                risk_level=r[9],
                audit_status=r[10],
            )
            for r in rows_result.fetchall()
        ]

        return rows, total

    async def get_detail(
        self, policy_id: int, carrier_id: int
    ) -> Optional[PolicyDetailRow]:
        """
        Returns the full Policy Detail meta card data.
        Resolves engine_on from carrier_calc_config.
        """
        await self._assert_carrier_accessible(carrier_id)

        result = await self._db.execute(
            text(
                """
                SELECT
                    p.policy_id, p.policy_number,
                    ph.name, ph.fein,
                    p.state_code, p.effective_date, p.expiration_date,
                    p.cancellation_date, p.policy_status, p.payment_frequency,
                    p.owner_status, p.audit_status, p.total_est_payroll
                FROM policies p
                JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id
                WHERE p.policy_id = :pid
                  AND p.carrier_id = :cid
                  AND p.deleted_at IS NULL
                """
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        row = result.fetchone()
        if row is None:
            return None

        # Resolve engine_on from carrier_calc_config
        ccc = await self._db.execute(
            text(
                "SELECT use_calculation_engine FROM carrier_calc_config "
                "WHERE carrier_id = :cid"
            ),
            {"cid": carrier_id},
        )
        ccc_row = ccc.fetchone()
        engine_on: bool = bool(ccc_row[0]) if ccc_row else True

        # Latest completed run
        run_result = await self._db.execute(
            text(
                "SELECT MAX(run_id) FROM ingestion_runs "
                "WHERE carrier_id = :cid AND status = 'complete'"
            ),
            {"cid": carrier_id},
        )
        latest_run_id: Optional[int] = run_result.scalar_one()

        return PolicyDetailRow(
            policy_id=row[0],
            policy_number=row[1],
            insured_name=row[2],
            fein=row[3],
            state_code=row[4],
            effective_date=row[5],
            expiration_date=row[6],
            cancellation_date=row[7],
            policy_status=row[8],
            payment_frequency=row[9],
            owner_status=row[10],
            audit_status=row[11],
            total_est_payroll=row[12],
            engine_on=engine_on,
            latest_run_id=latest_run_id,
        )
