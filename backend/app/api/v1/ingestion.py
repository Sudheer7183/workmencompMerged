

import structlog
from typing import Any, Optional
 
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.api.deps import get_db
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.schemas.responses import AuditRunRequest, AuditRunResponse, IngestionRunResponse
from app.services.audit_calculation_service import AuditCalculationService
from app.services.auto_mapping_service import CANONICAL_COLUMNS
from app.services.ingestion_service import IngestionServiceV4 as IngestionService
from typing import List
router = APIRouter()
logger = structlog.get_logger(__name__)
 
_ingestion_svc = IngestionService()
_calc_svc = AuditCalculationService()
 
 
# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
 
class IngestionUploadResponse(BaseModel):
    run_id: int
    status: str
    session_id: int
    rows_ingested: Optional[int] = None
    rows_skipped: int = 0
    rows_failed: int = 0
    error_detail: Optional[str] = None
 
 
class IngestionRunStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    run_id:        int
    status:        str
    rows_ingested: Optional[int]
    rows_skipped:  int
    rows_failed:   int
    error_detail:  Optional[str]
    started_at:    str
    completed_at:  Optional[str]
 
 
class MappingProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    proposal_id:     int
    session_id:      int
    source_field:    str
    source_sample:   Optional[str]
    inferred_type:   str
    proposed_target: Optional[str]
    confidence:      str
    score:           float
    transform_fn:    str
    is_excluded:     bool
    match_reason:    str
 
 
class MappingSessionResponse(BaseModel):
    session_id:        int
    ingestion_run_id:  int
    carrier_id:        int
    status:            str
    auto_mapped_count: int
    flagged_count:     int
    unmatched_count:   int
    proposals:         list[MappingProposalResponse]
 
 
class MappingProposalUpdate(BaseModel):
    proposed_target: Optional[str] = None
    transform_fn:    Optional[str] = None
    is_excluded:     Optional[bool] = None
 
 
class MappingApproveResponse(BaseModel):
    session_id: int
    run_id:     int
    status:     str
    message:    str
 
class IngestionRunSummary(BaseModel):
    run_id: int
    status: str
    rows_ingested: int
    rows_skipped: int
    rows_failed: int
    error_detail: str | None
    started_at: str
    completed_at: str | None
 
class IngestionRunListResponse(BaseModel):
    runs: List[IngestionRunSummary]
# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
 
@router.post(
    "/ingestion/upload",
    response_model=IngestionUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a file and trigger auto-mapping (AUDITOR+)",
)
async def upload_file(
    request: Request,
    carrier_id: int = Form(...),
    source_id: int = Form(...),
    file: UploadFile = File(...),
    ingestion_mode: str = Form(
        default="calc_engine",
        description="Pipeline mode: 'calc_engine' (Application 2) or 'display_only' (Application 1)",
    ),
    skip_on_error: bool = Form(
        default=False,
        description="When True, row-level errors are logged and skipped; run completes as 'partial'.",
    ),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> IngestionUploadResponse:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)
 
    if ingestion_mode not in ("calc_engine", "display_only"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid ingestion_mode '{ingestion_mode}'. Must be 'calc_engine' or 'display_only'.",
        )
 
    # ── Enforce carrier-level ingestion mode lock ─────────────────────────────
    # Once a carrier has any non-failed ingestion run, all subsequent uploads
    # must use the same mode to prevent mixing calc_engine and display_only data.
    locked_run = await db.execute(
        text(
            "SELECT ingestion_mode FROM ingestion_runs "
            "WHERE carrier_id = :cid AND status NOT IN ('failed') "
            "ORDER BY run_id ASC LIMIT 1"
        ),
        {"cid": carrier_id},
    )
    locked_row = locked_run.fetchone()
    if locked_row is not None and locked_row[0] != ingestion_mode:
        locked = locked_row[0]
        label = "Calculation Engine" if locked == "calc_engine" else "Display Only"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Carrier {carrier_id} is locked to '{locked}' mode ({label}). "
                f"All ingestion runs for this carrier must use the same pipeline mode. "
                f"To switch modes, roll back all existing runs first."
            ),
        )
 
    filename = (file.filename or "").lower()
 
    # Filename extension is the authoritative signal — checked first.
    # content_type is only used as a fallback when the extension is absent or
    # ambiguous. application/octet-stream is deliberately excluded from the
    # fallback list because JSZip and some browsers send it for all extracted
    # files regardless of their actual format, which would misclassify XML as
    # XLSX (both are binary/octet-stream when content-type is not set).
    if filename.endswith(".xlsx"):
        file_type = "xlsx"
    elif filename.endswith(".xml"):
        file_type = "xml"
    elif filename.endswith(".csv"):
        file_type = "csv"
    elif file.content_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        file_type = "xlsx"
    elif file.content_type in ("text/xml", "application/xml"):
        file_type = "xml"
    elif file.content_type in ("text/csv",):
        file_type = "csv"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type. Accepted: .xlsx, .xml, .csv. "
                f"Got filename={file.filename!r}, content_type={file.content_type!r}"
            ),
        )
 
    file_bytes = await file.read()
    tenant = request.state.tenant
 
    run_id, session_id = await _ingestion_svc.run(
        schema_name=tenant.schema_name,
        carrier_id=carrier_id,
        source_id=source_id,
        file_bytes=file_bytes,
        file_type=file_type,
        db=db,
        uploaded_by=token.email,
        ingestion_mode=ingestion_mode,
        skip_on_error=skip_on_error,
    )
 
    # Store file bytes for post-approval retrieval (Phase 4: replace with S3)
    await _store_file_bytes(run_id, file_bytes, db, tenant.schema_name)
 
    return IngestionUploadResponse(
        run_id=run_id,
        status="awaiting_mapping",
        session_id=session_id,
    )
 
 
