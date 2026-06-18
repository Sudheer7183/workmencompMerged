"""
platform.py — SUPER_ADMIN /platform/* endpoints (V9 S12, S25.4)

All routes in this module:
  - Require Role.SUPER_ADMIN (enforced via require_super_admin dependency).
  - Are exempt from TenantMiddleware (no X-Tenant-Slug header needed).
  - Use a public-schema DB session (SET search_path TO public).

Endpoints:
  GET    /platform/tenants
  GET    /platform/tenants/{slug}
  POST   /platform/tenants             → triggers TenantProvisioningService
  PATCH  /platform/tenants/{slug}
  DELETE /platform/tenants/{slug}      → soft delete
  POST   /platform/tenants/{slug}/activate
  GET    /platform/carriers
  POST   /platform/carriers
  PATCH  /platform/carriers/{id}
  POST   /platform/tenant-carriers     → assigns carrier to a tenant schema
  DELETE /platform/tenant-carriers/{id}
  GET    /platform/users               → platform-wide user list (public schema)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_public_db
from app.api.security import require_super_admin
from app.schemas.auth import Role, TokenPayload
from app.services.keycloak_admin_service import get_keycloak_admin_service
from app.services.tenant_provisioning_service import TenantProvisioningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["Platform Admin"])

# ---------------------------------------------------------------------------
# Pydantic schemas for this module
# ---------------------------------------------------------------------------

_RESERVED_SUBDOMAINS: frozenset[str] = frozenset(
    {
        "www", "api", "app", "admin", "platform", "mail", "auth",
        "health", "docs", "redoc", "cdn", "assets", "static",
    }
)

_SLUG_PATTERN = r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$"


class TenantCreateRequest(BaseModel):
    """Request body for POST /platform/tenants."""

    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., pattern=_SLUG_PATTERN)
    tenant_type: str = Field(..., pattern="^(AUDIT_COMPANY|CARRIER|BROKER)$")
    carrier_ids: list[int] = Field(default_factory=list)
    admin_email: str = Field(...)
    admin_first_name: str = Field(...)
    admin_last_name: str = Field(...)
    temporary_password: Optional[str] = None
    send_invitation: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug_not_reserved(cls, value: str) -> str:
        if value.lower() in _RESERVED_SUBDOMAINS:
            raise ValueError(f"Slug '{value}' is reserved and cannot be used.")
        return value.lower()


class TenantListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    tenant_type: str
    status: str
    schema_name: str


class TenantDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    tenant_type: str
    status: str
    schema_name: str
    config: Optional[dict[str, Any]] = None


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|SUSPENDED)$")
    config: Optional[dict[str, Any]] = None


class CarrierCreateRequest(BaseModel):
    carrier_name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?$")
    ai_narrative_enabled: bool = False


class CarrierUpdateRequest(BaseModel):
    carrier_name: Optional[str] = None
    ai_narrative_enabled: Optional[bool] = None


class CarrierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    carrier_id: int
    carrier_name: str
    slug: str
    ai_narrative_enabled: bool


class TenantCarrierAssignRequest(BaseModel):
    tenant_slug: str
    carrier_id: int


class PlatformUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    keycloak_id: str
    email: str
    first_name: str
    last_name: str
    role: str
    tenant_slug: Optional[str] = None
    is_active: bool


# ---------------------------------------------------------------------------
# Tenant endpoints
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=list[TenantListItem])
async def list_tenants(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> list[dict[str, Any]]:
    """Lists all tenants from public.tenants with optional status filtering."""
    offset = (page - 1) * page_size
    query = (
        "SELECT slug, name, tenant_type, status, schema_name "
        "FROM public.tenants WHERE deleted_at IS NULL"
    )
    params: dict[str, Any] = {"limit": page_size, "offset": offset}

    if status_filter:
        if status_filter == "DELETED":
            # Show soft-deleted tenants explicitly when requested
            query = (
                "SELECT slug, name, tenant_type, status, schema_name "
                "FROM public.tenants WHERE deleted_at IS NOT NULL "
                "AND status = 'DELETED'"
            )
        else:
            query = (
                "SELECT slug, name, tenant_type, status, schema_name "
                "FROM public.tenants WHERE deleted_at IS NULL "
                "AND status = :status_filter"
            )
            params["status_filter"] = status_filter
    else:
        # Default: show all non-deleted tenants
        query = (
            "SELECT slug, name, tenant_type, status, schema_name "
            "FROM public.tenants WHERE deleted_at IS NULL"
        )
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    return [
        {
            "slug": r[0],
            "name": r[1],
            "tenant_type": r[2],
            "status": r[3],
            "schema_name": r[4],
        }
        for r in rows
    ]


@router.get("/tenants/{slug}", response_model=TenantDetailResponse)
async def get_tenant(
    slug: str,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Returns full tenant detail for the given slug."""
    result = await db.execute(
        text(
            "SELECT slug, name, tenant_type, status, schema_name, config "
            "FROM public.tenants WHERE slug = :slug AND deleted_at IS NULL"
        ),
        {"slug": slug},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found.",
        )
    return {
        "slug": row[0],
        "name": row[1],
        "tenant_type": row[2],
        "status": row[3],
        "schema_name": row[4],
        "config": row[5],
    }


