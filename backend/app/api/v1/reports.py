from __future__ import annotations

"""
Reports API Router — Phase 5.

Per V9 S21.2 and V9 S25.4.

Endpoints:
  POST /api/v1/reports/generate
       AUDITOR+. Creates a report job and enqueues background generation.
       Returns 202 immediately with {job_id}.

  GET  /api/v1/reports/{job_id}/status
       REVIEWER+. Polls job status. Returns file_url when COMPLETE.

  GET  /api/v1/admin/report-template/{carrier_id}
       TENANT_ADMIN. Returns carrier_report_templates row.

  PUT  /api/v1/admin/report-template/{carrier_id}
       TENANT_ADMIN. Upserts carrier_report_templates branding.

  POST /api/v1/tenant/branding/report-logo/{carrier_id}
       TENANT_ADMIN. Uploads report logo to S3 → writes logo_url to DB (S3 atomicity).
"""

import re
import uuid as _uuid_module
from typing import Any, Optional

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import (
    Role,
    get_current_user,
    verify_carrier_scope,
    verify_role,
    verify_tenant,
)
from app.core.config import get_settings
from app.schemas.auth import TokenPayload
from app.services.report_generation_service import (
    EXCEL_ONLY_REPORT_TYPES,
    VALID_OUTPUT_FORMATS,
    VALID_REPORT_TYPES,
    ReportGenerationService,
)
from app.services.report_job_service import ReportJobService
from app.services.s3_service import S3Service

logger = structlog.get_logger(__name__)
router = APIRouter()

_report_job_svc = ReportJobService()
_report_gen_svc = ReportGenerationService()
_s3_svc = S3Service()

# Regex: 6-char hex without # prefix
_HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────────────────────


class GenerateReportRequest(BaseModel):
    """Body for POST /api/v1/reports/generate."""

    carrier_id: int
    report_type: str
    output_format: str
    policy_id: Optional[int] = None
    run_id: Optional[int] = None

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        if v not in VALID_REPORT_TYPES:
            raise ValueError(f"Invalid report_type '{v}'")
        return v

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        if v not in VALID_OUTPUT_FORMATS:
            raise ValueError(f"Invalid output_format '{v}'")
        return v


class GenerateReportResponse(BaseModel):
    """Response for POST /api/v1/reports/generate — 202 Accepted."""

    job_id: str


class ReportJobStatusResponse(BaseModel):
    """Response for GET /api/v1/reports/{job_id}/status."""

    job_id: str
    status: str
    file_url: Optional[str]
    report_type: str
    output_format: str
    requested_at: Optional[str]
    completed_at: Optional[str]
    error_detail: Optional[str]


