"""
Database Cleanup API — Phase 6.

Provides the three-endpoint monthly cleanup workflow per V9 S22 and S25.4.

Endpoints:
  POST /api/v1/database-cleanup/preview   → CleanupPreviewResponse   TENANT_ADMIN
  POST /api/v1/database-cleanup/execute   → CleanupExecuteResponse   TENANT_ADMIN
  GET  /api/v1/database-cleanup/history   → list[CleanupRunResponse] TENANT_ADMIN

The execute endpoint requires the exact confirmation string "CONFIRM" in the
request body as a server-side safety gate (V9 S22.5). Lowercase or any other
value returns HTTP 422.

RBAC: All three endpoints require TENANT_ADMIN. SUPER_ADMIN is excluded —
cleanup is a per-tenant operation and requires a resolved tenant context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.services.cleanup_service import CleanupService

router = APIRouter(prefix="/api/v1/database-cleanup", tags=["Database Cleanup"])

_cleanup_svc = CleanupService()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CleanupPreviewResponse(BaseModel):
    """Row counts for every table that would be affected by execute()."""

    premium_variance: int
    payroll_variance_class: int
    payroll_variance_policy: int
    zero_payroll: int
    missing_payroll: int
    policies: int
    policyholders: int
    ingestion_runs: int
    ingestion_errors: int
    ingestion_skipped_rows: int
    ingestion_rollbacks: int
    field_mapping_sessions: int
    field_mapping_proposals: int
    report_jobs: int


class CleanupExecuteRequest(BaseModel):
    """
    Request body for the execute endpoint.

    The confirm field must be the exact string "CONFIRM" (case-sensitive).
    Any other value is rejected with HTTP 422 before the service is called.
    """

    confirm: str

    @field_validator("confirm")
    @classmethod
    def must_be_exact_confirmation(cls, value: str) -> str:
        if value != "CONFIRM":
            raise ValueError(
                "Confirmation string must be exactly 'CONFIRM' (case-sensitive)."
            )
        return value


class CleanupExecuteResponse(BaseModel):
    """Result returned after a successful cleanup execution."""

    model_config = ConfigDict(from_attributes=True)

    cleanup_id: int
    status: str
    policies_archived: Optional[int]
    completed_at: Optional[datetime]


class CleanupRunResponse(BaseModel):
    """Single entry from the cleanup_runs audit log."""

    model_config = ConfigDict(from_attributes=True)

    cleanup_id: int
    initiated_by: str
    initiated_at: datetime
    status: str
    policies_archived: Optional[int]
    completed_at: Optional[datetime]
    error_detail: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/preview",
    response_model=CleanupPreviewResponse,
    summary="Preview cleanup — count rows that would be deleted (TENANT_ADMIN)",
)
async def preview_cleanup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CleanupPreviewResponse:
    """
    Returns row counts for every table that would be deleted by execute().
    This endpoint is read-only — it never modifies the database.

    Use this before execute() so the operator can confirm the scope of
    the cleanup before committing.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    counts = await _cleanup_svc.preview(db=db)
    return CleanupPreviewResponse(**counts)


@router.post(
    "/execute",
    response_model=CleanupExecuteResponse,
    summary="Execute cleanup — delete all operational data (TENANT_ADMIN)",
)
async def execute_cleanup(
    request: Request,
    body: CleanupExecuteRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CleanupExecuteResponse:
    """
    Deletes all operational data for the tenant in a single transaction.

    The request body must contain { "confirm": "CONFIRM" } (case-sensitive).
    Any other value is rejected with HTTP 422 before any deletion occurs.

    After a successful execution, returns the cleanup_id and summary counts.
    Configuration, labels, themes, and the cleanup_runs audit log are
    never affected.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # The field_validator on CleanupExecuteRequest already ensures confirm == "CONFIRM".
    # This explicit guard is a defence-in-depth double-check.
    if body.confirm != "CONFIRM":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirmation string required. Send exactly: { \"confirm\": \"CONFIRM\" }",
        )

    cleanup_id = await _cleanup_svc.execute(
        initiated_by=token.sub,
        db=db,
    )

    # Fetch the completed cleanup_runs row to return a full response.
    result = await db.execute(
        text(
            "SELECT cleanup_id, status, policies_archived, completed_at "
            "FROM cleanup_runs WHERE cleanup_id = :cleanup_id"
        ),
        {"cleanup_id": cleanup_id},
    )
    row = result.mappings().one()
    return CleanupExecuteResponse(**dict(row))


@router.get(
    "/history",
    response_model=list[CleanupRunResponse],
    summary="List cleanup history — last 20 runs (TENANT_ADMIN)",
)
async def get_cleanup_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[CleanupRunResponse]:
    """
    Returns the last 20 cleanup_runs rows for this tenant, ordered by
    initiated_at descending (most recent first).
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            """
            SELECT cleanup_id, initiated_by, initiated_at,
                   status, policies_archived, completed_at, error_detail
            FROM cleanup_runs
            ORDER BY initiated_at DESC
            LIMIT 20
            """
        )
    )
    rows = result.mappings().all()
    return [CleanupRunResponse(**dict(row)) for row in rows]