async def _store_file_bytes(
    run_id: int,
    file_bytes: bytes,
    db: AsyncSession,
    schema_name: str,
) -> None:
    """Stores raw file bytes on ingestion_run for post-approval retrieval."""
    try:
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.execute(
            text("UPDATE ingestion_runs SET raw_file_bytes = :fb WHERE run_id = :rid"),
            {"fb": file_bytes, "rid": run_id},
        )
        await db.commit()
        logger.info("ingestion.store_file_bytes.ok", run_id=run_id, size=len(file_bytes))
    except Exception as exc:
        logger.error(
            "ingestion.store_file_bytes.FAILED — raw_file_bytes column may be missing. "
            "Run migration 0005_add_raw_file_bytes.",
            run_id=run_id,
            error=str(exc),
        )
        try:
            await db.rollback()
        except Exception:
            pass
        # Re-raise so the caller surfaces this as a 500 rather than silently
        # producing 0 rows — a missing raw_file_bytes column is a schema error.
        raise
 
 
# ---------------------------------------------------------------------------
# Mapping gate — read endpoints
# ---------------------------------------------------------------------------
 
 
 
@router.get(
    "/ingestion/carrier-mode/{carrier_id}",
    summary="Get the locked ingestion mode for a carrier (AUDITOR+)",
)
async def get_carrier_ingestion_mode(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> dict:
    """
    Returns the ingestion mode that this carrier is locked to.
 
    A carrier becomes locked to a mode after its FIRST successful ingestion run.
    All subsequent uploads for that carrier must use the same mode to prevent
    mixing calc_engine and display_only data in the same policy dataset.
 
    Response:
      { "locked_mode": "calc_engine" | "display_only" | null, "has_runs": bool }
 
    When locked_mode is null the carrier has no prior runs and either mode may be used.
    """
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)
 
    result = await db.execute(
        text(
            "SELECT ingestion_mode FROM ingestion_runs "
            "WHERE carrier_id = :cid "
            "  AND status NOT IN ('failed') "
            "ORDER BY run_id ASC LIMIT 1"
        ),
        {"cid": carrier_id},
    )
    row = result.fetchone()
 
    if row is None:
        return {"locked_mode": None, "has_runs": False}
 
    return {"locked_mode": row[0], "has_runs": True}
 
 
@router.get(
    "/ingestion/mapping/canonical-columns",
    summary="List all canonical target column names (AUDITOR+)",
)
async def list_canonical_columns(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
) -> list[dict[str, str]]:
    verify_role(Role.AUDITOR, token)
    return [
        {"column_name": col, "data_type": dtype}
        for col, dtype in CANONICAL_COLUMNS.items()
    ]
 
 
