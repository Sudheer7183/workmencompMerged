



from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.schemas.policies import PolicyDetailResponse, PolicyListItem, PolicyListResponse, PolicyMetaCard
from app.schemas.responses import (
    ClassCodeVarianceResponse,
    ClassCodeVarianceRow,
    MissingPayrollResponse,
    MissingPayrollRow,
    PayrollMetricsResponse,
    PayrollVariancePolicyResponse,
    PremiumVarianceResponse,
    ZeroPayrollResponse,
    ZeroPayrollRow,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared security check — used by every endpoint below
# ---------------------------------------------------------------------------


async def _check(
    carrier_id: int,
    request: Request,
    token: TokenPayload,
    db: AsyncSession,
    role: Role = Role.REVIEWER,
) -> None:
    verify_role(role, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)


# ---------------------------------------------------------------------------
# 1. Policy list
# ---------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=PolicyListResponse,
    summary="Paginated list of policies with variance columns",
)
async def list_policies(
    carrier_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    risk_filter: str | None = Query(None, alias="risk"),
    state_filter: str | None = Query(None, alias="state"),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> PolicyListResponse:
    await _check(carrier_id, request, token, db)

    offset = (page - 1) * page_size

    # Build WHERE clause fragments
    where = ["p.carrier_id = :cid", "p.deleted_at IS NULL"]
    params: dict = {"cid": carrier_id, "limit": page_size, "offset": offset}
    if status_filter:
        where.append("p.policy_status = :status")
        params["status"] = status_filter
    if risk_filter:
        where.append("p.risk_level = :risk")
        params["risk"] = risk_filter
    if state_filter:
        where.append("p.state_code = :state")
        params["state"] = state_filter

    where_clause = " AND ".join(where)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM policies p WHERE {where_clause}"),
        params,
    )
    total: int = count_result.scalar_one() or 0

    rows_result = await db.execute(
        text(
            f"""
            SELECT
                p.policy_id,
                p.policy_number,
                ph.name                          AS insured_name,
                p.state_code,
                p.effective_date,
                p.policy_status,
                pv.est_premium_end               AS est_premium,
                pv.actual_premium,
                pv.variance_amount,
                CASE
                    WHEN pv.variance_pct IS NOT NULL THEN pv.variance_pct
                    WHEN pv.est_premium_end IS NOT NULL
                         AND pv.variance_amount IS NOT NULL
                         AND pv.est_premium_end <> 0
                    THEN pv.variance_amount / pv.est_premium_end
                    ELSE NULL
                END                              AS variance_pct,
                p.risk_level,
                p.audit_status
            FROM policies p
            JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id
            LEFT JOIN premium_variance pv ON pv.pv_id = (
                SELECT MAX(pv2.pv_id)
                FROM premium_variance pv2
                WHERE pv2.policy_id = p.policy_id
            )
            WHERE {where_clause}
            ORDER BY p.policy_id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    items = [
        PolicyListItem(
            policy_id=r[0],
            policy_number=r[1],
            insured_name=r[2],
            state_code=r[3],
            effective_date=r[4],
            policy_status=r[5],
            est_premium=r[6],
            # r[7] = actual_premium (not used in list but in SELECT)
            variance_amount=r[8],
            variance_pct=r[9],
            risk_level=r[10],
            audit_status=r[11],
        )
        for r in rows_result.fetchall()
    ]

    return PolicyListResponse(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# 2. Policy detail
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}",
    response_model=PolicyDetailResponse,
    summary="Policy meta card + engine_on flag",
)
async def get_policy_detail(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> PolicyDetailResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
        text(
            """
            SELECT
                p.policy_id, p.policy_number,
                ph.name, ph.fein,
                p.state_code, p.effective_date, p.expiration_date,
                p.cancellation_date, p.policy_status, p.payment_frequency,
                p.owner_status, p.audit_status, p.total_est_payroll,
                p.premium_written
            FROM policies p
            JOIN policyholders ph ON ph.policyholder_id = p.policyholder_id
            WHERE p.policy_id = :pid AND p.carrier_id = :cid AND p.deleted_at IS NULL
            """
        ),
        {"pid": policy_id, "cid": carrier_id},
    )
    row = result.fetchone()
    if row is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")

    # Latest completed run for THIS specific policy.
    # All four fact tables are searched so display_only policies (which may only
    # have zero_payroll or missing_payroll rows) also resolve correctly.
    run_result = await db.execute(
        text(
            """
            SELECT MAX(ir.run_id)
            FROM ingestion_runs ir
            WHERE ir.carrier_id = :cid
              AND ir.status IN ('complete', 'partial')
              AND (
                  EXISTS (
                      SELECT 1 FROM premium_variance pv
                      WHERE pv.ingestion_run_id = ir.run_id AND pv.policy_id = :pid
                  )
                  OR EXISTS (
                      SELECT 1 FROM payroll_variance_policy pvp
                      WHERE pvp.ingestion_run_id = ir.run_id AND pvp.policy_id = :pid
                  )
                  OR EXISTS (
                      SELECT 1 FROM zero_payroll zp
                      WHERE zp.ingestion_run_id = ir.run_id AND zp.policy_id = :pid
                  )
                  OR EXISTS (
                      SELECT 1 FROM missing_payroll mp
                      WHERE mp.ingestion_run_id = ir.run_id AND mp.policy_id = :pid
                  )
              )
            """
        ),
        {"cid": carrier_id, "pid": policy_id},
    )
    latest_run_id = run_result.scalar_one()

    # Resolve engine_on:
    # True when the carrier has the calc engine enabled (carrier_calc_config)
    # OR when premium_variance data already exists for any policy in this carrier.
    # This prevents the "engine off" banner from hiding valid calculated data.
    ccc_result = await db.execute(
        text("SELECT use_calculation_engine FROM carrier_calc_config WHERE carrier_id = :cid"),
        {"cid": carrier_id},
    )
    ccc_row = ccc_result.fetchone()
    config_engine_on: bool = bool(ccc_row[0]) if ccc_row else True

    # If config says off but we have variance data, still show it (data exists → show it)
    has_variance_data = False
    if not config_engine_on:
        pv_check = await db.execute(
            text(
                "SELECT COUNT(*) FROM premium_variance pv "
                "JOIN policies p ON p.policy_id = pv.policy_id "
                "WHERE p.carrier_id = :cid"
            ),
            {"cid": carrier_id},
        )
        has_variance_data = (pv_check.scalar_one() or 0) > 0

    engine_on: bool = config_engine_on or has_variance_data

    meta = PolicyMetaCard(
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
        premium_written=row[13],
    )

    # ── Narrative: read from policies table (display_only + calc_engine). ──────
    # run_audit writes narratives per-policy directly to policies.narrative_text.
    # This is the ONLY correct store for display_only bulk sessions where one
    # ingestion run contains many policies — ingestion_runs.narrative_text holds
    # only one value per run (the first policy's narrative) and must NOT be used
    # as a fallback for display_only, as it causes cross-policy contamination.
    from app.schemas.policies import NarrativeData as _NarrativeData

    tenant_schema = request.state.tenant.schema_name
    narrative: _NarrativeData | None = None

    # Path 1 — policies.narrative_text (written by run_audit for all modes).
    # Wrapped in try/except: the column is added by an idempotent ALTER TABLE in
    # run_audit, so it may not exist yet if run_audit has never been called.
    # Schema-qualified to be robust against search_path resets between requests.
    try:
        pol_narr_result = await db.execute(
            text(
                f'SELECT narrative_text, narrative_is_fallback, '
                f'narrative_provider, narrative_generated_at::text '
                f'FROM "{tenant_schema}".policies '
                f'WHERE policy_id = :pid AND carrier_id = :cid'
            ),
            {"pid": policy_id, "cid": carrier_id},
        )
        pol_narr_row = pol_narr_result.mappings().one_or_none()

        if pol_narr_row and pol_narr_row["narrative_text"]:
            narrative = _NarrativeData(
                text=pol_narr_row["narrative_text"],
                is_fallback=bool(pol_narr_row["narrative_is_fallback"]),
                provider=pol_narr_row["narrative_provider"],
                generated_at=pol_narr_row["narrative_generated_at"],
                engine_was_off=False,
            )
    except Exception:
        # Column doesn't exist yet — narrative not generated, leave as None.
        await db.rollback()

    # Path 2 — ingestion_runs.narrative_text fallback.
    # Only used for calc_engine single-policy runs where ingestion_runs holds
    # exactly one policy's narrative per run. NEVER used for display_only mode
    # (multi-policy runs) because ingestion_runs.narrative_text is shared across
    # all policies in a run and contains only the first policy's text.
    if narrative is None and latest_run_id is not None:
        try:
            narr_result = await db.execute(
                text(
                    f'SELECT ir.narrative_text, ir.narrative_is_fallback, '
                    f'ir.narrative_provider, ir.narrative_generated_at::text, '
                    f'ir.ingestion_mode '
                    f'FROM ingestion_runs ir '
                    f'WHERE ir.run_id = :rid'
                ),
                {"rid": latest_run_id},
            )
            narr_row = narr_result.mappings().one_or_none()
            if narr_row is not None:
                # Only use ingestion_runs narrative for calc_engine runs.
                # display_only runs with multiple policies must NOT fall back here.
                is_display_only = (narr_row.get("ingestion_mode") == "display_only")
                if not is_display_only and narr_row["narrative_text"]:
                    narrative = _NarrativeData(
                        text=narr_row["narrative_text"],
                        is_fallback=bool(narr_row["narrative_is_fallback"]),
                        provider=narr_row["narrative_provider"],
                        generated_at=narr_row["narrative_generated_at"],
                        engine_was_off=not engine_on,
                    )
                elif not engine_on:
                    narrative = _NarrativeData(
                        text="",
                        is_fallback=False,
                        engine_was_off=True,
                    )
                elif not is_display_only:
                    narrative = _NarrativeData(
                        text="",
                        is_fallback=False,
                        not_attempted=True,
                    )
        except Exception:
            pass

    return PolicyDetailResponse(meta=meta, engine_on=engine_on, latest_run_id=latest_run_id, narrative=narrative)


# ---------------------------------------------------------------------------
# 3. Premium variance
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/premium-variance",
    response_model=PremiumVarianceResponse,
    summary="Premium variance for the latest completed run",
)
async def get_premium_variance(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> PremiumVarianceResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
        text(
            """
            SELECT est_premium_end, actual_premium, variance_amount, variance_pct, as_of_date
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
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No premium variance data.")

    # Compute variance_pct if NULL in DB (calc engine may not have run yet).
    # variance_pct = variance_amount / est_premium_end (stored as ratio, e.g. -0.2219)
    # NaIndicator "pct" format multiplies by 100 to display -22.2%.
    stored_variance_pct = row[3]
    if stored_variance_pct is None and row[2] is not None and row[0] is not None:
        try:
            from decimal import Decimal as _D
            est = _D(str(row[0]))
            var = _D(str(row[2]))
            stored_variance_pct = float(var / est) if est != 0 else None
        except Exception:
            stored_variance_pct = None

    return PremiumVarianceResponse(
        est_premium_end=row[0],
        actual_premium=row[1],
        variance_amount=row[2],
        variance_pct=stored_variance_pct,
        as_of_date=row[4],
    )


# ---------------------------------------------------------------------------
# 4. Payroll variance
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/payroll-variance",
    response_model=PayrollVariancePolicyResponse,
    summary="Policy-level payroll variance for the latest run",
)
async def get_payroll_variance(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> PayrollVariancePolicyResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
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
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payroll variance data.")

    return PayrollVariancePolicyResponse(
        est_payroll=row[0],
        actual_payroll_reported=row[1],
        reported_over_under=row[2],
        reported_pct=row[3],
        actual_payroll_classified=row[4],
        classified_over_under=row[5],
        classified_pct=row[6],
        as_of_date=row[7],
    )


# ---------------------------------------------------------------------------
# 5. Class-code variance
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/class-code-variance",
    response_model=ClassCodeVarianceResponse,
    summary="Class-code-level payroll variance",
)
async def get_class_code_variance(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ClassCodeVarianceResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
        text(
            """
            SELECT
                cc.code            AS class_code,
                cc.description,
                pvc.state_code,
                pvc.est_payroll,
                pvc.actual_reported,
                pvc.reported_over_under,
                pvc.reported_pct,
                pvc.actual_classified,
                pvc.classified_over_under,
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
    rows = [
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
    return ClassCodeVarianceResponse(rows=rows)


# ---------------------------------------------------------------------------
# 6. Zero payroll
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/zero-payroll",
    response_model=ZeroPayrollResponse,
    summary="Zero-wage payroll submissions for this policy",
)
async def get_zero_payroll(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ZeroPayrollResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
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
    rows = [
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
    return ZeroPayrollResponse(rows=rows, total=len(rows))


# ---------------------------------------------------------------------------
# 7. Missing payroll
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/missing-payroll",
    response_model=MissingPayrollResponse,
    summary="Missing payroll periods detected for this policy",
)
async def get_missing_payroll(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> MissingPayrollResponse:
    await _check(carrier_id, request, token, db)

    result = await db.execute(
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
    rows = [
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
    return MissingPayrollResponse(rows=rows, total=len(rows))


# ---------------------------------------------------------------------------
# 8. Submission metrics (5 pills)
# ---------------------------------------------------------------------------


@router.get(
    "/policies/{policy_id}/submission-metrics",
    response_model=PayrollMetricsResponse,
    summary="5-pill payroll submission metrics row",
)
async def get_submission_metrics(
    policy_id: int,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> PayrollMetricsResponse:
    await _check(carrier_id, request, token, db)

    # ── Reference: mock_data_api.py _parse_audit_report() + premium_agent.py ──
    #
    # From audit report Business Entity section:
    #   a_actual_payroll_sub  = expected_till_today  (calendar-based, for YTD proration)
    #   a_actual_payroll_sub2 = actual_submissions   (Number of Payroll Reports Submitted)
    #   a_expected_payroll_sub = expected_full_term  (full policy term periods)
    #
    # From premium_agent.py:
    #   missing      = max(0, a_expected_payroll_sub - a_actual_payroll_sub2)
    #   submit_rate  = a_actual_payroll_sub2 / a_expected_payroll_sub * 100
    #   received     = a_actual_payroll_sub2 (actual submissions from file)
    #
    # We store:
    #   reported_pct on the main run row = submit_rate (written during ingestion Step 10)
    #   total payroll_variance_policy rows = a_actual_payroll_sub2 (1 real + N-1 synthetic)

    # Get stored submit_rate and actual_submissions count
    pvp_result = await db.execute(
        text("""
            SELECT
                reported_pct,
                (SELECT COUNT(*) FROM payroll_variance_policy
                 WHERE policy_id = :pid AND carrier_id = :cid) AS total_rows
            FROM payroll_variance_policy
            WHERE policy_id  = :pid
              AND carrier_id = :cid
              AND ingestion_run_id = (
                    SELECT MAX(ingestion_run_id)
                    FROM payroll_variance_policy
                    WHERE policy_id = :pid AND carrier_id = :cid
                      AND ingestion_run_id > 0
              )
            LIMIT 1
        """),
        {"pid": policy_id, "cid": carrier_id},
    )
    pvp_row = pvp_result.fetchone()

    # actual_received = a_actual_payroll_sub2 = total rows written during ingestion
    # (1 real summary row + N-1 synthetic per-period rows = N total = actual_submissions)
    actual_received: int = int(pvp_row[1]) if pvp_row and pvp_row[1] else 0

    zero_result = await db.execute(
        text("SELECT COUNT(*) FROM zero_payroll WHERE policy_id = :pid AND carrier_id = :cid"),
        {"pid": policy_id, "cid": carrier_id},
    )
    zero_count: int = zero_result.scalar_one() or 0

    missing_result = await db.execute(
        text("SELECT COUNT(*) FROM missing_payroll WHERE policy_id = :pid AND carrier_id = :cid"),
        {"pid": policy_id, "cid": carrier_id},
    )
    missing_count_db: int = missing_result.scalar_one() or 0

    # expected_full_term = a_expected_payroll_sub (full policy term periods)
    policy_meta = await db.execute(
        text(
            "SELECT payment_frequency, effective_date, expiration_date "
            "FROM policies WHERE policy_id = :pid"
        ),
        {"pid": policy_id},
    )
    meta_row = policy_meta.fetchone()
    expected_submissions = None
    if meta_row and meta_row[0] and meta_row[1] and meta_row[2]:
        freq_map = {"Weekly": 52, "Bi-Weekly": 26, "Semi-Monthly": 24, "Monthly": 12}
        periods_per_year = freq_map.get(meta_row[0], 0)
        if periods_per_year:
            eff = meta_row[1]
            exp = meta_row[2]
            months = (exp.year - eff.year) * 12 + (exp.month - eff.month)
            expected_submissions = round(months * periods_per_year / 12)

    # missing = max(0, expected_full_term - actual_submissions_from_file)
    if missing_count_db > 0:
        final_missing = missing_count_db
    elif expected_submissions is not None and actual_received >= 0:
        final_missing = max(0, expected_submissions - actual_received)
    else:
        final_missing = None

    # submission_rate is stored as RATIO (0.667) in reported_pct.
    # The frontend multiplies by 100 to display as percentage.
    # Fallback also returns ratio.
    if pvp_row and pvp_row[0] is not None:
        submission_rate = float(pvp_row[0])   # already a ratio from ingestion Step 10
    elif expected_submissions and expected_submissions > 0 and actual_received is not None:
        submission_rate = round(actual_received / expected_submissions, 4)  # ratio
    else:
        submission_rate = None

    return PayrollMetricsResponse(
        actual_received=actual_received,
        zero_payroll_count=zero_count,
        expected_submissions=expected_submissions,
        missing_payroll_count=final_missing,
        submission_rate=submission_rate,
    )