@router.post("/tenants", response_model=TenantDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreateRequest,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """
    Creates and provisions a new tenant.

    Triggers TenantProvisioningService which:
      1. Inserts a PROVISIONING record.
      2. Creates the PostgreSQL schema.
      3. Runs Alembic migrations.
      4. Seeds defaults (calc config, 22 rules, carrier_theme_config).
      5. Creates the TENANT_ADMIN in Keycloak.
      6. Marks the tenant ACTIVE.
    """
    # Check uniqueness
    existing = await db.execute(
        text("SELECT slug FROM public.tenants WHERE slug = :slug AND deleted_at IS NULL"),
        {"slug": body.slug},
    )
    if existing.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant slug '{body.slug}' is already taken.",
        )

    keycloak = get_keycloak_admin_service()
    provisioning_svc = TenantProvisioningService(keycloak)

    await provisioning_svc.provision_tenant(
        tenant_name=body.name,
        tenant_slug=body.slug,
        tenant_type=body.tenant_type,
        carrier_ids=body.carrier_ids,
        admin_email=body.admin_email,
        admin_first_name=body.admin_first_name,
        admin_last_name=body.admin_last_name,
        temporary_password=body.temporary_password,
        send_invitation=body.send_invitation,
        db=db,
    )

    return await get_tenant(body.slug, _token=_token, db=db)


