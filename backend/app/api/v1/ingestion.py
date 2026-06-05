# from __future__ import annotations

# """
# Ingestion API — Phase 3.

# Endpoints:
#   POST /ingestion/upload                              — upload file, generate mapping proposals
#   GET  /ingestion/mapping/canonical-columns           — list canonical target columns
#   GET  /ingestion/mapping/{session_id}                — get session + proposals
#   PUT  /ingestion/mapping/{session_id}/{proposal_id}  — update a proposal
#   POST /ingestion/mapping/{session_id}/approve        — TENANT_ADMIN approves (non-blocking)
#   POST /ingestion/mapping/{session_id}/reject         — TENANT_ADMIN rejects
#   GET  /ingestion/runs/{run_id}                       — poll run status
#   POST /audit/run                                     — manual calc engine trigger
# """

# import structlog
# from typing import Any, Optional

# from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
# from pydantic import BaseModel, ConfigDict
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.responses import AuditRunRequest, AuditRunResponse, IngestionRunResponse
# from app.services.audit_calculation_service import AuditCalculationService
# from app.services.auto_mapping_service import CANONICAL_COLUMNS
# from app.services.ingestion_service import IngestionService

# router = APIRouter()
# logger = structlog.get_logger(__name__)

# _ingestion_svc = IngestionService()
# _calc_svc = AuditCalculationService()


# # ---------------------------------------------------------------------------
# # Response schemas
# # ---------------------------------------------------------------------------

# class IngestionUploadResponse(BaseModel):
#     run_id: int
#     status: str
#     session_id: int
#     rows_ingested: Optional[int] = None
#     rows_skipped: int = 0
#     rows_failed: int = 0
#     error_detail: Optional[str] = None


# class IngestionRunStatusResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     run_id:        int
#     status:        str
#     rows_ingested: Optional[int]
#     rows_skipped:  int
#     rows_failed:   int
#     error_detail:  Optional[str]
#     started_at:    str
#     completed_at:  Optional[str]


# class MappingProposalResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     proposal_id:     int
#     session_id:      int
#     source_field:    str
#     source_sample:   Optional[str]
#     inferred_type:   str
#     proposed_target: Optional[str]
#     confidence:      str
#     score:           float
#     transform_fn:    str
#     is_excluded:     bool
#     match_reason:    str


# class MappingSessionResponse(BaseModel):
#     session_id:        int
#     ingestion_run_id:  int
#     carrier_id:        int
#     status:            str
#     auto_mapped_count: int
#     flagged_count:     int
#     unmatched_count:   int
#     proposals:         list[MappingProposalResponse]


# class MappingProposalUpdate(BaseModel):
#     proposed_target: Optional[str] = None
#     transform_fn:    Optional[str] = None
#     is_excluded:     Optional[bool] = None


# class MappingApproveResponse(BaseModel):
#     session_id: int
#     run_id:     int
#     status:     str
#     message:    str


# # ---------------------------------------------------------------------------
# # Upload
# # ---------------------------------------------------------------------------

# @router.post(
#     "/ingestion/upload",
#     response_model=IngestionUploadResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Upload a file and trigger auto-mapping (AUDITOR+)",
# )


# async def upload_file(
#     request: Request,
#     carrier_id: int = Form(...),
#     source_id: int = Form(...),
#     file: UploadFile = File(...),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> IngestionUploadResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)
#     await verify_carrier_scope(carrier_id, token, db)

#     filename = (file.filename or "").lower()

#     print("filename:", file.filename)
#     print("content_type:", file.content_type)
#     filename = (file.filename or "").lower()

#     if filename.endswith(".xlsx") or file.content_type in (
#         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         "application/octet-stream",
#     ):
#         file_type = "xlsx"
#     elif filename.endswith(".xml") or file.content_type in (
#         "text/xml",
#         "application/xml",
#     ):
#         file_type = "xml"
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail=f"Unsupported file type. Accepted: .xlsx, .xml. Got: {file.filename}",
#         )

#     file_bytes = await file.read()
#     tenant = request.state.tenant
#     print("file type in the ingestion upload",file_type)
#     run_id, session_id = await _ingestion_svc.run(
#         schema_name=tenant.schema_name,
#         carrier_id=carrier_id,
#         source_id=source_id,
#         file_bytes=file_bytes,
#         file_type=file_type,
#         db=db,
#         uploaded_by=token.email,
#     )

#     # Store file bytes for post-approval retrieval (Phase 4: replace with S3)
#     await _store_file_bytes(run_id, file_bytes, db, tenant.schema_name)

#     return IngestionUploadResponse(
#         run_id=run_id,
#         status="awaiting_mapping",
#         session_id=session_id,
#     )