class ReportTemplateBody(BaseModel):
    """Body for PUT /api/v1/admin/report-template/{carrier_id}."""

    logo_url: Optional[str] = None
    primary_colour: Optional[str] = None
    secondary_colour: Optional[str] = None
    contact_block: Optional[str] = None

    @field_validator("primary_colour", "secondary_colour", mode="before")
    @classmethod
    def validate_hex_colour(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.lstrip("#")
        if not _HEX_RE.match(stripped):
            raise ValueError(
                f"Colour must be a 6-character hex value (e.g. '1A3C5E'), got '{v}'"
            )
        return stripped


class ReportTemplateResponse(BaseModel):
    """Response for GET/PUT /api/v1/admin/report-template/{carrier_id}."""

    carrier_id: int
    logo_url: Optional[str]
    primary_colour: Optional[str]
    secondary_colour: Optional[str]
    contact_block: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/reports/generate — AUDITOR+
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/reports/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateReportResponse,
    summary="Generate a report (async — returns job_id for polling)",
)
async def generate_report(
    body: GenerateReportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> GenerateReportResponse:
    """
    Validates the request, creates a report job (QUEUED), and enqueues background
    generation. Returns 202 immediately with {job_id}.

    Client polls GET /reports/{job_id}/status every 3s until status=COMPLETE.
    When COMPLETE, file_url contains the pre-signed S3 download URL (24h TTL).

    RBAC: AUDITOR+ (V9 S25.4).
    Validates report_type/output_format combination — Excel-only types with
    output_format='pdf' return HTTP 422.
    """
    verify_role(Role.AUDITOR, token)
    verify_tenant(request, token)
    await verify_carrier_scope(body.carrier_id, token, db)

    # Cross-validate type + format + required params
    try:
        _report_gen_svc.validate_report_request(
            report_type=body.report_type,
            output_format=body.output_format,
            policy_id=body.policy_id,
            run_id=body.run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    schema_name: str = request.state.tenant.schema_name

    job_id = await _report_job_svc.create_job(
        carrier_id=body.carrier_id,
        policy_id=body.policy_id,
        report_type=body.report_type,
        output_format=body.output_format,
        run_id=body.run_id,
        requested_by=token.sub,
        schema_name=schema_name,
        db=db,
    )

    # Enqueue background generation — response returns before this completes
    background_tasks.add_task(
        _report_job_svc.run_job,
        job_id=job_id,
        carrier_id=body.carrier_id,
        policy_id=body.policy_id,
        report_type=body.report_type,
        output_format=body.output_format,
        run_id=body.run_id,
        schema_name=schema_name,
        db=db,
    )

    logger.info(
        "report.generate.accepted",
        job_id=str(job_id),
        report_type=body.report_type,
        output_format=body.output_format,
        carrier_id=body.carrier_id,
    )

    return GenerateReportResponse(job_id=str(job_id))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/reports/{job_id}/status — REVIEWER+
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/reports/{job_id}/status",
    response_model=ReportJobStatusResponse,
    summary="Poll report job status",
)
async def get_report_status(
    job_id: _uuid_module.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ReportJobStatusResponse:
    """
    Returns the current status of a report job.
    When status='COMPLETE', file_url contains the pre-signed S3 URL (24h TTL).

    Carrier scope is enforced by fetching the job's carrier_id from DB and
    verifying it belongs to the current tenant via tenant_carriers.

    RBAC: REVIEWER+ (V9 S25.4 — REVIEWER can poll status and download).
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    # Fetch job to get its carrier_id for scope check
    row_result = await db.execute(
        text(
            "SELECT job_id, carrier_id, status, file_url, report_type, "
            "output_format, requested_at, completed_at, error_detail "
            "FROM report_jobs WHERE job_id = :jid"
        ),
        {"jid": job_id},
    )
    row = row_result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job {job_id} not found.",
        )

    job_carrier_id: int = row[1]

    # Verify the job's carrier belongs to this tenant
    await verify_carrier_scope(job_carrier_id, token, db)

    return ReportJobStatusResponse(
        job_id=str(row[0]),
        status=row[2],
        file_url=row[3],
        report_type=row[4],
        output_format=row[5],
        requested_at=row[6].isoformat() if row[6] else None,
        completed_at=row[7].isoformat() if row[7] else None,
        error_detail=row[8],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Report Template CRUD — TENANT_ADMIN
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/admin/report-template/{carrier_id}",
    response_model=ReportTemplateResponse,
    summary="Get carrier report template branding",
)
async def get_report_template(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ReportTemplateResponse:
    """
    Returns the carrier_report_templates row for a carrier.
    Returns null fields if no template has been configured yet.
    TENANT_ADMIN only.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT carrier_id, logo_url, primary_colour, secondary_colour, contact_block "
            "FROM carrier_report_templates WHERE carrier_id = :cid"
        ),
        {"cid": carrier_id},
    )
    row = result.fetchone()
    if row is None:
        return ReportTemplateResponse(
            carrier_id=carrier_id,
            logo_url=None,
            primary_colour=None,
            secondary_colour=None,
            contact_block=None,
        )
    return ReportTemplateResponse(
        carrier_id=row[0],
        logo_url=row[1],
        primary_colour=row[2],
        secondary_colour=row[3],
        contact_block=row[4],
    )


