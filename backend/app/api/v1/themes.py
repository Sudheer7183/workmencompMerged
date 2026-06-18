"""
Themes API — Phase 6.

Full theme management system per V9 S24 and Theme Addendum S12.

Endpoints:

  Theme resolution (REVIEWER+):
    GET  /api/v1/theme/resolved?carrier_id={id}

  Custom themes CRUD (TENANT_ADMIN):
    GET    /api/v1/admin/themes?carrier_id={id}
    POST   /api/v1/admin/themes
    PUT    /api/v1/admin/themes/{theme_id}
    DELETE /api/v1/admin/themes/{theme_id}
    GET    /api/v1/admin/themes/{theme_id}/export
    POST   /api/v1/admin/themes/import

  Carrier theme config (TENANT_ADMIN):
    GET    /api/v1/admin/carrier-theme-config/{carrier_id}
    PUT    /api/v1/admin/carrier-theme-config/{carrier_id}

  User theme preference (REVIEWER+):
    GET    /api/v1/user/theme-preference
    PUT    /api/v1/user/theme-preference
    DELETE /api/v1/user/theme-preference

Theme resolution chain (V9 S24.1, Addendum S2):
  1. user_theme_prefs  (if allow_user_override = TRUE)
  2. carrier_theme_config.default_theme_id / theme_source
  3. Default Dark  (public.theme_definitions theme_id = 1)
  After resolving: overlay tenant_branding.brand_color onto --brand if set.

Redis cache:
  Key: {schema_name}:theme:{carrier_id}:{user_keycloak_id}  TTL 300s
  Invalidated on: PUT carrier-theme-config, PUT/DELETE user-theme-preference,
                  PUT/DELETE custom theme.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.core.redis import get_redis_dep
from app.schemas.auth import Role, TokenPayload
from redis.asyncio import Redis

router = APIRouter(tags=["Themes"])

_THEME_CACHE_TTL = 300  # seconds — matches useTheme staleTime on the frontend

# All 13 CSS token column names in DB (without dashes).
_TOKEN_FIELDS: list[str] = [
    "bg", "surface", "surface2", "border_col",
    "text_primary", "text_muted",
    "brand", "brand_dark", "accent",
    "color_green", "color_amber", "color_red", "color_blue",
]

# Valid hex colour: exactly 6 hex chars (no leading #).
_HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _theme_cache_key(schema_name: str, carrier_id: int, user_keycloak_id: str) -> str:
    return f"{schema_name}:theme:{carrier_id}:{user_keycloak_id}"


def _theme_carrier_pattern(schema_name: str, carrier_id: int) -> str:
    """Pattern for invalidating all user-scoped keys for one carrier."""
    return f"{schema_name}:theme:{carrier_id}:*"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ThemeTokens(BaseModel):
    """The 13 CSS token values for a theme."""

    bg: str
    surface: str
    surface2: str
    border_col: str
    text_primary: str
    text_muted: str
    brand: str
    brand_dark: str
    accent: str
    color_green: str
    color_amber: str
    color_red: str
    color_blue: str

    @field_validator(
        "bg", "surface", "surface2", "border_col",
        "text_primary", "text_muted", "brand", "brand_dark", "accent",
        "color_green", "color_amber", "color_red", "color_blue",
        mode="before",
    )
    @classmethod
    def must_be_valid_hex(cls, value: str) -> str:
        if not _HEX_RE.match(str(value)):
            raise ValueError(f"Token value must be a 6-character hex colour without '#'. Got: {value!r}")
        return str(value).lower()


class ResolvedThemeResponse(ThemeTokens):
    """
    Resolved theme returned by GET /api/v1/theme/resolved.
    All 13 tokens with brand_color overlay already applied.
    """

    theme_id: int
    theme_name: str
    mode: str
    source: str  # 'USER', 'CARRIER', or 'SYSTEM_DEFAULT'


class ThemeResponse(ThemeTokens):
    """Full theme row — returned from CRUD endpoints."""

    model_config = ConfigDict(from_attributes=True)

    theme_id: int
    theme_name: str
    mode: str
    is_system: bool
    based_on_name: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ThemeCreateRequest(ThemeTokens):
    """Body for POST /api/v1/admin/themes."""

    theme_name: str
    mode: str
    based_on_name: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def must_be_valid_mode(cls, value: str) -> str:
        if value not in ("dark", "light"):
            raise ValueError("mode must be 'dark' or 'light'.")
        return value


class ThemeUpdateRequest(ThemeTokens):
    """Body for PUT /api/v1/admin/themes/{theme_id}."""

    theme_name: str


class CarrierThemeConfigResponse(BaseModel):
    """Carrier theme config row."""

    model_config = ConfigDict(from_attributes=True)

    carrier_id: int
    theme_source: str
    default_theme_id: int
    allow_user_override: bool


class CarrierThemeConfigUpdateRequest(BaseModel):
    default_theme_id: int
    theme_source: str
    allow_user_override: bool

    @field_validator("theme_source")
    @classmethod
    def must_be_valid_source(cls, value: str) -> str:
        if value not in ("SYSTEM", "CUSTOM"):
            raise ValueError("theme_source must be 'SYSTEM' or 'CUSTOM'.")
        return value


class UserThemePrefResponse(BaseModel):
    """User theme preference row."""

    user_keycloak_id: str
    theme_source: str
    theme_id: int


class UserThemePrefUpdateRequest(BaseModel):
    theme_id: int
    theme_source: str

    @field_validator("theme_source")
    @classmethod
    def must_be_valid_source(cls, value: str) -> str:
        if value not in ("SYSTEM", "CUSTOM"):
            raise ValueError("theme_source must be 'SYSTEM' or 'CUSTOM'.")
        return value


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_theme_by_id(
    theme_id: int,
    theme_source: str,
    db: AsyncSession,
) -> dict[str, Any] | None:
    """
    Resolves a theme row from either public.theme_definitions (SYSTEM)
    or tenant_themes (CUSTOM).
    Returns the raw row dict or None if not found.
    """
    if theme_source == "SYSTEM":
        result = await db.execute(
            text(
                "SELECT theme_id, theme_name, mode, is_system, "
                + ", ".join(_TOKEN_FIELDS)
                + " FROM public.theme_definitions WHERE theme_id = :theme_id"
            ),
            {"theme_id": theme_id},
        )
    else:
        result = await db.execute(
            text(
                "SELECT theme_id, theme_name, mode, is_system, "
                "based_on_name, created_by, created_at, updated_at, "
                + ", ".join(_TOKEN_FIELDS)
                + " FROM tenant_themes WHERE theme_id = :theme_id"
            ),
            {"theme_id": theme_id},
        )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def _get_default_dark_theme(db: AsyncSession) -> dict[str, Any]:
    """Returns the Default Dark system theme (theme_id=1)."""
    result = await db.execute(
        text(
            "SELECT theme_id, theme_name, mode, is_system, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM public.theme_definitions WHERE theme_id = 1"
        )
    )
    row = result.mappings().one()
    return dict(row)


async def _get_brand_color_override(db: AsyncSession) -> Optional[str]:
    """Returns tenant_branding.brand_color (6-char hex) if set, else None."""
    result = await db.execute(
        text("SELECT brand_color FROM tenant_branding LIMIT 1")
    )
    row = result.mappings().one_or_none()
    if row and row["brand_color"] and _HEX_RE.match(row["brand_color"]):
        return row["brand_color"]
    return None


async def _invalidate_carrier_theme_cache(
    redis: Redis,  # type: ignore[type-arg]
    schema_name: str,
    carrier_id: int,
) -> None:
    """Removes all per-user theme cache keys for a carrier."""
    pattern = _theme_carrier_pattern(schema_name, carrier_id)
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


# ---------------------------------------------------------------------------
# Endpoint — Theme resolution (REVIEWER+)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/theme/resolved",
    response_model=ResolvedThemeResponse,
    summary="Get resolved theme for current user and carrier (REVIEWER+)",
)
async def get_resolved_theme(
    request: Request,
    carrier_id: int = Query(..., description="Carrier ID to resolve theme for"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> ResolvedThemeResponse:
    """
    Resolves the theme following the priority chain:
      1. User preference (if carrier allows override)
      2. Carrier default theme
      3. Default Dark (system fallback)

    Then overlays tenant_branding.brand_color onto --brand if configured.
    Result is Redis-cached per (schema_name, carrier_id, user_keycloak_id).
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    tenant = request.state.tenant
    cache_key = _theme_cache_key(tenant.schema_name, carrier_id, token.sub)

    # Cache hit
    cached = await redis.get(cache_key)
    if cached is not None:
        return ResolvedThemeResponse(**json.loads(cached))

    # --- Resolution step 1: check user preference ---
    theme_row: dict[str, Any] | None = None
    source = "SYSTEM_DEFAULT"

    user_pref_result = await db.execute(
        text(
            "SELECT utp.theme_id, utp.theme_source "
            "FROM user_theme_prefs utp "
            "JOIN carrier_theme_config ctc ON ctc.allow_user_override = TRUE "
            "WHERE utp.user_keycloak_id = :uid AND ctc.carrier_id = :carrier_id"
        ),
        {"uid": token.sub, "carrier_id": carrier_id},
    )
    user_pref = user_pref_result.mappings().one_or_none()

    if user_pref:
        theme_row = await _resolve_theme_by_id(
            user_pref["theme_id"], user_pref["theme_source"], db
        )
        if theme_row:
            source = "USER"

    # --- Resolution step 2: carrier default ---
    if theme_row is None:
        carrier_cfg_result = await db.execute(
            text(
                "SELECT default_theme_id, theme_source "
                "FROM carrier_theme_config WHERE carrier_id = :carrier_id"
            ),
            {"carrier_id": carrier_id},
        )
        carrier_cfg = carrier_cfg_result.mappings().one_or_none()
        if carrier_cfg:
            theme_row = await _resolve_theme_by_id(
                carrier_cfg["default_theme_id"], carrier_cfg["theme_source"], db
            )
            if theme_row:
                source = "CARRIER"

    # --- Resolution step 3: Default Dark fallback ---
    if theme_row is None:
        theme_row = await _get_default_dark_theme(db)
        source = "SYSTEM_DEFAULT"

    # Overlay brand_color from tenant_branding if set.
    brand_override = await _get_brand_color_override(db)
    if brand_override:
        theme_row = {**theme_row, "brand": brand_override}

    resolved = ResolvedThemeResponse(
        theme_id=theme_row["theme_id"],
        theme_name=theme_row["theme_name"],
        mode=theme_row["mode"],
        source=source,
        bg=theme_row["bg"],
        surface=theme_row["surface"],
        surface2=theme_row["surface2"],
        border_col=theme_row["border_col"],
        text_primary=theme_row["text_primary"],
        text_muted=theme_row["text_muted"],
        brand=theme_row["brand"],
        brand_dark=theme_row["brand_dark"],
        accent=theme_row["accent"],
        color_green=theme_row["color_green"],
        color_amber=theme_row["color_amber"],
        color_red=theme_row["color_red"],
        color_blue=theme_row["color_blue"],
    )

    await redis.set(cache_key, resolved.model_dump_json(), ex=_THEME_CACHE_TTL)
    return resolved


