"""
tenant_admin.py — TENANT_ADMIN /api/v1/tenant/* endpoints (V9 S13, S14, S25.4)

Endpoints:
  GET  /api/v1/tenant/profile               REVIEWER+
  PUT  /api/v1/tenant/profile               TENANT_ADMIN
  GET  /api/v1/tenant/contacts              REVIEWER+
  PUT  /api/v1/tenant/contacts              TENANT_ADMIN
  GET  /api/v1/tenant/branding              REVIEWER+
  PUT  /api/v1/tenant/branding              TENANT_ADMIN
  POST /api/v1/tenant/branding/logo         TENANT_ADMIN  — S3 atomic upload
  GET  /api/v1/tenant/users                 TENANT_ADMIN
  GET  /api/v1/tenant/users/me              REVIEWER+
  POST /api/v1/tenant/users                 TENANT_ADMIN
  PATCH /api/v1/tenant/users/{user_id}      TENANT_ADMIN
  DELETE /api/v1/tenant/users/{user_id}     TENANT_ADMIN
  GET  /api/v1/tenant/carriers              REVIEWER+
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

import boto3
import botocore.exceptions
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_role, verify_tenant
from app.core.config import get_settings
from app.schemas.auth import Role, TokenPayload
from app.services.keycloak_admin_service import get_keycloak_admin_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenant", tags=["Tenant Admin"])

_HEX_COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TenantProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    display_name: Optional[str] = None
    legal_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


class TenantProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    legal_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


class TenantContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    contact_id: int
    contact_type: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    title: Optional[str] = None


class TenantContactUpsertItem(BaseModel):
    contact_type: str = Field(..., pattern="^(PRIMARY|SECONDARY|BILLING|TECHNICAL)$")
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    title: Optional[str] = None


class TenantBrandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    brand_color: Optional[str] = None


class TenantBrandingUpdateRequest(BaseModel):
    brand_color: Optional[str] = None

    @field_validator("brand_color")
    @classmethod
    def validate_hex_color(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not _HEX_COLOR_RE.match(value):
            raise ValueError(
                "brand_color must be a 6-character hexadecimal string (no leading #)."
            )
        return value.upper()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    keycloak_id: str
    email: str
    first_name: str
    last_name: str
    role: str
    onboarding_completed: bool
    is_active: bool


class UserCreateRequest(BaseModel):
    email: str
    first_name: str
    last_name: str
    role: str = Field(..., pattern="^(AUDITOR|REVIEWER)$")
    temporary_password: Optional[str] = None


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, pattern="^(AUDITOR|REVIEWER|TENANT_ADMIN)$")
    onboarding_completed: Optional[bool] = None
    is_active: Optional[bool] = None


class TenantCarrierItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    carrier_id: int
    carrier_name: str
    carrier_slug: str
    is_active: bool


# ---------------------------------------------------------------------------
# Helper: resolve tenant schema from request state
# ---------------------------------------------------------------------------


def _get_schema(request: Request) -> str:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant context for this request.",
        )
    return tenant.schema_name


# ---------------------------------------------------------------------------
# Organization Profile
# ---------------------------------------------------------------------------


@router.get("/profile", response_model=TenantProfileResponse)
async def get_tenant_profile(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT display_name, legal_name, address_line1, address_line2, "
            "city, state, zip_code, phone, website "
            "FROM tenant_profiles LIMIT 1"
        )
    )
    row = result.fetchone()
    if row is None:
        # Return an empty-but-typed profile so the frontend form renders cleanly
        return {
            "display_name": None, "legal_name": None,
            "address_line1": None, "address_line2": None,
            "city": None, "state": None, "zip_code": None,
            "phone": None, "website": None,
        }
    return {
        "display_name": row[0],
        "legal_name": row[1],
        "address_line1": row[2],
        "address_line2": row[3],
        "city": row[4],
        "state": row[5],
        "zip_code": row[6],
        "phone": row[7],
        "website": row[8],
    }


@router.put("/profile", response_model=TenantProfileResponse)
async def update_tenant_profile(
    request: Request,
    body: TenantProfileUpdateRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    updates: list[str] = []
    params: dict[str, Any] = {}

    field_map = {
        "display_name": body.display_name,
        "legal_name": body.legal_name,
        "address_line1": body.address_line1,
        "address_line2": body.address_line2,
        "city": body.city,
        "state": body.state,
        "zip_code": body.zip_code,
        "phone": body.phone,
        "website": body.website,
    }
    for col, val in field_map.items():
        if val is not None:
            updates.append(f"{col} = :{col}")
            params[col] = val

    if updates:
        await db.execute(
            text(
                "INSERT INTO tenant_profiles (id) VALUES (1) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
        await db.execute(
            text(
                f"UPDATE tenant_profiles SET {', '.join(updates)} WHERE id = 1"
            ),
            params,
        )
        await db.commit()

    return await get_tenant_profile(request, token=token, db=db)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@router.get("/contacts", response_model=list[TenantContactResponse])
async def get_tenant_contacts(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT contact_id, contact_type, first_name, last_name, "
            "email, phone, title FROM tenant_contacts ORDER BY contact_type"
        )
    )
    rows = result.fetchall()
    return [
        {
            "contact_id": r[0],
            "contact_type": r[1],
            "first_name": r[2],
            "last_name": r[3],
            "email": r[4],
            "phone": r[5],
            "title": r[6],
        }
        for r in rows
    ]


@router.put("/contacts", response_model=list[TenantContactResponse])
async def update_tenant_contacts(
    request: Request,
    body: list[TenantContactUpsertItem],
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    for contact in body:
        await db.execute(
            text(
                "INSERT INTO tenant_contacts "
                "(contact_type, first_name, last_name, email, phone, title) "
                "VALUES (:ctype, :first, :last, :email, :phone, :title) "
                "ON CONFLICT (contact_type) DO UPDATE SET "
                "first_name = EXCLUDED.first_name, "
                "last_name = EXCLUDED.last_name, "
                "email = EXCLUDED.email, "
                "phone = EXCLUDED.phone, "
                "title = EXCLUDED.title"
            ),
            {
                "ctype": contact.contact_type,
                "first": contact.first_name,
                "last": contact.last_name,
                "email": contact.email,
                "phone": contact.phone,
                "title": contact.title,
            },
        )
    await db.commit()
    return await get_tenant_contacts(request, token=token, db=db)


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------


@router.get("/branding", response_model=TenantBrandingResponse)
async def get_tenant_branding(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT logo_url, logo_dark_url, favicon_url, brand_color "
            "FROM tenant_branding LIMIT 1"
        )
    )
    row = result.fetchone()
    if row is None:
        return {"logo_url": None, "logo_dark_url": None, "favicon_url": None, "brand_color": None}
    return {
        "logo_url": row[0],
        "logo_dark_url": row[1],
        "favicon_url": row[2],
        "brand_color": row[3],
    }


@router.put("/branding", response_model=TenantBrandingResponse)
async def update_tenant_branding(
    request: Request,
    body: TenantBrandingUpdateRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    await db.execute(
        text(
            "INSERT INTO tenant_branding (id) VALUES (1) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    await db.execute(
        text("UPDATE tenant_branding SET brand_color = :brand_color WHERE id = 1"),
        {"brand_color": body.brand_color},
    )
    await db.commit()
    return await get_tenant_branding(request, token=token, db=db)


@router.post("/branding/logo", status_code=status.HTTP_200_OK)
async def upload_tenant_logo(
    request: Request,
    file: UploadFile,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Uploads a tenant logo to S3 and writes the URL to tenant_branding.

    S3 atomicity rule (V9 S8):
    The database URL field is written ONLY after the S3 upload successfully
    completes. A failed S3 upload leaves the database unchanged.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # Validate content type
    allowed_types = {"image/png", "image/jpeg", "image/svg+xml"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{file.content_type}'. Accepted: PNG, JPEG, SVG.",
        )

    # Validate file size (5MB limit)
    content = await file.read()
    max_bytes = 5 * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Logo file must not exceed 5 MB.",
        )

    settings = get_settings()
    schema_name = _get_schema(request)
    extension = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "png"
    object_key = f"logos/{schema_name}/{uuid.uuid4()}.{extension}"

    # Step 1 — Upload to S3 (atomic write: DB update only on success)
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=object_key,
            Body=content,
            ContentType=file.content_type,
        )
    except botocore.exceptions.ClientError as exc:
        logger.error(
            "branding.logo_upload.s3_failed",
            extra={"schema": schema_name, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Logo upload to storage failed. Database was not updated.",
        ) from exc

    # Construct the public URL
    if settings.S3_ENDPOINT_URL:
        logo_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{object_key}"
    else:
        logo_url = f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{object_key}"

    # Step 2 — Write URL to DB only after confirmed S3 success
    await db.execute(
        text(
            "INSERT INTO tenant_branding (id) VALUES (1) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    await db.execute(
        text("UPDATE tenant_branding SET logo_url = :url WHERE id = 1"),
        {"url": logo_url},
    )
    await db.commit()

    return {"logo_url": logo_url}


# ---------------------------------------------------------------------------
# Users — /me endpoint (REVIEWER+)
# ---------------------------------------------------------------------------


# @router.get("/users/me", response_model=UserResponse)
# async def get_current_user_profile(
#     request: Request,
#     token: TokenPayload = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ) -> dict[str, Any]:
#     """
#     Returns the profile of the currently authenticated user.
#     Queries users WHERE keycloak_id = token.sub.
#     """
#     verify_role(Role.REVIEWER, token)
#     verify_tenant(request, token)