@router.put(
    "/admin/report-template/{carrier_id}",
    response_model=ReportTemplateResponse,
    summary="Save carrier report template branding",
)
async def put_report_template(
    carrier_id: int,
    body: ReportTemplateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ReportTemplateResponse:
    """
    Upserts the carrier_report_templates row.
    Null values in the body clear the corresponding field.
    TENANT_ADMIN only.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    await db.execute(
        text(
            """
            INSERT INTO carrier_report_templates
              (carrier_id, logo_url, primary_colour, secondary_colour, contact_block)
            VALUES
              (:cid, :logo_url, :primary_colour, :secondary_colour, :contact_block)
            ON CONFLICT (carrier_id) DO UPDATE SET
              logo_url         = EXCLUDED.logo_url,
              primary_colour   = EXCLUDED.primary_colour,
              secondary_colour = EXCLUDED.secondary_colour,
              contact_block    = EXCLUDED.contact_block
            """
        ),
        {
            "cid": carrier_id,
            "logo_url": body.logo_url,
            "primary_colour": body.primary_colour,
            "secondary_colour": body.secondary_colour,
            "contact_block": body.contact_block,
        },
    )
    await db.commit()

    logger.info("report_template.saved", carrier_id=carrier_id, sub=token.sub)

    return ReportTemplateResponse(
        carrier_id=carrier_id,
        logo_url=body.logo_url,
        primary_colour=body.primary_colour,
        secondary_colour=body.secondary_colour,
        contact_block=body.contact_block,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/tenant/branding/report-logo/{carrier_id} — TENANT_ADMIN
# S3 atomicity: logo_url written ONLY after S3 upload confirms.
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenant/branding/report-logo/{carrier_id}",
    status_code=status.HTTP_200_OK,
    summary="Upload carrier-specific report logo to S3",
)
async def upload_report_logo(
    carrier_id: int,
    file: UploadFile,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    """
    Uploads a carrier-specific report logo to S3 and writes the URL to
    carrier_report_templates.logo_url.

    S3 atomicity (V9 S21.2): logo_url is written to DB ONLY after S3 upload
    confirms. A failed upload leaves logo_url unchanged.

    TENANT_ADMIN only.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    settings = get_settings()
    schema_name: str = request.state.tenant.schema_name

    # Validate file type
    filename = file.filename or "logo.png"
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in {"png", "jpg", "jpeg", "svg", "gif", "webp"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Logo must be an image file (png, jpg, jpeg, svg, gif, webp).",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Logo file must be smaller than 5 MB.",
        )

    import uuid as _u
    object_key = f"report-logos/{schema_name}/{carrier_id}/{_u.uuid4()}.{extension}"
    content_type = file.content_type or f"image/{extension}"

    # Step 1 — Upload to S3 (raises on failure; DB is NOT touched until success)
    try:
        _s3_svc.upload_bytes(
            key=object_key,
            data=file_bytes,
            content_type=content_type,
        )
    except Exception as exc:
        logger.error("report_logo.s3_upload_failed", carrier_id=carrier_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload logo to object storage.",
        ) from exc

    # Construct URL (MinIO path-style for local dev; S3 virtual-hosted for production)
    endpoint = (
        settings.S3_ENDPOINT_URL
        if settings.S3_ENDPOINT_URL
        else f"https://s3.{settings.AWS_REGION}.amazonaws.com"
    )
    logo_url = f"{endpoint}/{settings.S3_BUCKET}/{object_key}"

    # Step 2 — Write logo_url to DB (only reached after successful S3 upload)
    await db.execute(
        text(
            """
            INSERT INTO carrier_report_templates (carrier_id, logo_url)
            VALUES (:cid, :url)
            ON CONFLICT (carrier_id) DO UPDATE SET logo_url = EXCLUDED.logo_url
            """
        ),
        {"cid": carrier_id, "url": logo_url},
    )
    await db.commit()

    logger.info("report_logo.uploaded", carrier_id=carrier_id, logo_url=logo_url)
    return {"logo_url": logo_url}