# ---------------------------------------------------------------------------
# Endpoints — Custom themes CRUD (TENANT_ADMIN)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/admin/themes",
    response_model=list[ThemeResponse],
    summary="List all themes — system + custom (TENANT_ADMIN)",
)
async def list_themes(
    request: Request,
    carrier_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[ThemeResponse]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # System themes from public schema
    sys_result = await db.execute(
        text(
            "SELECT theme_id, theme_name, mode, is_system, "
            "NULL::text as based_on_name, NULL::text as created_by, "
            "NULL::timestamptz as created_at, NULL::timestamptz as updated_at, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM public.theme_definitions ORDER BY theme_id"
        )
    )
    system_themes = [ThemeResponse(**dict(row)) for row in sys_result.mappings().all()]

    # Custom themes from tenant schema
    custom_result = await db.execute(
        text(
            "SELECT theme_id, theme_name, mode, is_system, "
            "based_on_name, created_by, created_at, updated_at, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM tenant_themes ORDER BY theme_id"
        )
    )
    custom_themes = [ThemeResponse(**dict(row)) for row in custom_result.mappings().all()]

    return system_themes + custom_themes


@router.post(
    "/api/v1/admin/themes",
    response_model=ThemeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom theme (TENANT_ADMIN)",
)
async def create_theme(
    body: ThemeCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ThemeResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # Ensure theme_name is unique within this tenant.
    existing = await db.execute(
        text("SELECT 1 FROM tenant_themes WHERE theme_name = :name"),
        {"name": body.theme_name},
    )
    if existing.one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A theme named '{body.theme_name}' already exists for this tenant.",
        )

    now = datetime.now(tz=timezone.utc)
    token_values = {field: getattr(body, field) for field in _TOKEN_FIELDS}

    result = await db.execute(
        text(
            """
            INSERT INTO tenant_themes
              (theme_name, mode, is_system, based_on_name, created_by,
               created_at, updated_at,
               bg, surface, surface2, border_col, text_primary, text_muted,
               brand, brand_dark, accent,
               color_green, color_amber, color_red, color_blue)
            VALUES
              (:theme_name, :mode, FALSE, :based_on_name, :created_by,
               :created_at, :updated_at,
               :bg, :surface, :surface2, :border_col, :text_primary, :text_muted,
               :brand, :brand_dark, :accent,
               :color_green, :color_amber, :color_red, :color_blue)
            RETURNING theme_id
            """
        ),
        {
            "theme_name": body.theme_name,
            "mode": body.mode,
            "based_on_name": body.based_on_name,
            "created_by": token.sub,
            "created_at": now,
            "updated_at": now,
            **token_values,
        },
    )
    theme_id = int(result.scalar_one())
    await db.commit()

    row_result = await db.execute(
        text(
            "SELECT theme_id, theme_name, mode, is_system, based_on_name, "
            "created_by, created_at, updated_at, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM tenant_themes WHERE theme_id = :theme_id"
        ),
        {"theme_id": theme_id},
    )
    return ThemeResponse(**dict(row_result.mappings().one()))


@router.put(
    "/api/v1/admin/themes/{theme_id}",
    response_model=ThemeResponse,
    summary="Update a custom theme (TENANT_ADMIN)",
)
async def update_theme(
    theme_id: int,
    body: ThemeUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> ThemeResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    tenant = request.state.tenant

    # System themes cannot be edited.
    existing = await db.execute(
        text("SELECT is_system FROM tenant_themes WHERE theme_id = :theme_id"),
        {"theme_id": theme_id},
    )
    row = existing.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    if row["is_system"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System themes cannot be edited.")

    token_values = {field: getattr(body, field) for field in _TOKEN_FIELDS}
    now = datetime.now(tz=timezone.utc)

    set_clauses = ", ".join(
        [f"{col} = :{col}" for col in _TOKEN_FIELDS] + ["theme_name = :theme_name", "updated_at = :updated_at"]
    )
    await db.execute(
        text(f"UPDATE tenant_themes SET {set_clauses} WHERE theme_id = :theme_id"),
        {"theme_name": body.theme_name, "updated_at": now, "theme_id": theme_id, **token_values},
    )
    await db.commit()

    # Invalidate all per-user theme cache keys for this tenant (any carrier may reference this theme).
    all_carriers_result = await db.execute(
        text("SELECT carrier_id FROM carrier_theme_config WHERE default_theme_id = :theme_id AND theme_source = 'CUSTOM'"),
        {"theme_id": theme_id},
    )
    for carrier_row in all_carriers_result.mappings().all():
        await _invalidate_carrier_theme_cache(redis, tenant.schema_name, carrier_row["carrier_id"])

    row_result = await db.execute(
        text(
            "SELECT theme_id, theme_name, mode, is_system, based_on_name, "
            "created_by, created_at, updated_at, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM tenant_themes WHERE theme_id = :theme_id"
        ),
        {"theme_id": theme_id},
    )
    return ThemeResponse(**dict(row_result.mappings().one()))


@router.delete(
    "/api/v1/admin/themes/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a custom theme (TENANT_ADMIN)",
)
async def delete_theme(
    theme_id: int,
    request: Request,
    replacement_theme_id: Optional[int] = Query(None, description="Replacement theme ID if theme is in use"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> None:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    tenant = request.state.tenant

    row_result = await db.execute(
        text("SELECT is_system FROM tenant_themes WHERE theme_id = :theme_id"),
        {"theme_id": theme_id},
    )
    row = row_result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    if row["is_system"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System themes cannot be deleted.")

    # Check references in carrier_theme_config and user_theme_prefs.
    carrier_refs_result = await db.execute(
        text(
            "SELECT carrier_id FROM carrier_theme_config "
            "WHERE default_theme_id = :theme_id AND theme_source = 'CUSTOM'"
        ),
        {"theme_id": theme_id},
    )
    carrier_refs = [r["carrier_id"] for r in carrier_refs_result.mappings().all()]

    user_count_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM user_theme_prefs "
            "WHERE theme_id = :theme_id AND theme_source = 'CUSTOM'"
        ),
        {"theme_id": theme_id},
    )
    user_count = int(user_count_result.scalar_one())

    if (carrier_refs or user_count > 0) and replacement_theme_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Theme is in use and cannot be deleted without specifying a replacement_theme_id.",
                "affected_carriers": carrier_refs,
                "affected_user_count": user_count,
            },
        )

    if replacement_theme_id is not None and (carrier_refs or user_count > 0):
        # Update references to the replacement theme before deleting.
        await db.execute(
            text(
                "UPDATE carrier_theme_config "
                "SET default_theme_id = :rep_id "
                "WHERE default_theme_id = :theme_id AND theme_source = 'CUSTOM'"
            ),
            {"rep_id": replacement_theme_id, "theme_id": theme_id},
        )
        await db.execute(
            text(
                "UPDATE user_theme_prefs "
                "SET theme_id = :rep_id "
                "WHERE theme_id = :theme_id AND theme_source = 'CUSTOM'"
            ),
            {"rep_id": replacement_theme_id, "theme_id": theme_id},
        )

    await db.execute(
        text("DELETE FROM tenant_themes WHERE theme_id = :theme_id"),
        {"theme_id": theme_id},
    )
    await db.commit()

    # Invalidate cache for affected carriers.
    for cid in carrier_refs:
        await _invalidate_carrier_theme_cache(redis, tenant.schema_name, cid)


@router.get(
    "/api/v1/admin/themes/{theme_id}/export",
    summary="Export a theme as JSON (TENANT_ADMIN)",
)
async def export_theme(
    theme_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> JSONResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    row_result = await db.execute(
        text(
            "SELECT theme_name, mode, based_on_name, "
            + ", ".join(_TOKEN_FIELDS)
            + " FROM tenant_themes WHERE theme_id = :theme_id"
        ),
        {"theme_id": theme_id},
    )
    row = row_result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")

    export_payload = {
        "name": row["theme_name"],
        "mode": row["mode"],
        "based_on": row["based_on_name"],
        "tokens": {field: row[field] for field in _TOKEN_FIELDS},
    }

    return JSONResponse(
        content=export_payload,
        headers={"Content-Disposition": f'attachment; filename="theme_{theme_id}.json"'},
    )


@router.post(
    "/api/v1/admin/themes/import",
    summary="Preview an imported theme JSON (TENANT_ADMIN)",
)
async def import_theme_preview(
    request: Request,
    file: UploadFile = File(...),
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Validates and previews a theme JSON file per Addendum S9.
    Does NOT save the theme — the caller must POST /api/v1/admin/themes to persist.
    """
    verify_role(Role.TENANT_ADMIN, token)

    try:
        contents = await file.read()
        payload = json.loads(contents.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {exc}",
        ) from exc

    required_keys = {"name", "mode", "tokens"}
    if not required_keys.issubset(payload.keys()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"JSON must contain keys: {sorted(required_keys)}",
        )

    if payload["mode"] not in ("dark", "light"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mode must be 'dark' or 'light'.",
        )

    tokens = payload.get("tokens", {})
    invalid_tokens = [
        f for f in _TOKEN_FIELDS
        if f not in tokens or not _HEX_RE.match(str(tokens.get(f, "")))
    ]
    if invalid_tokens:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing or invalid hex values for tokens: {invalid_tokens}",
        )

    return {
        "theme_name": payload["name"],
        "mode": payload["mode"],
        "based_on_name": payload.get("based_on"),
        "tokens": {f: tokens[f] for f in _TOKEN_FIELDS},
        "preview": True,
    }


# ---------------------------------------------------------------------------
# Endpoints — Carrier theme config (TENANT_ADMIN)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/admin/carrier-theme-config/{carrier_id}",
    response_model=CarrierThemeConfigResponse,
    summary="Get carrier theme config (TENANT_ADMIN)",
)
async def get_carrier_theme_config(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CarrierThemeConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT carrier_id, theme_source, default_theme_id, allow_user_override "
            "FROM carrier_theme_config WHERE carrier_id = :carrier_id"
        ),
        {"carrier_id": carrier_id},
    )
    row = result.mappings().one_or_none()
    if row is None:
        # Return defaults if no config row exists.
        return CarrierThemeConfigResponse(
            carrier_id=carrier_id,
            theme_source="SYSTEM",
            default_theme_id=1,
            allow_user_override=True,
        )
    return CarrierThemeConfigResponse(**dict(row))


@router.put(
    "/api/v1/admin/carrier-theme-config/{carrier_id}",
    response_model=CarrierThemeConfigResponse,
    summary="Update carrier theme config (TENANT_ADMIN)",
)
async def update_carrier_theme_config(
    carrier_id: int,
    body: CarrierThemeConfigUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> CarrierThemeConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)
    tenant = request.state.tenant

    await db.execute(
        text(
            """
            INSERT INTO carrier_theme_config
              (carrier_id, theme_source, default_theme_id, allow_user_override)
            VALUES
              (:carrier_id, :theme_source, :default_theme_id, :allow_user_override)
            ON CONFLICT (carrier_id)
            DO UPDATE SET
              theme_source        = EXCLUDED.theme_source,
              default_theme_id    = EXCLUDED.default_theme_id,
              allow_user_override = EXCLUDED.allow_user_override
            """
        ),
        {
            "carrier_id": carrier_id,
            "theme_source": body.theme_source,
            "default_theme_id": body.default_theme_id,
            "allow_user_override": body.allow_user_override,
        },
    )
    await db.commit()

    # Invalidate all per-user theme cache keys for this carrier.
    await _invalidate_carrier_theme_cache(redis, tenant.schema_name, carrier_id)

    return CarrierThemeConfigResponse(
        carrier_id=carrier_id,
        theme_source=body.theme_source,
        default_theme_id=body.default_theme_id,
        allow_user_override=body.allow_user_override,
    )


# ---------------------------------------------------------------------------
# Endpoints — User theme preference (REVIEWER+)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/user/theme-preference",
    response_model=Optional[UserThemePrefResponse],
    summary="Get current user's theme preference (REVIEWER+)",
)
async def get_user_theme_preference(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> Optional[UserThemePrefResponse]:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT user_keycloak_id, theme_source, theme_id "
            "FROM user_theme_prefs WHERE user_keycloak_id = :uid"
        ),
        {"uid": token.sub},
    )
    row = result.mappings().one_or_none()
    return UserThemePrefResponse(**dict(row)) if row else None


@router.put(
    "/api/v1/user/theme-preference",
    response_model=UserThemePrefResponse,
    summary="Set current user's theme preference (REVIEWER+)",
)
async def set_user_theme_preference(
    body: UserThemePrefUpdateRequest,
    request: Request,
    carrier_id: int = Query(..., description="Carrier context for allow_user_override check"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> UserThemePrefResponse:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
    tenant = request.state.tenant

    # Verify allow_user_override is TRUE for this carrier.
    override_check = await db.execute(
        text(
            "SELECT allow_user_override FROM carrier_theme_config "
            "WHERE carrier_id = :carrier_id"
        ),
        {"carrier_id": carrier_id},
    )
    cfg_row = override_check.mappings().one_or_none()
    if cfg_row and not cfg_row["allow_user_override"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User theme override is disabled for this carrier.",
        )

    await db.execute(
        text(
            """
            INSERT INTO user_theme_prefs (user_keycloak_id, theme_source, theme_id)
            VALUES (:uid, :theme_source, :theme_id)
            ON CONFLICT (user_keycloak_id)
            DO UPDATE SET theme_source = EXCLUDED.theme_source, theme_id = EXCLUDED.theme_id
            """
        ),
        {"uid": token.sub, "theme_source": body.theme_source, "theme_id": body.theme_id},
    )
    await db.commit()

    # Invalidate the user-specific theme cache key.
    cache_key = _theme_cache_key(tenant.schema_name, carrier_id, token.sub)
    await redis.delete(cache_key)

    return UserThemePrefResponse(
        user_keycloak_id=token.sub,
        theme_source=body.theme_source,
        theme_id=body.theme_id,
    )


@router.delete(
    "/api/v1/user/theme-preference",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Remove current user's theme preference (revert to carrier default) (REVIEWER+)",
)
async def delete_user_theme_preference(
    request: Request,
    carrier_id: int = Query(..., description="Carrier context for cache invalidation"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> None:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
    tenant = request.state.tenant

    await db.execute(
        text("DELETE FROM user_theme_prefs WHERE user_keycloak_id = :uid"),
        {"uid": token.sub},
    )
    await db.commit()

    cache_key = _theme_cache_key(tenant.schema_name, carrier_id, token.sub)
    await redis.delete(cache_key)