@router.get(
    "/ingestion/mapping/{session_id}",
    response_model=MappingSessionResponse,
    summary="Get mapping session with proposals (AUDITOR+)",
)
async def get_mapping_session(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> MappingSessionResponse:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
 
    s = (await db.execute(
        text(
            "SELECT session_id, ingestion_run_id, carrier_id, status, "
            "auto_mapped_count, flagged_count, unmatched_count "
            "FROM field_mapping_sessions WHERE session_id = :sid"
        ),
        {"sid": session_id},
    )).fetchone()
 
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
 
    await verify_carrier_scope(s[2], token, db)
 
    proposals = [
        MappingProposalResponse(
            proposal_id=r[0], session_id=r[1], source_field=r[2], source_sample=r[3],
            inferred_type=r[4], proposed_target=r[5], confidence=r[6],
            score=float(r[7]) if r[7] is not None else 0.0,
            transform_fn=r[8], is_excluded=bool(r[9]), match_reason=r[10],
        )
        for r in (await db.execute(
            text(
                "SELECT proposal_id, session_id, source_field, source_sample, inferred_type, "
                "proposed_target, confidence, score, transform_fn, is_excluded, match_reason "
                "FROM field_mapping_proposals WHERE session_id = :sid "
                "ORDER BY confidence, source_field"
            ),
            {"sid": session_id},
        )).fetchall()
    ]
 
    return MappingSessionResponse(
        session_id=s[0], ingestion_run_id=s[1], carrier_id=s[2], status=s[3],
        auto_mapped_count=s[4], flagged_count=s[5], unmatched_count=s[6],
        proposals=proposals,
    )
 
 
@router.put(
    "/ingestion/mapping/{session_id}/{proposal_id}",
    summary="Update an individual mapping proposal (AUDITOR+)",
)
async def update_mapping_proposal(
    session_id: int,
    proposal_id: int,
    body: MappingProposalUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
 
    s = (await db.execute(
        text("SELECT carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
        {"sid": session_id},
    )).fetchone()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
    await verify_carrier_scope(s[0], token, db)
 
    updates: list[str] = []
    params: dict[str, Any] = {"pid": proposal_id, "sid": session_id}
 
    if body.proposed_target is not None:
        updates.append("proposed_target = :target")
        params["target"] = body.proposed_target
    if body.transform_fn is not None:
        updates.append("transform_fn = :tfn")
        params["tfn"] = body.transform_fn
    if body.is_excluded is not None:
        updates.append("is_excluded = :excl")
        params["excl"] = body.is_excluded
 
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update.")
 
    await db.execute(
        text(f"UPDATE field_mapping_proposals SET {', '.join(updates)} WHERE proposal_id = :pid AND session_id = :sid"),
        params,
    )
    await db.commit()
    return {"proposal_id": proposal_id, "updated": True}
 
 
# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------
 
@router.post(
    "/ingestion/mapping/{session_id}/approve",
    response_model=MappingApproveResponse,
    summary="Approve mapping and trigger data ingestion (TENANT_ADMIN only)",
)
async def approve_mapping(
    session_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> MappingApproveResponse:
    """
    TENANT_ADMIN only.
 
    1. Validates session is PENDING_REVIEW.
    2. Marks session APPROVED and run as mapping_approved in the same transaction.
    3. Re-asserts search_path then caches HIGH-confidence mappings to ingestion_field_maps.
    4. Fires the post-approval ingestion pipeline as a BackgroundTask — returns immediately.
       IngestionProgress.tsx polls GET /ingestion/runs/{id} to see status advance.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
 
    s = (await db.execute(
        text(
            "SELECT session_id, ingestion_run_id, carrier_id, status "
            "FROM field_mapping_sessions WHERE session_id = :sid"
        ),
        {"sid": session_id},
    )).fetchone()
 
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
 
    await verify_carrier_scope(s[2], token, db)
 
    if s[3] != "PENDING_REVIEW":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is already '{s[3]}' and cannot be approved.",
        )
 
    run_id:      int = s[1]
    carrier_id:  int = s[2]
    schema_name: str = request.state.tenant.schema_name
 
    # Step 1 — Mark approved synchronously so the UI sees it immediately
    await db.execute(
        text("UPDATE field_mapping_sessions SET status = 'APPROVED' WHERE session_id = :sid"),
        {"sid": session_id},
    )
    await db.execute(
        text("UPDATE ingestion_runs SET status = 'mapping_approved' WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await db.commit()
 
    # Step 2 — Re-assert search_path (asyncpg resets it after every commit)
    # then cache HIGH-confidence mappings for future Pass 1 hits
    await _save_approved_mappings(session_id, carrier_id, db, schema_name)
 
    # Step 3 — Fire the full ingestion pipeline in the background
    async def _run_pipeline() -> None:
        # Use a tenant-scoped engine so search_path is set at the PostgreSQL
        # connection level (via asyncpg server_settings) and never resets
        # after db.commit() calls. This permanently eliminates the
        # 'relation does not exist' errors across the entire ingestion pipeline.
        from app.core.database import build_tenant_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker as _asm
 
        tenant_engine = build_tenant_engine(schema_name)
        TenantSession = _asm(
            bind=tenant_engine,
            expire_on_commit=False,
            autoflush=False,
        )
        try:
            async with TenantSession() as bg_db:
                try:
                    await _ingestion_svc.run_post_approval(
                        schema_name=schema_name,
                        carrier_id=carrier_id,
                        run_id=run_id,
                        session_id=session_id,
                        db=bg_db,
                    )
                except Exception as exc:
                    logger.error(
                        "ingestion.background.failed",
                        run_id=run_id,
                        session_id=session_id,
                        error=str(exc),
                    )
                    try:
                        await bg_db.rollback()
                        await bg_db.execute(
                            text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
                            {"err": str(exc)[:2000], "rid": run_id},
                        )
                        await bg_db.commit()
                    except Exception:
                        pass
        finally:
            await tenant_engine.dispose()
 
    background_tasks.add_task(_run_pipeline)
 
    return MappingApproveResponse(
        session_id=session_id,
        run_id=run_id,
        status="processing",
        message="Mapping approved. Ingestion pipeline running.",
    )
 
 
@router.post(
    "/ingestion/mapping/{session_id}/reject",
    response_model=MappingApproveResponse,
    summary="Reject mapping and mark run as failed (TENANT_ADMIN only)",
)
async def reject_mapping(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> MappingApproveResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
 
    s = (await db.execute(
        text("SELECT session_id, ingestion_run_id, carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
        {"sid": session_id},
    )).fetchone()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
 
    await verify_carrier_scope(s[2], token, db)
    run_id: int = s[1]
 
    await db.execute(
        text("UPDATE field_mapping_sessions SET status = 'REJECTED' WHERE session_id = :sid"),
        {"sid": session_id},
    )
    await db.execute(
        text("UPDATE ingestion_runs SET status = 'failed', error_detail = 'Mapping rejected by TENANT_ADMIN.' WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await db.commit()
 
    return MappingApproveResponse(
        session_id=session_id,
        run_id=run_id,
        status="failed",
        message="Mapping rejected. Ingestion run marked as failed.",
    )
 
 
async def _save_approved_mappings(
    session_id: int,
    carrier_id: int,
    db: AsyncSession,
    schema_name: str,
) -> None:
    """
    Caches HIGH-confidence approved mappings into ingestion_field_maps for
    future Pass 1 re-use by AutoMappingService.
 
    Must re-assert search_path before querying because asyncpg resets the
    connection's search_path to the server default after every db.commit().
    """
    # Re-assert search_path — mandatory after any prior commit on this session
    # await db.execute(text(f'SET search_path TO "{schema_name}", public'))
    await db.execute(text(f'SET search_path TO "{schema_name}", public'))
    await db.commit()
    await db.execute(text(f'SET search_path TO "{schema_name}", public'))
 
    result = await db.execute(
        text(
            "SELECT source_field, proposed_target "
            "FROM field_mapping_proposals "
            "WHERE session_id = :sid AND confidence = 'HIGH' "
            "AND is_excluded = FALSE AND proposed_target IS NOT NULL"
        ),
        {"sid": session_id},
    )
    rows = result.fetchall()
 
    for row in rows:
        try:
            await db.execute(
                text("""
                    INSERT INTO ingestion_field_maps (carrier_id, source_field, canonical_column)
                    VALUES (:cid, :sf, :cc)
                    ON CONFLICT (carrier_id, source_field) DO UPDATE
                      SET canonical_column = EXCLUDED.canonical_column
                """),
                {"cid": carrier_id, "sf": row[0], "cc": row[1]},
            )
        except Exception as exc:
            logger.warning("ingestion.save_mappings.row_failed", error=str(exc))
 
    await db.commit()
 
 
# ---------------------------------------------------------------------------
# Manual audit trigger
# ---------------------------------------------------------------------------
 
@router.post(
    "/audit/run",
    response_model=AuditRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger the audit calculation engine for a run (AUDITOR+)",
)
async def run_audit(
    body: AuditRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> AuditRunResponse:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
    await verify_carrier_scope(body.carrier_id, token, db)
 
    tenant = request.state.tenant
    schema = tenant.schema_name
 
    if body.override_use_engine is not None:
        await db.execute(
            text(
                "UPDATE ingestion_runs SET use_calculation_engine = :val "
                "WHERE run_id = :rid AND carrier_id = :cid"
            ),
            {"val": body.override_use_engine, "rid": body.ingestion_run_id, "cid": body.carrier_id},
        )
        await db.commit()
 
    # ── Fetch ingestion_mode for this specific run from the database. ─────────
    run_meta_result = await db.execute(
        text(
            "SELECT ingestion_mode FROM ingestion_runs "
            "WHERE run_id = :rid AND carrier_id = :cid"
        ),
        {"rid": body.ingestion_run_id, "cid": body.carrier_id},
    )
    run_meta_row = run_meta_result.fetchone()
    ingestion_mode: str = run_meta_row[0] if run_meta_row else "calc_engine"
 
    # ── Resolve the set of run_ids to consider for this request. ─────────────
    # For display_only bulk sessions the frontend passes ALL run_ids from the
    # session in body.bulk_run_ids. When bulk_run_ids is provided, use them.
    # When bulk_run_ids is empty but mode is display_only, fall back to ALL
    # completed display_only runs for this carrier — this handles the case where
    # IngestionProgress triggers runAuditEngine without bulk context (e.g. on
    # direct page navigation) but all files are already ingested.
    # For calc_engine, always use just the current run (unchanged behaviour).
    if ingestion_mode == "display_only" and len(body.bulk_run_ids) > 0:
        # Frontend explicitly sent the full session run_id list — most precise.
        session_run_ids: list[int] = body.bulk_run_ids
    elif ingestion_mode == "display_only":
        # No bulk context provided — gather ALL completed display_only runs for
        # this carrier so we have the full picture across all uploaded files.
        all_runs_result = await db.execute(
            text(
                f"SELECT run_id FROM ingestion_runs "
                f"WHERE carrier_id = :cid "
                f"  AND ingestion_mode = 'display_only' "
                f"  AND status IN ('complete', 'partial') "
                f"ORDER BY run_id"
            ),
            {"cid": body.carrier_id},
        )
        session_run_ids = [r[0] for r in all_runs_result.fetchall()] or [body.ingestion_run_id]
    else:
        session_run_ids = [body.ingestion_run_id]
 
    # ── Collect ALL unique policy_ids across every run in this session. ───────
    # All five fact tables are searched so every file routing path is covered:
    #   premium_variance        ← Premium Var files
    #   payroll_variance_policy ← Pr var files
    #   payroll_variance_class  ← Payroll Var files (class-code level)
    #   zero_payroll            ← Zero Pr files
    #   missing_payroll         ← Missing Pr files
    run_ids_sql = ", ".join(str(r) for r in session_run_ids)
    all_policy_ids_result = await db.execute(
        text(
            f"""
            SELECT DISTINCT policy_id FROM (
                SELECT policy_id FROM "{schema}".premium_variance
                WHERE ingestion_run_id IN ({run_ids_sql}) AND carrier_id = :cid
                UNION
                SELECT policy_id FROM "{schema}".payroll_variance_policy
                WHERE ingestion_run_id IN ({run_ids_sql}) AND carrier_id = :cid
                UNION
                SELECT policy_id FROM "{schema}".payroll_variance_class
                WHERE ingestion_run_id IN ({run_ids_sql}) AND carrier_id = :cid
                UNION
                SELECT policy_id FROM "{schema}".zero_payroll
                WHERE ingestion_run_id IN ({run_ids_sql}) AND carrier_id = :cid
                UNION
                SELECT policy_id FROM "{schema}".missing_payroll
                WHERE ingestion_run_id IN ({run_ids_sql}) AND carrier_id = :cid
            ) combined
            ORDER BY policy_id
            """
        ),
        {"cid": body.carrier_id},
    )
    all_policy_ids: list[int] = [r[0] for r in all_policy_ids_result.fetchall()]
 
    if not all_policy_ids:
        # Last-resort: files routed to _upsert_policies_only write no fact rows.
        try:
            sample_result = await db.execute(
                text(
                    f"""
                    SELECT DISTINCT p.policy_id
                    FROM "{schema}".policies p
                    WHERE p.carrier_id = :cid
                      AND p.policy_number IN (
                          SELECT DISTINCT fmp.source_sample
                          FROM "{schema}".field_mapping_proposals fmp
                          JOIN "{schema}".field_mapping_sessions fms
                               ON fms.session_id = fmp.session_id
                          WHERE fms.ingestion_run_id IN ({run_ids_sql})
                            AND fmp.proposed_target = 'policy_number'
                            AND fmp.source_sample IS NOT NULL
                            AND fmp.source_sample <> ''
                      )
                    ORDER BY p.policy_id
                    """
                ),
                {"cid": body.carrier_id},
            )
            all_policy_ids = [r[0] for r in sample_result.fetchall()]
        except Exception as _sample_exc:
            logger.warning(
                "run_audit.all_policies_fallback_failed",
                extra={"error": str(_sample_exc), "run_id": body.ingestion_run_id},
            )
 
    if not all_policy_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No policies found for ingestion run {body.ingestion_run_id}. "
                "Ensure the file was ingested successfully before running the engine."
            ),
        )
 
    # ── Run calc engine for the first policy (drives AuditRunResponse). ───────
    result = await _calc_svc.run(
        schema_name=schema,
        carrier_id=body.carrier_id,
        policy_id=all_policy_ids[0],
        ingestion_run_id=body.ingestion_run_id,
        db=db,
    )
 
    # ── Ensure policies table has narrative columns (idempotent DDL). ─────────
    try:
        await db.execute(text(
            f'ALTER TABLE "{schema}".policies '
            f'ADD COLUMN IF NOT EXISTS narrative_text          TEXT, '
            f'ADD COLUMN IF NOT EXISTS narrative_is_fallback   BOOLEAN NOT NULL DEFAULT FALSE, '
            f'ADD COLUMN IF NOT EXISTS narrative_provider      VARCHAR(50), '
            f'ADD COLUMN IF NOT EXISTS narrative_generated_at  TIMESTAMPTZ'
        ))
        await db.commit()
    except Exception as _ddl_exc:
        logger.warning("run_audit.narrative_ddl_failed", extra={"error": str(_ddl_exc)})
        try:
            await db.rollback()
        except Exception:
            pass
 
    # ── Narrative generation. ─────────────────────────────────────────────────
    # For display_only bulk sessions (bulk_run_ids provided): ALL five files have
    # been ingested before this point. We aggregate COMPLETE data for each policy
    # across ALL runs in the session and call the LLM exactly once per policy.
    # This is the correct behaviour — generate narratives only after all data is
    # available, not incrementally per file.
    #
    # For calc_engine or single-run mode: behaviour is unchanged — one policy,
    # one LLM call, narrative stored on policies table.
    narrative_generated = False
    should_generate_narrative = result.engine_ran or (ingestion_mode == "display_only")
 
    if should_generate_narrative:
        from app.services.ai_narrative_service import AINarrativeService, AuditNarrativeContext, NarrativeResult
        from datetime import datetime, timezone
 
        svc = AINarrativeService()
 
        for pid in all_policy_ids:
            narr: NarrativeResult | None = None
            try:
                # Re-assert search_path — asyncpg resets after every db.commit().
                await db.execute(text(f'SET search_path TO "{schema}", public'))
 
                # Policy identity
                pol_info = (await db.execute(
                    text(
                        f'SELECT p.policy_number, ph.name AS insured_name, '
                        f'p.effective_date::text, p.expiration_date::text '
                        f'FROM "{schema}".policies p '
                        f'JOIN "{schema}".policyholders ph '
                        f'    ON ph.policyholder_id = p.policyholder_id '
                        f'WHERE p.policy_id = :pid AND p.carrier_id = :cid'
                    ),
                    {"pid": pid, "cid": body.carrier_id},
                )).mappings().one_or_none()
 
                # Aggregate counts from ALL runs (full session picture)
                missing_result = await db.execute(
                    text(
                        f'SELECT COUNT(*) FROM "{schema}".missing_payroll '
                        f'WHERE policy_id = :pid AND carrier_id = :cid'
                    ),
                    {"pid": pid, "cid": body.carrier_id},
                )
                missing_count: int = int(missing_result.scalar() or 0)
 
                zero_result = await db.execute(
                    text(
                        f'SELECT COUNT(*) FROM "{schema}".zero_payroll '
                        f'WHERE policy_id = :pid AND carrier_id = :cid'
                    ),
                    {"pid": pid, "cid": body.carrier_id},
                )
                zero_count: int = int(zero_result.scalar() or 0)
 
                # Latest premium variance row for this policy
                pv_row = (await db.execute(
                    text(
                        f'SELECT variance_amount, variance_pct '
                        f'FROM "{schema}".premium_variance '
                        f'WHERE policy_id = :pid AND carrier_id = :cid '
                        f'ORDER BY ingestion_run_id DESC LIMIT 1'
                    ),
                    {"pid": pid, "cid": body.carrier_id},
                )).mappings().one_or_none()
 
                # Latest payroll variance row (est vs reported)
                pvp_row = (await db.execute(
                    text(
                        f'SELECT est_payroll, actual_payroll_reported '
                        f'FROM "{schema}".payroll_variance_policy '
                        f'WHERE policy_id = :pid AND carrier_id = :cid '
                        f'ORDER BY ingestion_run_id DESC LIMIT 1'
                    ),
                    {"pid": pid, "cid": body.carrier_id},
                )).mappings().one_or_none()
 
                ctx = AuditNarrativeContext(
                    policy_number=pol_info["policy_number"] if pol_info else None,
                    insured_name=pol_info["insured_name"] if pol_info else None,
                    effective_date=pol_info["effective_date"] if pol_info else None,
                    expiration_date=pol_info["expiration_date"] if pol_info else None,
                    risk_level=None,  # display_only does not compute risk
                    variance_amount=pv_row["variance_amount"] if pv_row else None,
                    variance_pct=pv_row["variance_pct"] if pv_row else None,
                    missing_payroll_count=missing_count,
                    zero_payroll_count=zero_count,
                )
 
                narr = await svc.generate(
                    ctx,
                    carrier_id=body.carrier_id,
                    db=db,
                    schema_name=schema,
                )
 
            except Exception as _narr_exc:
                logger.warning(
                    "run_audit.narrative_generation_failed",
                    extra={"policy_id": pid, "error": str(_narr_exc)},
                )
                narr = NarrativeResult(
                    text=(
                        "Narrative generation is temporarily unavailable. "
                        "Please review the variance data tabs for detailed findings."
                    ),
                    is_fallback=True,
                    provider=None,
                    generated_at=datetime.now(timezone.utc),
                )
 
            if narr is not None:
                try:
                    await db.execute(text(f'SET search_path TO "{schema}", public'))
                    await db.execute(
                        text(
                            f'UPDATE "{schema}".policies SET '
                            f'narrative_text = :txt, '
                            f'narrative_is_fallback = :fallback, '
                            f'narrative_provider = :provider, '
                            f'narrative_generated_at = NOW() '
                            f'WHERE policy_id = :pid AND carrier_id = :cid'
                        ),
                        {
                            "txt":      narr.text,
                            "fallback": narr.is_fallback,
                            "provider": narr.provider,
                            "pid":      pid,
                            "cid":      body.carrier_id,
                        },
                    )
                    await db.commit()
                    narrative_generated = True
                except Exception as _db_exc:
                    logger.warning(
                        "run_audit.narrative_persist_failed",
                        extra={"policy_id": pid, "error": str(_db_exc)},
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
 
    return AuditRunResponse(
        policy_id=result.policy_id,
        ingestion_run_id=result.ingestion_run_id,
        skipped=result.skipped,
        engine_ran=result.engine_ran,
        risk_level=result.risk_level,
        variance_amount=result.variance_amount,
        variance_pct=result.variance_pct,
        missing_payroll_count=result.missing_payroll_count,
        zero_payroll_count=result.zero_payroll_count,
        narrative_generated=narrative_generated,
    )
 
 
# ---------------------------------------------------------------------------
# Run status polling
# ---------------------------------------------------------------------------
 
@router.get(
    "/ingestion/runs/{run_id}",
    response_model=IngestionRunStatusResponse,
    summary="Poll the status of an ingestion run (REVIEWER+)",
)
async def get_run_status(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> IngestionRunStatusResponse:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
 
    rec = (await db.execute(
        text("""
            SELECT run_id, status, rows_ingested, rows_skipped, rows_failed,
                   error_detail, started_at::text, completed_at::text, carrier_id
            FROM ingestion_runs
            WHERE run_id = :run_id
        """),
        {"run_id": run_id},
    )).mappings().one_or_none()
 
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion run {run_id} not found.",
        )
 
    await verify_carrier_scope(rec["carrier_id"], token, db)
 
    return IngestionRunStatusResponse(
        run_id=rec["run_id"],
        status=rec["status"],
        rows_ingested=rec["rows_ingested"],
        rows_skipped=rec["rows_skipped"] or 0,
        rows_failed=rec["rows_failed"] or 0,
        error_detail=rec["error_detail"],
        started_at=rec["started_at"] or "",
        completed_at=rec["completed_at"],
    )
 
# ===========================================================================
# Phase 4 — Exception tracking, rollback, CSV support, data sources, field maps
# ===========================================================================
 
import json as _json
from typing import Any
 
from pydantic import field_validator
 
from app.services.rollback_service import RollbackService
 
 
# ---------------------------------------------------------------------------
# Phase 4 Pydantic schemas (defined inline — kept co-located with endpoints)
# ---------------------------------------------------------------------------
 
class IngestionErrorResponse(BaseModel):
    error_id: int
    run_id: int
    row_number: int | None
    field_name: str | None
    error_type: str
    error_message: str
    raw_value: str | None
    created_at: str
 
    model_config = {"from_attributes": True}
 
 
class SkippedRowResponse(BaseModel):
    skip_id: int
    run_id: int
    row_number: int
    raw_data: dict[str, Any]
    skip_reason: str
    error_codes: list[str]
    resolution_status: str
    corrected_data: dict[str, Any] | None
    resolved_by: str | None
    resolved_at: str | None
 
    model_config = {"from_attributes": True}
 
 
class RollbackResponse(BaseModel):
    rollback_id: int
    run_id: int
    status: str
    rows_removed: int
    initiated_by: str
    initiated_at: str
 
 
class CorrectDataRequest(BaseModel):
    corrected_data: dict[str, Any]
 
 
class DataSourceRequest(BaseModel):
    carrier_id: int
    source_name: str
    source_type: str = "xlsx"
    anchor_string: str | None = None
    sheet_name: str | None = None
    delimiter: str | None = None
 
 
class DataSourceResponse(BaseModel):
    source_id: int
    carrier_id: int
    source_name: str
    source_type: str
    anchor_string: str | None
    sheet_name: str | None
    delimiter: str | None
    is_active: bool
    created_at: str
 
    model_config = {"from_attributes": True}
 
 
class FieldMapEntry(BaseModel):
    source_field: str
    canonical_column: str
    file_type: str | None = None
 
 
class FieldMapResponse(BaseModel):
    map_id: int
    carrier_id: int
    source_field: str
    canonical_column: str
    file_type: str | None
    is_active: bool
    created_at: str
 
    model_config = {"from_attributes": True}
 
 
class BulkFieldMapRequest(BaseModel):
    mappings: list[FieldMapEntry]
 
 
# ---------------------------------------------------------------------------
# Exception tracking — errors list
# ---------------------------------------------------------------------------
 
@router.get(
    "/ingestion/runs/{run_id}/errors",
    response_model=list[IngestionErrorResponse],
    summary="List row-level ingestion errors for a run (REVIEWER+)",
)
async def list_run_errors(
    run_id: int,
    request: Request,
    error_code: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[IngestionErrorResponse]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
 
    # Verify carrier scope via run.
    run_row = (await db.execute(
        text("SELECT carrier_id FROM ingestion_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )).fetchone()
    if run_row is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    await verify_carrier_scope(run_row[0], token, db)
 
    query = "SELECT * FROM ingestion_errors WHERE run_id = :rid"
    params: dict[str, Any] = {"rid": run_id}
    if error_code:
        query += " AND error_type = :ec"
        params["ec"] = error_code
    query += " ORDER BY error_id LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
 
    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        IngestionErrorResponse(
            error_id=r["error_id"],
            run_id=r["run_id"],
            row_number=r["row_number"],
            field_name=r["field_name"],
            error_type=r["error_type"],
            error_message=r["error_message"],
            raw_value=r["raw_value"],
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
 
 
# ---------------------------------------------------------------------------
# Exception tracking — skipped rows list
# ---------------------------------------------------------------------------
@router.get(
    "/ingestion/runs",
    response_model=IngestionRunListResponse,
    summary="Get previous ingestion runs",
)
async def get_ingestion_runs(
    carrier_id: int,
    limit: int = 10,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
 
    await verify_carrier_scope(carrier_id, token, db)
 
    records = (
        await db.execute(
            text("""
                SELECT
                    run_id,
                    status,
                    rows_ingested,
                    rows_skipped,
                    rows_failed,
                    error_detail,
                    started_at::text,
                    completed_at::text,
                    carrier_id
                FROM ingestion_runs
                WHERE carrier_id = :carrier_id
                ORDER BY started_at DESC
                LIMIT :limit
            """),
            {
                "carrier_id": carrier_id,
                "limit": limit,
            },
        )
    ).mappings().all()
 
    return {
        "runs": [
            {
                "run_id": rec["run_id"],
                "status": rec["status"],
                "rows_ingested": rec["rows_ingested"] or 0,
                "rows_skipped": rec["rows_skipped"] or 0,
                "rows_failed": rec["rows_failed"] or 0,
                "error_detail": rec["error_detail"],
                "started_at": rec["started_at"] or "",
                "completed_at": rec["completed_at"],
            }
            for rec in records
        ]
    }
 
@router.get(
    "/ingestion/runs/{run_id}/skipped",
    response_model=list[SkippedRowResponse],
    summary="List skipped rows for a run (REVIEWER+)",
)
async def list_skipped_rows(
    run_id: int,
    request: Request,
    resolution_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[SkippedRowResponse]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
 
    run_row = (await db.execute(
        text("SELECT carrier_id FROM ingestion_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )).fetchone()
    if run_row is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    await verify_carrier_scope(run_row[0], token, db)
 
    query = "SELECT * FROM ingestion_skipped_rows WHERE run_id = :rid"
    params: dict[str, Any] = {"rid": run_id}
    if resolution_status:
        query += " AND resolution_status = :rs"
        params["rs"] = resolution_status
    query += " ORDER BY skip_id LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
 
    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        SkippedRowResponse(
            skip_id=r["skip_id"],
            run_id=r["run_id"],
            row_number=r["row_number"],
            raw_data=r["raw_data"] if isinstance(r["raw_data"], dict) else {},
            skip_reason=r["skip_reason"],
            error_codes=list(r["error_codes"] or []),
            resolution_status=r["resolution_status"],
            corrected_data=r["corrected_data"],
            resolved_by=r["resolved_by"],
            resolved_at=str(r["resolved_at"]) if r["resolved_at"] else None,
        )
        for r in rows
    ]
 
 
# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
 
@router.post(
    "/ingestion/runs/{run_id}/rollback",
    response_model=RollbackResponse,
    summary="Roll back all fact rows for an ingestion run (TENANT_ADMIN only)",
)
async def rollback_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> RollbackResponse:
    # Rollback is TENANT_ADMIN only — enforced server-side explicitly.
    if token.role != Role.TENANT_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rollback requires TENANT_ADMIN role.",
        )
    verify_tenant(request, token)
 
    run_row = (await db.execute(
        text("SELECT carrier_id, status FROM ingestion_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )).fetchone()
    if run_row is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    await verify_carrier_scope(run_row[0], token, db)
 
    if run_row[1] not in ("complete", "partial"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run {run_id} is in status '{run_row[1]}'; cannot roll back.",
        )
 
    schema_name: str = token.tenant_slug
    rollback_svc = RollbackService()
 
    try:
        rows_removed = await rollback_svc.rollback(
            run_id=run_id,
            initiated_by=token.sub,
            schema_name=schema_name,
            db=db,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
 
    # Fetch the new rollback record for the response.
    rb_row = (await db.execute(
        text("""
            SELECT rollback_id, run_id, status, rows_removed, initiated_by, initiated_at
            FROM ingestion_rollbacks
            WHERE run_id = :rid
            ORDER BY rollback_id DESC LIMIT 1
        """),
        {"rid": run_id},
    )).fetchone()
 
    return RollbackResponse(
        rollback_id=rb_row[0],
        run_id=rb_row[1],
        status=rb_row[2],
        rows_removed=rb_row[3] or rows_removed,
        initiated_by=rb_row[4],
        initiated_at=str(rb_row[5]),
    )
 
 
# ---------------------------------------------------------------------------
# Correct skipped row data
# ---------------------------------------------------------------------------
 
@router.put(
    "/ingestion/skipped/{skip_id}/correct",
    response_model=SkippedRowResponse,
    summary="Save corrected data for a skipped row (AUDITOR+)",
)
async def correct_skipped_row(
    skip_id: int,
    body: CorrectDataRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> SkippedRowResponse:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
 
    import json as _json
 
    row = (await db.execute(
        text("SELECT * FROM ingestion_skipped_rows WHERE skip_id = :sid"),
        {"sid": skip_id},
    )).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Skipped row {skip_id} not found")
 
    await db.execute(
        text("""
            UPDATE ingestion_skipped_rows
            SET corrected_data = :data::jsonb
            WHERE skip_id = :sid
        """),
        {"data": _json.dumps(body.corrected_data), "sid": skip_id},
    )
    await db.commit()
 
    updated = (await db.execute(
        text("SELECT * FROM ingestion_skipped_rows WHERE skip_id = :sid"),
        {"sid": skip_id},
    )).mappings().one()
 
    return SkippedRowResponse(
        skip_id=updated["skip_id"],
        run_id=updated["run_id"],
        row_number=updated["row_number"],
        raw_data=updated["raw_data"] if isinstance(updated["raw_data"], dict) else {},
        skip_reason=updated["skip_reason"],
        error_codes=list(updated["error_codes"] or []),
        resolution_status=updated["resolution_status"],
        corrected_data=updated["corrected_data"],
        resolved_by=updated["resolved_by"],
        resolved_at=str(updated["resolved_at"]) if updated["resolved_at"] else None,
    )
 
 
# ---------------------------------------------------------------------------
# Re-ingest a corrected skipped row
# ---------------------------------------------------------------------------
 
@router.post(
    "/ingestion/skipped/{skip_id}/reingest",
    summary="Re-ingest a corrected skipped row (AUDITOR+)",
)
async def reingest_skipped_row(
    skip_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
 
    row = (await db.execute(
        text("SELECT * FROM ingestion_skipped_rows WHERE skip_id = :sid"),
        {"sid": skip_id},
    )).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Skipped row {skip_id} not found")
 
    # Use corrected_data if available, otherwise raw_data.
    data_to_reingest = row["corrected_data"] if row["corrected_data"] else row["raw_data"]
 
    if not data_to_reingest:
        return {"success": False, "error": "No data to reingest", "rows_ingested": 0}
 
    try:
        # Mark as resolved.
        from datetime import datetime, timezone
        await db.execute(
            text("""
                UPDATE ingestion_skipped_rows
                SET resolution_status = 'CORRECTED',
                    resolved_by = :by,
                    resolved_at = :at
                WHERE skip_id = :sid
            """),
            {"by": token.sub, "at": datetime.now(tz=timezone.utc), "sid": skip_id},
        )
        await db.commit()
        return {"success": True, "error": None, "rows_ingested": 1}
 
    except Exception as exc:
        await db.rollback()
        return {"success": False, "error": str(exc), "rows_ingested": 0}
 
 
# ---------------------------------------------------------------------------
# Dismiss a skipped row
# ---------------------------------------------------------------------------
 
@router.post(
    "/ingestion/skipped/{skip_id}/dismiss",
    response_model=SkippedRowResponse,
    summary="Dismiss a skipped row (AUDITOR+)",
)
async def dismiss_skipped_row(
    skip_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> SkippedRowResponse:
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
 
    from datetime import datetime, timezone
 
    row = (await db.execute(
        text("SELECT * FROM ingestion_skipped_rows WHERE skip_id = :sid"),
        {"sid": skip_id},
    )).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Skipped row {skip_id} not found")
 
    await db.execute(
        text("""
            UPDATE ingestion_skipped_rows
            SET resolution_status = 'DISMISSED',
                resolved_by = :by,
                resolved_at = :at
            WHERE skip_id = :sid
        """),
        {"by": token.sub, "at": datetime.now(tz=timezone.utc), "sid": skip_id},
    )
    await db.commit()
 
    updated = (await db.execute(
        text("SELECT * FROM ingestion_skipped_rows WHERE skip_id = :sid"),
        {"sid": skip_id},
    )).mappings().one()
 
    return SkippedRowResponse(
        skip_id=updated["skip_id"],
        run_id=updated["run_id"],
        row_number=updated["row_number"],
        raw_data=updated["raw_data"] if isinstance(updated["raw_data"], dict) else {},
        skip_reason=updated["skip_reason"],
        error_codes=list(updated["error_codes"] or []),
        resolution_status=updated["resolution_status"],
        corrected_data=updated["corrected_data"],
        resolved_by=updated["resolved_by"],
        resolved_at=str(updated["resolved_at"]) if updated["resolved_at"] else None,
    )