@router.patch("/tenants/{slug}", response_model=TenantDetailResponse)
async def update_tenant(
    slug: str,
    body: TenantUpdateRequest,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Updates mutable tenant fields (name, status, config)."""
    updates: list[str] = []
    params: dict[str, Any] = {"slug": slug}

    if body.carrier_name is not None:
        updates.append("carrier_name = :carrier_name")
        params["carrier_name"] = body.carrier_name
    if body.status is not None:
        updates.append("status = :status")
        params["status"] = body.status
    if body.config is not None:
        updates.append("config = :config::jsonb")
        params["config"] = str(body.config)

    if not updates:
        return await get_tenant(slug, _token=_token, db=db)

    await db.execute(
        text(
            f"UPDATE public.tenants SET {', '.join(updates)} "
            "WHERE slug = :slug AND deleted_at IS NULL"
        ),
        params,
    )
    await db.commit()
    return await get_tenant(slug, _token=_token, db=db)


@router.delete("/tenants/{slug}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_tenant(
    slug: str,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> None:
    """Soft-deletes a tenant (sets deleted_at, status=DELETED). Schema is preserved."""
    await db.execute(
        text(
            "UPDATE public.tenants SET deleted_at = now(), status = 'DELETED' "
            "WHERE slug = :slug AND deleted_at IS NULL"
        ),
        {"slug": slug},
    )
    await db.commit()


@router.post("/tenants/{slug}/activate", response_model=TenantDetailResponse)
async def activate_tenant(
    slug: str,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Sets tenant status to ACTIVE if currently SUSPENDED or PROVISIONING."""
    await db.execute(
        text(
            "UPDATE public.tenants SET status = 'ACTIVE' "
            "WHERE slug = :slug AND deleted_at IS NULL "
            "AND status IN ('DRAFT', 'SUSPENDED', 'PROVISIONING')"
        ),
        {"slug": slug},
    )
    await db.commit()
    return await get_tenant(slug, _token=_token, db=db)

@router.post("/tenants/{slug}/suspend", response_model=TenantDetailResponse)
async def suspend_tenant(
    slug: str,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Sets tenant status to SUSPENDED if currently ACTIVE."""
    await db.execute(
        text(
            "UPDATE public.tenants SET status = 'SUSPENDED' "
            "WHERE slug = :slug AND deleted_at IS NULL AND status = 'ACTIVE'"
        ),
        {"slug": slug},
    )
    await db.commit()
    return await get_tenant(slug, _token=_token, db=db)

# ---------------------------------------------------------------------------
# Carrier endpoints
# ---------------------------------------------------------------------------


@router.get("/carriers", response_model=list[CarrierResponse])
async def list_carriers(
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> list[dict[str, Any]]:
    """Lists all carriers from public.carriers."""
    result = await db.execute(
        text(
            "SELECT carrier_id, carrier_name, slug, ai_narrative_enabled "
            "FROM public.carriers ORDER BY carrier_name"
        )
    )
    rows = result.fetchall()
    return [
        {
            "carrier_id": r[0],
            "carrier_name": r[1],
            "slug": r[2],
            "ai_narrative_enabled": r[3],
        }
        for r in rows
    ]


@router.post("/carriers", response_model=CarrierResponse, status_code=status.HTTP_201_CREATED)
async def create_carrier(
    body: CarrierCreateRequest,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Creates a new carrier in public.carriers."""
    result = await db.execute(
        text(
            "INSERT INTO public.carriers (carrier_name, slug, ai_narrative_enabled) "
            "VALUES (:carrier_name, :slug, :ai_enabled) "
            "RETURNING carrier_id, carrier_name, slug, ai_narrative_enabled"
        ),
        {"carrier_name": body.carrier_name, "slug": body.slug, "ai_enabled": body.ai_narrative_enabled},
    )
    await db.commit()
    row = result.fetchone()
    return {
        "carrier_id": row[0],
        "carrier_name": row[1],
        "slug": row[2],
        "ai_narrative_enabled": row[3],
    }


@router.patch("/carriers/{carrier_id}", response_model=CarrierResponse)
async def update_carrier(
    carrier_id: int,
    body: CarrierUpdateRequest,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """Updates mutable carrier fields."""
    updates: list[str] = []
    params: dict[str, Any] = {"carrier_id": carrier_id}

    if body.carrier_name is not None:
        updates.append("carrier_name = :carrier_name")
        params["carrier_name"] = body.carrier_name
    if body.ai_narrative_enabled is not None:
        updates.append("ai_narrative_enabled = :ai_enabled")
        params["ai_enabled"] = body.ai_narrative_enabled

    if updates:
        await db.execute(
            text(
                f"UPDATE public.carriers SET {', '.join(updates)} "
                "WHERE carrier_id = :carrier_id"
            ),
            params,
        )
        await db.commit()

    result = await db.execute(
        text(
            "SELECT carrier_id, carrier_name, slug, ai_narrative_enabled "
            "FROM public.carriers WHERE carrier_id = :carrier_id"
        ),
        {"carrier_id": carrier_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier {carrier_id} not found.",
        )
    return {
        "carrier_id": row[0],
        "carrier_name": row[1],
        "slug": row[2],
        "ai_narrative_enabled": row[3],
    }


# ---------------------------------------------------------------------------
# Tenant-Carrier assignment
# ---------------------------------------------------------------------------


@router.post("/tenant-carriers", status_code=status.HTTP_201_CREATED)
async def assign_carrier_to_tenant(
    body: TenantCarrierAssignRequest,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict[str, Any]:
    """
    Assigns a carrier to a tenant by inserting into the tenant's schema
    tenant_carriers table.

    The search_path is switched to the tenant schema for this operation.
    This is the cross-schema write that only SUPER_ADMIN can perform.
    """
    # Resolve the tenant's schema name from public.tenants
    result = await db.execute(
        text(
            "SELECT schema_name FROM public.tenants "
            "WHERE slug = :slug AND deleted_at IS NULL"
        ),
        {"slug": body.tenant_slug},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{body.tenant_slug}' not found.",
        )
    schema_name = row[0]

    # Switch search_path to write into the tenant's schema
    await db.execute(text(f"SET search_path TO {schema_name}, public"))
    await db.execute(
        text(
            "INSERT INTO tenant_carriers (carrier_id, is_active) "
            "VALUES (:cid, TRUE) ON CONFLICT DO NOTHING"
        ),
        {"cid": body.carrier_id},
    )
    await db.execute(text("SET search_path TO public"))
    await db.commit()

    return {"tenant_slug": body.tenant_slug, "carrier_id": body.carrier_id, "assigned": True}


@router.delete("/tenant-carriers/{carrier_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_carrier_from_tenant(
    carrier_id: int,
    tenant_slug: str = Query(...),
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> None:
    """Deactivates a carrier assignment in the tenant's schema."""
    result = await db.execute(
        text(
            "SELECT schema_name FROM public.tenants "
            "WHERE slug = :slug AND deleted_at IS NULL"
        ),
        {"slug": tenant_slug},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found.",
        )
    schema_name = row[0]

    await db.execute(text(f"SET search_path TO {schema_name}, public"))
    await db.execute(
        text(
            "UPDATE tenant_carriers SET is_active = FALSE "
            "WHERE carrier_id = :cid"
        ),
        {"cid": carrier_id},
    )
    await db.execute(text("SET search_path TO public"))
    await db.commit()


# ---------------------------------------------------------------------------
# Platform users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[PlatformUserListItem])
async def list_platform_users(
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> list[dict[str, Any]]:
    """
    Returns all platform users via the Keycloak admin API.
    Falls back to an empty list on Keycloak connectivity failure so the
    dashboard remains functional even when Keycloak is temporarily down.
    """
    keycloak = get_keycloak_admin_service()
    try:
        admin_token = await keycloak.get_admin_token()
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            from app.core.config import get_settings
            s = get_settings()
            resp = await client.get(
                f"{s.KEYCLOAK_URL}/admin/realms/{s.KEYCLOAK_REALM}/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                params={"max": 200},
            )
            resp.raise_for_status()
            users_raw = resp.json()
    except Exception as exc:
        logger.warning(
            "platform.users.keycloak_fetch_failed",
            extra={"error": str(exc)},
        )
        return []

    results: list[dict[str, Any]] = []
    for u in users_raw:
        attrs = u.get("attributes", {})
        tenant_slug_list = attrs.get("tenant_slug", [])
        results.append(
            {
                "keycloak_id": u.get("id", ""),
                "email": u.get("email", ""),
                "first_name": u.get("firstName", ""),
                "last_name": u.get("lastName", ""),
                "role": "UNKNOWN",  # Role comes from realm roles — fetch separately if needed
                "tenant_slug": tenant_slug_list[0] if tenant_slug_list else None,
                "is_active": u.get("enabled", False),
            }
        )
    return results

# ---------------------------------------------------------------------------
# Platform themes (SUPER_ADMIN) — Item 1.4
# ---------------------------------------------------------------------------


class PlatformThemeCreate(BaseModel):
    """Request body for POST /platform/themes."""

    theme_name: str = Field(..., min_length=2, max_length=200)
    base_mode: str = Field("dark", pattern="^(dark|light)$")
    tokens: dict = Field(default_factory=dict)


class PlatformThemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    theme_id: int
    theme_name: str
    is_default: bool
    base_mode: str
    tokens: dict
    created_at: str


@router.get("/themes", response_model=list[PlatformThemeResponse])
async def list_platform_themes(
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> list[dict]:
    """Lists all platform-level themes (public schema)."""
    result = await db.execute(
        text(
            "SELECT theme_id, theme_name, is_default, base_mode, tokens::jsonb, "
            "created_at::text FROM public.platform_themes ORDER BY theme_id"
        )
    )
    rows = result.mappings().all()
    await db.execute(text("SET search_path TO public"))
    return [
        {
            "theme_id": r["theme_id"],
            "theme_name": r["theme_name"],
            "is_default": r.get("is_default", False),
            "base_mode": r.get("base_mode", "dark"),
            "tokens": r.get("tokens") or {},
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.post("/themes", response_model=PlatformThemeResponse, status_code=201)
async def create_platform_theme(
    body: PlatformThemeCreate,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict:
    """Creates a new platform-level theme variant."""
    import json as _json

    result = await db.execute(
        text(
            "INSERT INTO public.platform_themes (theme_name, base_mode, tokens, is_default) "
            "VALUES (:name, :mode, :tokens::jsonb, FALSE) "
            "RETURNING theme_id, theme_name, is_default, base_mode, tokens::jsonb, created_at::text"
        ),
        {
            "name": body.theme_name,
            "mode": body.base_mode,
            "tokens": _json.dumps(body.tokens),
        },
    )
    await db.execute(text("SET search_path TO public"))
    await db.commit()
    row = result.mappings().one()
    return {
        "theme_id": row["theme_id"],
        "theme_name": row["theme_name"],
        "is_default": row["is_default"],
        "base_mode": row.get("base_mode", "dark"),
        "tokens": row.get("tokens") or {},
        "created_at": str(row["created_at"]),
    }


@router.post("/themes/{theme_id}/default", status_code=200)
async def set_platform_default_theme(
    theme_id: int,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict:
    """Designates a theme as the platform default (clears is_default on all others first)."""
    # Verify theme exists
    check = await db.execute(
        text("SELECT theme_id FROM public.platform_themes WHERE theme_id = :id"),
        {"id": theme_id},
    )
    if not check.mappings().first():
        raise HTTPException(status_code=404, detail="Theme not found.")

    await db.execute(
        text("UPDATE public.platform_themes SET is_default = FALSE WHERE is_default = TRUE")
    )
    await db.execute(
        text("UPDATE public.platform_themes SET is_default = TRUE WHERE theme_id = :id"),
        {"id": theme_id},
    )
    await db.execute(text("SET search_path TO public"))
    await db.commit()
    return {"theme_id": theme_id, "is_default": True}


# ---------------------------------------------------------------------------
# PUT /platform/themes/{theme_id} — update token values and/or name
# Phase 7BCD — needed by PlatformThemeEditor token editing UI
# ---------------------------------------------------------------------------


class PlatformThemeUpdate(BaseModel):
    """Request body for PUT /platform/themes/{theme_id}."""

    theme_name: Optional[str] = Field(None, min_length=2, max_length=200)
    tokens: Optional[dict] = None


@router.put("/themes/{theme_id}", response_model=PlatformThemeResponse)
async def update_platform_theme(
    theme_id: int,
    body: PlatformThemeUpdate,
    _token: TokenPayload = Depends(require_super_admin),
    db: AsyncSession = Depends(get_public_db),
) -> dict:
    """Updates a platform theme's name and/or token values."""
    import json as _json

    # Verify exists
    check = await db.execute(
        text(
            "SELECT theme_id, theme_name, is_default, base_mode, tokens::jsonb, created_at::text "
            "FROM public.platform_themes WHERE theme_id = :id"
        ),
        {"id": theme_id},
    )
    row = check.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Theme not found.")

    updates: list[str] = []
    params: dict = {"id": theme_id}

    if body.theme_name is not None:
        updates.append("theme_name = :name")
        params["name"] = body.theme_name

    if body.tokens is not None:
        updates.append("tokens = :tokens::jsonb")
        params["tokens"] = _json.dumps(body.tokens)

    if not updates:
        # Nothing to update — return current state
        return {
            "theme_id": row["theme_id"],
            "theme_name": row["theme_name"],
            "is_default": row.get("is_default", False),
            "base_mode": row.get("base_mode", "dark"),
            "tokens": row.get("tokens") or {},
            "created_at": str(row["created_at"]),
        }

    result = await db.execute(
        text(
            f"UPDATE public.platform_themes SET {', '.join(updates)} "
            "WHERE theme_id = :id "
            "RETURNING theme_id, theme_name, is_default, base_mode, tokens::jsonb, created_at::text"
        ),
        params,
    )
    await db.execute(text("SET search_path TO public"))
    await db.commit()
    updated = result.mappings().one()
    return {
        "theme_id": updated["theme_id"],
        "theme_name": updated["theme_name"],
        "is_default": updated.get("is_default", False),
        "base_mode": updated.get("base_mode", "dark"),
        "tokens": updated.get("tokens") or {},
        "created_at": str(updated["created_at"]),
    }