# async def _store_file_bytes(
#     run_id: int,
#     file_bytes: bytes,
#     db: AsyncSession,
#     schema_name: str,
# ) -> None:
#     """Stores raw file bytes on ingestion_run for post-approval retrieval."""
#     try:
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.commit()
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.execute(
#             text("UPDATE ingestion_runs SET raw_file_bytes = :fb WHERE run_id = :rid"),
#             {"fb": file_bytes, "rid": run_id},
#         )
#         await db.commit()
#     except Exception as exc:
#         logger.warning("ingestion.store_file_bytes.failed", run_id=run_id, error=str(exc))
#         try:
#             await db.rollback()
#         except Exception:
#             pass


# # ---------------------------------------------------------------------------
# # Mapping gate — read endpoints
# # ---------------------------------------------------------------------------

# @router.get(
#     "/ingestion/mapping/canonical-columns",
#     summary="List all canonical target column names (AUDITOR+)",
# )
# async def list_canonical_columns(
#     request: Request,
#     token: TokenPayload = Depends(get_current_user),
# ) -> list[dict[str, str]]:
#     verify_role(Role.AUDITOR, token)
#     return [
#         {"column_name": col, "data_type": dtype}
#         for col, dtype in CANONICAL_COLUMNS.items()
#     ]


# @router.get(
#     "/ingestion/mapping/{session_id}",
#     response_model=MappingSessionResponse,
#     summary="Get mapping session with proposals (AUDITOR+)",
# )
# async def get_mapping_session(
#     session_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingSessionResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text(
#             "SELECT session_id, ingestion_run_id, carrier_id, status, "
#             "auto_mapped_count, flagged_count, unmatched_count "
#             "FROM field_mapping_sessions WHERE session_id = :sid"
#         ),
#         {"sid": session_id},
#     )).fetchone()

#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)

#     proposals = [
#         MappingProposalResponse(
#             proposal_id=r[0], session_id=r[1], source_field=r[2], source_sample=r[3],
#             inferred_type=r[4], proposed_target=r[5], confidence=r[6],
#             score=float(r[7]) if r[7] is not None else 0.0,
#             transform_fn=r[8], is_excluded=bool(r[9]), match_reason=r[10],
#         )
#         for r in (await db.execute(
#             text(
#                 "SELECT proposal_id, session_id, source_field, source_sample, inferred_type, "
#                 "proposed_target, confidence, score, transform_fn, is_excluded, match_reason "
#                 "FROM field_mapping_proposals WHERE session_id = :sid "
#                 "ORDER BY confidence, source_field"
#             ),
#             {"sid": session_id},
#         )).fetchall()
#     ]

#     return MappingSessionResponse(
#         session_id=s[0], ingestion_run_id=s[1], carrier_id=s[2], status=s[3],
#         auto_mapped_count=s[4], flagged_count=s[5], unmatched_count=s[6],
#         proposals=proposals,
#     )


# @router.put(
#     "/ingestion/mapping/{session_id}/{proposal_id}",
#     summary="Update an individual mapping proposal (AUDITOR+)",
# )
# async def update_mapping_proposal(
#     session_id: int,
#     proposal_id: int,
#     body: MappingProposalUpdate,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> dict[str, Any]:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text("SELECT carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
#         {"sid": session_id},
#     )).fetchone()
#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
#     await verify_carrier_scope(s[0], token, db)

#     updates: list[str] = []
#     params: dict[str, Any] = {"pid": proposal_id, "sid": session_id}

#     if body.proposed_target is not None:
#         updates.append("proposed_target = :target")
#         params["target"] = body.proposed_target
#     if body.transform_fn is not None:
#         updates.append("transform_fn = :tfn")
#         params["tfn"] = body.transform_fn
#     if body.is_excluded is not None:
#         updates.append("is_excluded = :excl")
#         params["excl"] = body.is_excluded

#     if not updates:
#         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update.")

#     await db.execute(
#         text(f"UPDATE field_mapping_proposals SET {', '.join(updates)} WHERE proposal_id = :pid AND session_id = :sid"),
#         params,
#     )
#     await db.commit()
#     return {"proposal_id": proposal_id, "updated": True}


# # ---------------------------------------------------------------------------
# # Approve / Reject
# # ---------------------------------------------------------------------------

# @router.post(
#     "/ingestion/mapping/{session_id}/approve",
#     response_model=MappingApproveResponse,
#     summary="Approve mapping and trigger data ingestion (TENANT_ADMIN only)",
# )
# async def approve_mapping(
#     session_id: int,
#     request: Request,
#     background_tasks: BackgroundTasks,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingApproveResponse:
#     """
#     TENANT_ADMIN only.

#     1. Validates session is PENDING_REVIEW.
#     2. Marks session APPROVED and run as mapping_approved in the same transaction.
#     3. Re-asserts search_path then caches HIGH-confidence mappings to ingestion_field_maps.
#     4. Fires the post-approval ingestion pipeline as a BackgroundTask — returns immediately.
#        IngestionProgress.tsx polls GET /ingestion/runs/{id} to see status advance.
#     """
#     verify_role(Role.TENANT_ADMIN, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text(
#             "SELECT session_id, ingestion_run_id, carrier_id, status "
#             "FROM field_mapping_sessions WHERE session_id = :sid"
#         ),
#         {"sid": session_id},
#     )).fetchone()

#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)

#     if s[3] != "PENDING_REVIEW":
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail=f"Session is already '{s[3]}' and cannot be approved.",
#         )

#     run_id:      int = s[1]
#     carrier_id:  int = s[2]
#     schema_name: str = request.state.tenant.schema_name

#     # Step 1 — Mark approved synchronously so the UI sees it immediately
#     await db.execute(
#         text("UPDATE field_mapping_sessions SET status = 'APPROVED' WHERE session_id = :sid"),
#         {"sid": session_id},
#     )
#     await db.execute(
#         text("UPDATE ingestion_runs SET status = 'mapping_approved' WHERE run_id = :rid"),
#         {"rid": run_id},
#     )
#     await db.commit()

#     # Step 2 — Re-assert search_path (asyncpg resets it after every commit)
#     # then cache HIGH-confidence mappings for future Pass 1 hits
#     await _save_approved_mappings(session_id, carrier_id, db, schema_name)

#     # Step 3 — Fire the full ingestion pipeline in the background
#     async def _run_pipeline() -> None:
#         from app.core.database import _AsyncSessionLocal  # type: ignore[attr-defined]
#         if _AsyncSessionLocal is None:
#             logger.error("ingestion.background.no_session_factory", run_id=run_id)
#             return
#         async with _AsyncSessionLocal() as bg_db:
#             try:
#                 # SET search_path must be committed as its own transaction so
#                 # asyncpg's statement cache sees the correct schema before the
#                 # first DML statement is prepared. Without this commit, the
#                 # implicit transaction wrapping SET search_path is not yet
#                 # visible when the next statement is prepared, causing
#                 # "relation does not exist" errors for all tenant-schema tables.
#                 await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                 await bg_db.commit()
#                 # Re-set after commit so the session object also knows the path
#                 await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))

#                 await _ingestion_svc.run_post_approval(
#                     schema_name=schema_name,
#                     carrier_id=carrier_id,
#                     run_id=run_id,
#                     session_id=session_id,
#                     db=bg_db,
#                 )
#             except Exception as exc:
#                 logger.error(
#                     "ingestion.background.failed",
#                     run_id=run_id,
#                     session_id=session_id,
#                     error=str(exc),
#                 )
#                 # Mark run as failed so the polling stops
#                 try:
#                     await bg_db.rollback()
#                     await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                     await bg_db.execute(
#                         text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
#                         {"err": str(exc)[:2000], "rid": run_id},
#                     )
#                     await bg_db.commit()
#                 except Exception:
#                     pass

#     background_tasks.add_task(_run_pipeline)

#     return MappingApproveResponse(
#         session_id=session_id,
#         run_id=run_id,
#         status="processing",
#         message="Mapping approved. Ingestion pipeline running.",
#     )


# @router.post(
#     "/ingestion/mapping/{session_id}/reject",
#     response_model=MappingApproveResponse,
#     summary="Reject mapping and mark run as failed (TENANT_ADMIN only)",
# )
# async def reject_mapping(
#     session_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingApproveResponse:
#     verify_role(Role.TENANT_ADMIN, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text("SELECT session_id, ingestion_run_id, carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
#         {"sid": session_id},
#     )).fetchone()
#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)
#     run_id: int = s[1]

#     await db.execute(
#         text("UPDATE field_mapping_sessions SET status = 'REJECTED' WHERE session_id = :sid"),
#         {"sid": session_id},
#     )
#     await db.execute(
#         text("UPDATE ingestion_runs SET status = 'failed', error_detail = 'Mapping rejected by TENANT_ADMIN.' WHERE run_id = :rid"),
#         {"rid": run_id},
#     )
#     await db.commit()

#     return MappingApproveResponse(
#         session_id=session_id,
#         run_id=run_id,
#         status="failed",
#         message="Mapping rejected. Ingestion run marked as failed.",
#     )


# async def _save_approved_mappings(
#     session_id: int,
#     carrier_id: int,
#     db: AsyncSession,
#     schema_name: str,
# ) -> None:
#     """
#     Caches HIGH-confidence approved mappings into ingestion_field_maps for
#     future Pass 1 re-use by AutoMappingService.

#     Must re-assert search_path before querying because asyncpg resets the
#     connection's search_path to the server default after every db.commit().
#     """
#     # Re-assert search_path — mandatory after any prior commit on this session
#     # await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#     await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#     await db.commit()
#     await db.execute(text(f'SET search_path TO "{schema_name}", public'))

#     result = await db.execute(
#         text(
#             "SELECT source_field, proposed_target "
#             "FROM field_mapping_proposals "
#             "WHERE session_id = :sid AND confidence = 'HIGH' "
#             "AND is_excluded = FALSE AND proposed_target IS NOT NULL"
#         ),
#         {"sid": session_id},
#     )
#     rows = result.fetchall()

#     for row in rows:
#         try:
#             await db.execute(
#                 text("""
#                     INSERT INTO ingestion_field_maps (carrier_id, source_field, canonical_column)
#                     VALUES (:cid, :sf, :cc)
#                     ON CONFLICT (carrier_id, source_field) DO UPDATE
#                       SET canonical_column = EXCLUDED.canonical_column
#                 """),
#                 {"cid": carrier_id, "sf": row[0], "cc": row[1]},
#             )
#         except Exception as exc:
#             logger.warning("ingestion.save_mappings.row_failed", error=str(exc))

#     await db.commit()


# # ---------------------------------------------------------------------------
# # Manual audit trigger
# # ---------------------------------------------------------------------------

# @router.post(
#     "/audit/run",
#     response_model=AuditRunResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Manually trigger the audit calculation engine for a run (AUDITOR+)",
# )
# async def run_audit(
#     body: AuditRunRequest,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> AuditRunResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)
#     await verify_carrier_scope(body.carrier_id, token, db)

#     tenant = request.state.tenant

#     if body.override_use_engine is not None:
#         await db.execute(
#             text(
#                 "UPDATE ingestion_runs SET use_calculation_engine = :val "
#                 "WHERE run_id = :rid AND carrier_id = :cid"
#             ),
#             {"val": body.override_use_engine, "rid": body.ingestion_run_id, "cid": body.carrier_id},
#         )
#         await db.commit()

#     pol_result = await db.execute(
#         text(
#             "SELECT DISTINCT policy_id FROM premium_variance "
#             "WHERE ingestion_run_id = :rid AND carrier_id = :cid"
#         ),
#         {"rid": body.ingestion_run_id, "cid": body.carrier_id},
#     )
#     policy_ids = [r[0] for r in pol_result.fetchall()]

#     if not policy_ids:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No policies found for this ingestion run.",
#         )

#     result = await _calc_svc.run(
#         schema_name=tenant.schema_name,
#         carrier_id=body.carrier_id,
#         policy_id=policy_ids[0],
#         ingestion_run_id=body.ingestion_run_id,
#         db=db,
#     )

#     return AuditRunResponse(
#         policy_id=result.policy_id,
#         ingestion_run_id=result.ingestion_run_id,
#         skipped=result.skipped,
#         engine_ran=result.engine_ran,
#         risk_level=result.risk_level,
#         variance_amount=result.variance_amount,
#         variance_pct=result.variance_pct,
#         missing_payroll_count=result.missing_payroll_count,
#         zero_payroll_count=result.zero_payroll_count,
#         narrative_generated=result.narrative_generated,
#     )


# # ---------------------------------------------------------------------------
# # Run status polling
# # ---------------------------------------------------------------------------

# @router.get(
#     "/ingestion/runs/{run_id}",
#     response_model=IngestionRunStatusResponse,
#     summary="Poll the status of an ingestion run (REVIEWER+)",
# )
# async def get_run_status(
#     run_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> IngestionRunStatusResponse:
#     verify_role(Role.REVIEWER, token)
#     verify_tenant(request, token)

#     rec = (await db.execute(
#         text("""
#             SELECT run_id, status, rows_ingested, rows_skipped, rows_failed,
#                    error_detail, started_at::text, completed_at::text, carrier_id
#             FROM ingestion_runs
#             WHERE run_id = :run_id
#         """),
#         {"run_id": run_id},
#     )).mappings().one_or_none()

#     if rec is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Ingestion run {run_id} not found.",
#         )

#     await verify_carrier_scope(rec["carrier_id"], token, db)

#     return IngestionRunStatusResponse(
#         run_id=rec["run_id"],
#         status=rec["status"],
#         rows_ingested=rec["rows_ingested"],
#         rows_skipped=rec["rows_skipped"] or 0,
#         rows_failed=rec["rows_failed"] or 0,
#         error_detail=rec["error_detail"],
#         started_at=rec["started_at"] or "",
#         completed_at=rec["completed_at"],
#     )

# from __future__ import annotations

# """
# Ingestion API — Phase 3.

# Endpoints:
#   POST /ingestion/upload                              — upload file, generate mapping proposals
#   GET  /ingestion/mapping/canonical-columns           — list canonical target columns
#   GET  /ingestion/mapping/{session_id}                — get session + proposals
#   PUT  /ingestion/mapping/{session_id}/{proposal_id}  — update a proposal
#   POST /ingestion/mapping/{session_id}/approve        — TENANT_ADMIN approves (non-blocking)
#   POST /ingestion/mapping/{session_id}/reject         — TENANT_ADMIN rejects
#   GET  /ingestion/runs/{run_id}                       — poll run status
#   POST /audit/run                                     — manual calc engine trigger
# """

# import structlog
# from typing import Any, Optional

# from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
# from pydantic import BaseModel, ConfigDict
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.responses import AuditRunRequest, AuditRunResponse, IngestionRunResponse
# from app.services.audit_calculation_service import AuditCalculationService
# from app.services.auto_mapping_service import CANONICAL_COLUMNS
# from app.services.ingestion_service import IngestionService

# router = APIRouter()
# logger = structlog.get_logger(__name__)

# _ingestion_svc = IngestionService()
# _calc_svc = AuditCalculationService()


# # ---------------------------------------------------------------------------
# # Response schemas
# # ---------------------------------------------------------------------------

# class IngestionUploadResponse(BaseModel):
#     run_id: int
#     status: str
#     session_id: int
#     rows_ingested: Optional[int] = None
#     rows_skipped: int = 0
#     rows_failed: int = 0
#     error_detail: Optional[str] = None


# class IngestionRunStatusResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     run_id:        int
#     status:        str
#     rows_ingested: Optional[int]
#     rows_skipped:  int
#     rows_failed:   int
#     error_detail:  Optional[str]
#     started_at:    str
#     completed_at:  Optional[str]


# class MappingProposalResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     proposal_id:     int
#     session_id:      int
#     source_field:    str
#     source_sample:   Optional[str]
#     inferred_type:   str
#     proposed_target: Optional[str]
#     confidence:      str
#     score:           float
#     transform_fn:    str
#     is_excluded:     bool
#     match_reason:    str


# class MappingSessionResponse(BaseModel):
#     session_id:        int
#     ingestion_run_id:  int
#     carrier_id:        int
#     status:            str
#     auto_mapped_count: int
#     flagged_count:     int
#     unmatched_count:   int
#     proposals:         list[MappingProposalResponse]


# class MappingProposalUpdate(BaseModel):
#     proposed_target: Optional[str] = None
#     transform_fn:    Optional[str] = None
#     is_excluded:     Optional[bool] = None


# class MappingApproveResponse(BaseModel):
#     session_id: int
#     run_id:     int
#     status:     str
#     message:    str


# # ---------------------------------------------------------------------------
# # Upload
# # ---------------------------------------------------------------------------

# @router.post(
#     "/ingestion/upload",
#     response_model=IngestionUploadResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Upload a file and trigger auto-mapping (AUDITOR+)",
# )


# async def upload_file(
#     request: Request,
#     carrier_id: int = Form(...),
#     source_id: int = Form(...),
#     file: UploadFile = File(...),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> IngestionUploadResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)
#     await verify_carrier_scope(carrier_id, token, db)

#     filename = (file.filename or "").lower()

#     print("filename:", file.filename)
#     print("content_type:", file.content_type)
#     filename = (file.filename or "").lower()

#     if filename.endswith(".xlsx") or file.content_type in (
#         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         "application/octet-stream",
#     ):
#         file_type = "xlsx"
#     elif filename.endswith(".xml") or file.content_type in (
#         "text/xml",
#         "application/xml",
#     ):
#         file_type = "xml"
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail=f"Unsupported file type. Accepted: .xlsx, .xml. Got: {file.filename}",
#         )

#     file_bytes = await file.read()
#     tenant = request.state.tenant
#     print("file type in the ingestion upload",file_type)
#     run_id, session_id = await _ingestion_svc.run(
#         schema_name=tenant.schema_name,
#         carrier_id=carrier_id,
#         source_id=source_id,
#         file_bytes=file_bytes,
#         file_type=file_type,
#         db=db,
#         uploaded_by=token.email,
#     )

#     # Store file bytes for post-approval retrieval (Phase 4: replace with S3)
#     await _store_file_bytes(run_id, file_bytes, db, tenant.schema_name)

#     return IngestionUploadResponse(
#         run_id=run_id,
#         status="awaiting_mapping",
#         session_id=session_id,
#     )


# async def _store_file_bytes(
#     run_id: int,
#     file_bytes: bytes,
#     db: AsyncSession,
#     schema_name: str,
# ) -> None:
#     """Stores raw file bytes on ingestion_run for post-approval retrieval."""
#     try:
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.commit()
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.execute(
#             text("UPDATE ingestion_runs SET raw_file_bytes = :fb WHERE run_id = :rid"),
#             {"fb": file_bytes, "rid": run_id},
#         )
#         await db.commit()
#     except Exception as exc:
#         logger.warning("ingestion.store_file_bytes.failed", run_id=run_id, error=str(exc))
#         try:
#             await db.rollback()
#         except Exception:
#             pass


# # ---------------------------------------------------------------------------
# # Mapping gate — read endpoints
# # ---------------------------------------------------------------------------

# @router.get(
#     "/ingestion/mapping/canonical-columns",
#     summary="List all canonical target column names (AUDITOR+)",
# )
# async def list_canonical_columns(
#     request: Request,
#     token: TokenPayload = Depends(get_current_user),
# ) -> list[dict[str, str]]:
#     verify_role(Role.AUDITOR, token)
#     return [
#         {"column_name": col, "data_type": dtype}
#         for col, dtype in CANONICAL_COLUMNS.items()
#     ]


# @router.get(
#     "/ingestion/mapping/{session_id}",
#     response_model=MappingSessionResponse,
#     summary="Get mapping session with proposals (AUDITOR+)",
# )
# async def get_mapping_session(
#     session_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingSessionResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text(
#             "SELECT session_id, ingestion_run_id, carrier_id, status, "
#             "auto_mapped_count, flagged_count, unmatched_count "
#             "FROM field_mapping_sessions WHERE session_id = :sid"
#         ),
#         {"sid": session_id},
#     )).fetchone()

#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)

#     proposals = [
#         MappingProposalResponse(
#             proposal_id=r[0], session_id=r[1], source_field=r[2], source_sample=r[3],
#             inferred_type=r[4], proposed_target=r[5], confidence=r[6],
#             score=float(r[7]) if r[7] is not None else 0.0,
#             transform_fn=r[8], is_excluded=bool(r[9]), match_reason=r[10],
#         )
#         for r in (await db.execute(
#             text(
#                 "SELECT proposal_id, session_id, source_field, source_sample, inferred_type, "
#                 "proposed_target, confidence, score, transform_fn, is_excluded, match_reason "
#                 "FROM field_mapping_proposals WHERE session_id = :sid "
#                 "ORDER BY confidence, source_field"
#             ),
#             {"sid": session_id},
#         )).fetchall()
#     ]

#     return MappingSessionResponse(
#         session_id=s[0], ingestion_run_id=s[1], carrier_id=s[2], status=s[3],
#         auto_mapped_count=s[4], flagged_count=s[5], unmatched_count=s[6],
#         proposals=proposals,
#     )


# @router.put(
#     "/ingestion/mapping/{session_id}/{proposal_id}",
#     summary="Update an individual mapping proposal (AUDITOR+)",
# )
# async def update_mapping_proposal(
#     session_id: int,
#     proposal_id: int,
#     body: MappingProposalUpdate,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> dict[str, Any]:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text("SELECT carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
#         {"sid": session_id},
#     )).fetchone()
#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")
#     await verify_carrier_scope(s[0], token, db)

#     updates: list[str] = []
#     params: dict[str, Any] = {"pid": proposal_id, "sid": session_id}

#     if body.proposed_target is not None:
#         updates.append("proposed_target = :target")
#         params["target"] = body.proposed_target
#     if body.transform_fn is not None:
#         updates.append("transform_fn = :tfn")
#         params["tfn"] = body.transform_fn
#     if body.is_excluded is not None:
#         updates.append("is_excluded = :excl")
#         params["excl"] = body.is_excluded

#     if not updates:
#         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update.")

#     await db.execute(
#         text(f"UPDATE field_mapping_proposals SET {', '.join(updates)} WHERE proposal_id = :pid AND session_id = :sid"),
#         params,
#     )
#     await db.commit()
#     return {"proposal_id": proposal_id, "updated": True}


# # ---------------------------------------------------------------------------
# # Approve / Reject
# # ---------------------------------------------------------------------------

# @router.post(
#     "/ingestion/mapping/{session_id}/approve",
#     response_model=MappingApproveResponse,
#     summary="Approve mapping and trigger data ingestion (TENANT_ADMIN only)",
# )
# async def approve_mapping(
#     session_id: int,
#     request: Request,
#     background_tasks: BackgroundTasks,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingApproveResponse:
#     """
#     TENANT_ADMIN only.

#     1. Validates session is PENDING_REVIEW.
#     2. Marks session APPROVED and run as mapping_approved in the same transaction.
#     3. Re-asserts search_path then caches HIGH-confidence mappings to ingestion_field_maps.
#     4. Fires the post-approval ingestion pipeline as a BackgroundTask — returns immediately.
#        IngestionProgress.tsx polls GET /ingestion/runs/{id} to see status advance.
#     """
#     verify_role(Role.TENANT_ADMIN, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text(
#             "SELECT session_id, ingestion_run_id, carrier_id, status "
#             "FROM field_mapping_sessions WHERE session_id = :sid"
#         ),
#         {"sid": session_id},
#     )).fetchone()

#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)

#     if s[3] != "PENDING_REVIEW":
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail=f"Session is already '{s[3]}' and cannot be approved.",
#         )

#     run_id:      int = s[1]
#     carrier_id:  int = s[2]
#     schema_name: str = request.state.tenant.schema_name

#     # Step 1 — Mark approved synchronously so the UI sees it immediately
#     await db.execute(
#         text("UPDATE field_mapping_sessions SET status = 'APPROVED' WHERE session_id = :sid"),
#         {"sid": session_id},
#     )
#     await db.execute(
#         text("UPDATE ingestion_runs SET status = 'mapping_approved' WHERE run_id = :rid"),
#         {"rid": run_id},
#     )
#     await db.commit()

#     # Step 2 — Re-assert search_path (asyncpg resets it after every commit)
#     # then cache HIGH-confidence mappings for future Pass 1 hits
#     await _save_approved_mappings(session_id, carrier_id, db, schema_name)

#     # Step 3 — Fire the full ingestion pipeline in the background
#     async def _run_pipeline() -> None:
#         from app.core.database import _AsyncSessionLocal  # type: ignore[attr-defined]
#         if _AsyncSessionLocal is None:
#             logger.error("ingestion.background.no_session_factory", run_id=run_id)
#             return
#         async with _AsyncSessionLocal() as bg_db:
#             try:
#                 # SET search_path must be committed as its own transaction so
#                 # asyncpg's statement cache sees the correct schema before the
#                 # first DML statement is prepared. Without this commit, the
#                 # implicit transaction wrapping SET search_path is not yet
#                 # visible when the next statement is prepared, causing
#                 # "relation does not exist" errors for all tenant-schema tables.
#                 await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                 await bg_db.commit()
#                 # Re-set after commit so the session object also knows the path
#                 await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))

#                 await _ingestion_svc.run_post_approval(
#                     schema_name=schema_name,
#                     carrier_id=carrier_id,
#                     run_id=run_id,
#                     session_id=session_id,
#                     db=bg_db,
#                 )
#             except Exception as exc:
#                 logger.error(
#                     "ingestion.background.failed",
#                     run_id=run_id,
#                     session_id=session_id,
#                     error=str(exc),
#                 )
#                 # Mark run as failed so the polling stops
#                 try:
#                     await bg_db.rollback()
#                     await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                     await bg_db.execute(
#                         text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
#                         {"err": str(exc)[:2000], "rid": run_id},
#                     )
#                     await bg_db.commit()
#                 except Exception:
#                     pass

#     background_tasks.add_task(_run_pipeline)

#     return MappingApproveResponse(
#         session_id=session_id,
#         run_id=run_id,
#         status="processing",
#         message="Mapping approved. Ingestion pipeline running.",
#     )


# @router.post(
#     "/ingestion/mapping/{session_id}/reject",
#     response_model=MappingApproveResponse,
#     summary="Reject mapping and mark run as failed (TENANT_ADMIN only)",
# )
# async def reject_mapping(
#     session_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> MappingApproveResponse:
#     verify_role(Role.TENANT_ADMIN, token)
#     verify_tenant(request, token)

#     s = (await db.execute(
#         text("SELECT session_id, ingestion_run_id, carrier_id FROM field_mapping_sessions WHERE session_id = :sid"),
#         {"sid": session_id},
#     )).fetchone()
#     if s is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping session not found.")

#     await verify_carrier_scope(s[2], token, db)
#     run_id: int = s[1]

#     await db.execute(
#         text("UPDATE field_mapping_sessions SET status = 'REJECTED' WHERE session_id = :sid"),
#         {"sid": session_id},
#     )
#     await db.execute(
#         text("UPDATE ingestion_runs SET status = 'failed', error_detail = 'Mapping rejected by TENANT_ADMIN.' WHERE run_id = :rid"),
#         {"rid": run_id},
#     )
#     await db.commit()

#     return MappingApproveResponse(
#         session_id=session_id,
#         run_id=run_id,
#         status="failed",
#         message="Mapping rejected. Ingestion run marked as failed.",
#     )


# async def _save_approved_mappings(
#     session_id: int,
#     carrier_id: int,
#     db: AsyncSession,
#     schema_name: str,
# ) -> None:
#     """
#     Caches HIGH-confidence approved mappings into ingestion_field_maps for
#     future Pass 1 re-use by AutoMappingService.

#     Must re-assert search_path before querying because asyncpg resets the
#     connection's search_path to the server default after every db.commit().
#     """
#     # Re-assert search_path — mandatory after any prior commit on this session
#     # await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#     await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#     await db.commit()
#     await db.execute(text(f'SET search_path TO "{schema_name}", public'))

#     result = await db.execute(
#         text(
#             "SELECT source_field, proposed_target "
#             "FROM field_mapping_proposals "
#             "WHERE session_id = :sid AND confidence = 'HIGH' "
#             "AND is_excluded = FALSE AND proposed_target IS NOT NULL"
#         ),
#         {"sid": session_id},
#     )
#     rows = result.fetchall()

#     for row in rows:
#         try:
#             await db.execute(
#                 text("""
#                     INSERT INTO ingestion_field_maps (carrier_id, source_field, canonical_column)
#                     VALUES (:cid, :sf, :cc)
#                     ON CONFLICT (carrier_id, source_field) DO UPDATE
#                       SET canonical_column = EXCLUDED.canonical_column
#                 """),
#                 {"cid": carrier_id, "sf": row[0], "cc": row[1]},
#             )
#         except Exception as exc:
#             logger.warning("ingestion.save_mappings.row_failed", error=str(exc))

#     await db.commit()


# # ---------------------------------------------------------------------------
# # Manual audit trigger
# # ---------------------------------------------------------------------------

# @router.post(
#     "/audit/run",
#     response_model=AuditRunResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Manually trigger the audit calculation engine for a run (AUDITOR+)",
# )
# async def run_audit(
#     body: AuditRunRequest,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> AuditRunResponse:
#     verify_role(Role.AUDITOR, token)
#     verify_tenant(request, token)
#     await verify_carrier_scope(body.carrier_id, token, db)

#     tenant = request.state.tenant

#     if body.override_use_engine is not None:
#         await db.execute(
#             text(
#                 "UPDATE ingestion_runs SET use_calculation_engine = :val "
#                 "WHERE run_id = :rid AND carrier_id = :cid"
#             ),
#             {"val": body.override_use_engine, "rid": body.ingestion_run_id, "cid": body.carrier_id},
#         )
#         await db.commit()

#     pol_result = await db.execute(
#         text(
#             "SELECT DISTINCT policy_id FROM premium_variance "
#             "WHERE ingestion_run_id = :rid AND carrier_id = :cid"
#         ),
#         {"rid": body.ingestion_run_id, "cid": body.carrier_id},
#     )
#     policy_ids = [r[0] for r in pol_result.fetchall()]

#     if not policy_ids:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No policies found for this ingestion run.",
#         )

#     result = await _calc_svc.run(
#         schema_name=tenant.schema_name,
#         carrier_id=body.carrier_id,
#         policy_id=policy_ids[0],
#         ingestion_run_id=body.ingestion_run_id,
#         db=db,
#     )

#     return AuditRunResponse(
#         policy_id=result.policy_id,
#         ingestion_run_id=result.ingestion_run_id,
#         skipped=result.skipped,
#         engine_ran=result.engine_ran,
#         risk_level=result.risk_level,
#         variance_amount=result.variance_amount,
#         variance_pct=result.variance_pct,
#         missing_payroll_count=result.missing_payroll_count,
#         zero_payroll_count=result.zero_payroll_count,
#         narrative_generated=result.narrative_generated,
#     )


# # ---------------------------------------------------------------------------
# # Run status polling
# # ---------------------------------------------------------------------------

# @router.get(
#     "/ingestion/runs/{run_id}",
#     response_model=IngestionRunStatusResponse,
#     summary="Poll the status of an ingestion run (REVIEWER+)",
# )
# async def get_run_status(
#     run_id: int,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> IngestionRunStatusResponse:
#     verify_role(Role.REVIEWER, token)
#     verify_tenant(request, token)

#     rec = (await db.execute(
#         text("""
#             SELECT run_id, status, rows_ingested, rows_skipped, rows_failed,
#                    error_detail, started_at::text, completed_at::text, carrier_id
#             FROM ingestion_runs
#             WHERE run_id = :run_id
#         """),
#         {"run_id": run_id},
#     )).mappings().one_or_none()

#     if rec is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Ingestion run {run_id} not found.",
#         )

#     await verify_carrier_scope(rec["carrier_id"], token, db)

#     return IngestionRunStatusResponse(
#         run_id=rec["run_id"],
#         status=rec["status"],
#         rows_ingested=rec["rows_ingested"],
#         rows_skipped=rec["rows_skipped"] or 0,
#         rows_failed=rec["rows_failed"] or 0,
#         error_detail=rec["error_detail"],
#         started_at=rec["started_at"] or "",
#         completed_at=rec["completed_at"],
#     )

from __future__ import annotations

"""
Ingestion API — Phase 3.

Endpoints:
  POST /ingestion/upload                              — upload file, generate mapping proposals
  GET  /ingestion/mapping/canonical-columns           — list canonical target columns
  GET  /ingestion/mapping/{session_id}                — get session + proposals
  PUT  /ingestion/mapping/{session_id}/{proposal_id}  — update a proposal
  POST /ingestion/mapping/{session_id}/approve        — TENANT_ADMIN approves (non-blocking)
  POST /ingestion/mapping/{session_id}/reject         — TENANT_ADMIN rejects
  GET  /ingestion/runs/{run_id}                       — poll run status
  POST /audit/run                                     — manual calc engine trigger
"""

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
from app.services.ingestion_service import IngestionService

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

    filename = (file.filename or "").lower()

    if filename.endswith(".xlsx") or file.content_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    ):
        file_type = "xlsx"
    elif filename.endswith(".xml") or file.content_type in (
        "text/xml",
        "application/xml",
    ):
        file_type = "xml"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type. Accepted: .xlsx, .xml. Got: {file.filename}",
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

    if body.override_use_engine is not None:
        await db.execute(
            text(
                "UPDATE ingestion_runs SET use_calculation_engine = :val "
                "WHERE run_id = :rid AND carrier_id = :cid"
            ),
            {"val": body.override_use_engine, "rid": body.ingestion_run_id, "cid": body.carrier_id},
        )
        await db.commit()

    pol_result = await db.execute(
        text(
            "SELECT DISTINCT policy_id FROM premium_variance "
            "WHERE ingestion_run_id = :rid AND carrier_id = :cid"
        ),
        {"rid": body.ingestion_run_id, "cid": body.carrier_id},
    )
    policy_ids = [r[0] for r in pol_result.fetchall()]

    if not policy_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No policies found for this ingestion run.",
        )

    result = await _calc_svc.run(
        schema_name=tenant.schema_name,
        carrier_id=body.carrier_id,
        policy_id=policy_ids[0],
        ingestion_run_id=body.ingestion_run_id,
        db=db,
    )

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
        narrative_generated=result.narrative_generated,
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