#     result = await db.execute(
#         text(
#             "SELECT user_id, keycloak_id, email, first_name, last_name, "
#             "role, onboarding_completed, is_active "
#             "FROM users WHERE keycloak_id = :kid"
#         ),
#         {"kid": token.sub},
#     )
#     row = result.fetchone()
#     if row is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User profile not found.",
#         )
#     return {
#         "user_id": row[0],
#         "keycloak_id": row[1],
#         "email": row[2],
#         "first_name": row[3],
#         "last_name": row[4],
#         "role": row[5],
#         "onboarding_completed": row[6],
#         "is_active": row[7],
#     }


# FIND:
@router.get("/users/me", response_model=UserResponse)
async def get_current_user_profile(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns the profile of the currently authenticated user.
    Queries users WHERE keycloak_id = token.sub.
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT user_id, keycloak_id, email, first_name, last_name, "
            "role, onboarding_completed, is_active "
            "FROM users WHERE keycloak_id = :kid"
        ),
        {"kid": token.sub},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )
    return {
        "user_id": row[0],
        "keycloak_id": row[1],
        "email": row[2],
        "first_name": row[3],
        "last_name": row[4],
        "role": row[5],
        "onboarding_completed": row[6],
        "is_active": row[7],
    }



@router.patch("/users/me", response_model=UserResponse)
async def patch_current_user_profile(
    request: Request,
    body: UserUpdateRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Updates the currently authenticated user's own profile fields.

    Used by the onboarding wizard Step 5 to mark onboarding_completed = true.
    The caller can only update their own record (keycloak_id = token.sub).
    Role escalation via this endpoint is not permitted.
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    updates: list[str] = []
    params: dict[str, Any] = {"kid": token.sub}

    # Only allow onboarding_completed and is_active — not role (privilege escalation risk)
    if body.onboarding_completed is not None:
        updates.append("onboarding_completed = :onboarding_completed")
        params["onboarding_completed"] = body.onboarding_completed
    if body.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = body.is_active

    if updates:
        await db.execute(
            text(
                f"UPDATE users SET {', '.join(updates)} WHERE keycloak_id = :kid"
            ),
            params,
        )
        await db.commit()

    return await get_current_user_profile(request, token=token, db=db)



# ---------------------------------------------------------------------------
# Users — management (TENANT_ADMIN)
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserResponse])
async def list_tenant_users(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT user_id, keycloak_id, email, first_name, last_name, "
            "role, onboarding_completed, is_active "
            "FROM users ORDER BY last_name, first_name"
        )
    )
    rows = result.fetchall()
    return [
        {
            "user_id": r[0],
            "keycloak_id": r[1],
            "email": r[2],
            "first_name": r[3],
            "last_name": r[4],
            "role": r[5],
            "onboarding_completed": r[6],
            "is_active": r[7],
        }
        for r in rows
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_user(
    request: Request,
    body: UserCreateRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Creates a new AUDITOR or REVIEWER user.

    Flow:
      1. Check email uniqueness in DB.
      2. Check email uniqueness in Keycloak.
      3. Create user in Keycloak (assigns role + tenant_slug attribute).
      4. Insert user row with keycloak_id.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    tenant = request.state.tenant

    # Step 1 — DB uniqueness check
    existing = await db.execute(
        text("SELECT user_id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if existing.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{body.email}' already exists.",
        )

    keycloak = get_keycloak_admin_service()

    # Step 2 — Keycloak uniqueness check
    kc_existing = await keycloak.get_user_by_email(body.email)
    if kc_existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{body.email}' is already registered in the identity provider.",
        )

    # Step 3 — Create in Keycloak
    role_enum = Role(body.role)
    keycloak_id = await keycloak.create_tenant_user(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        tenant_slug=tenant.slug,
        role=role_enum,
        temporary_password=body.temporary_password,
    )

    # Step 4 — Insert into DB
    result = await db.execute(
        text(
            "INSERT INTO users "
            "(keycloak_id, email, first_name, last_name, role, onboarding_completed, is_active) "
            "VALUES (:kid, :email, :first, :last, :role, FALSE, TRUE) "
            "RETURNING user_id, keycloak_id, email, first_name, last_name, "
            "role, onboarding_completed, is_active"
        ),
        {
            "kid": keycloak_id,
            "email": body.email,
            "first": body.first_name,
            "last": body.last_name,
            "role": body.role,
        },
    )
    await db.commit()
    row = result.fetchone()
    return {
        "user_id": row[0],
        "keycloak_id": row[1],
        "email": row[2],
        "first_name": row[3],
        "last_name": row[4],
        "role": row[5],
        "onboarding_completed": row[6],
        "is_active": row[7],
    }


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_tenant_user(
    request: Request,
    user_id: int,
    body: UserUpdateRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    updates: list[str] = []
    params: dict[str, Any] = {"user_id": user_id}

    if body.role is not None:
        updates.append("role = :role")
        params["role"] = body.role
    if body.onboarding_completed is not None:
        updates.append("onboarding_completed = :onboarding_completed")
        params["onboarding_completed"] = body.onboarding_completed
    if body.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = body.is_active

    if updates:
        await db.execute(
            text(
                f"UPDATE users SET {', '.join(updates)} WHERE user_id = :user_id"
            ),
            params,
        )
        await db.commit()

    result = await db.execute(
        text(
            "SELECT user_id, keycloak_id, email, first_name, last_name, "
            "role, onboarding_completed, is_active "
            "FROM users WHERE user_id = :user_id"
        ),
        {"user_id": user_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return {
        "user_id": row[0],
        "keycloak_id": row[1],
        "email": row[2],
        "first_name": row[3],
        "last_name": row[4],
        "role": row[5],
        "onboarding_completed": row[6],
        "is_active": row[7],
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT,response_model=None)
async def delete_tenant_user(
    request: Request,
    user_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deactivates a user: marks is_active=False in DB and disables in Keycloak.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # Get the user's keycloak_id first
    result = await db.execute(
        text("SELECT keycloak_id FROM users WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    keycloak_id = row[0]

    # Deactivate in Keycloak
    keycloak = get_keycloak_admin_service()
    await keycloak.deactivate_user(keycloak_id)

    # Deactivate in DB
    await db.execute(
        text("UPDATE users SET is_active = FALSE WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Tenant carriers (read — needed by TenantCarrierContext)
# ---------------------------------------------------------------------------


@router.get("/carriers", response_model=list[TenantCarrierItem])
async def get_tenant_carriers(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Returns the carriers linked to the current tenant."""
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT tc.carrier_id, c.name, c.slug, tc.is_active "
            "FROM tenant_carriers tc "
            "JOIN public.carriers c ON c.carrier_id = tc.carrier_id "
            "ORDER BY c.name"
        )
    )
    rows = result.fetchall()
    return [
        {
            "carrier_id": r[0],
            "carrier_name": r[1],
            "carrier_slug": r[2],
            "is_active": r[3],
        }
        for r in rows
    ]
