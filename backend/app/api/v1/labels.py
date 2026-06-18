"""
Labels API — Phase 6.

Endpoints per V9 S23 and S25:

  GET  /api/v1/labels                             REVIEWER+
       Returns carrier-specific label overrides as a nested dict.
       Redis cached: {schema_name}:labels:{carrier_id}:{screen_key}  TTL 300s (per V9 S23.1).

  GET  /api/v1/admin/ui-labels/{carrier_id}       TENANT_ADMIN
       Returns all label override rows for management UI.

  PUT  /api/v1/admin/ui-labels/{carrier_id}       TENANT_ADMIN
       Bulk upsert label overrides. Invalidates Redis cache.

  DELETE /api/v1/admin/ui-labels/{carrier_id}/{label_id}   TENANT_ADMIN
       Deletes a single label override (reset to default).
       Invalidates Redis cache.

  POST /api/v1/admin/ui-labels/{carrier_id}/export-csv     TENANT_ADMIN
       Returns all label rows as a CSV file download.

  POST /api/v1/admin/ui-labels/{carrier_id}/import-csv     TENANT_ADMIN
       Parses an uploaded CSV and bulk-upserts the label overrides.
       Invalidates Redis cache.

  GET  /api/v1/admin/display-config/{carrier_id}  TENANT_ADMIN
  PUT  /api/v1/admin/display-config/{carrier_id}  TENANT_ADMIN
       Column visibility, ordering and conditional formatting config.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.core.redis import get_redis_dep
from app.schemas.auth import Role, TokenPayload
from redis.asyncio import Redis

router = APIRouter(tags=["Labels & Display Config"])

_LABELS_CACHE_TTL = 300  # seconds — matches useLabels staleTime on the frontend


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _labels_cache_key(schema_name: str, carrier_id: int, screen_key: str) -> str:
    return f"{schema_name}:labels:{carrier_id}:{screen_key}"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LabelOverrideRow(BaseModel):
    """Single label override row returned in management UI."""

    model_config = ConfigDict(from_attributes=True)

    label_id: int
    carrier_id: int
    screen_key: str
    field_key: str
    label_text: str


class LabelUpsertItem(BaseModel):
    """Single label to create or update in a bulk upsert."""

    screen_key: str
    field_key: str
    label_text: str


class LabelUpsertRequest(BaseModel):
    labels: list[LabelUpsertItem]


class DisplayConfigItem(BaseModel):
    """Single display config row — column visibility, ordering, and conditional formatting."""

    model_config = ConfigDict(from_attributes=True)

    config_id: Optional[int] = None
    carrier_id: int
    screen_key: str
    field_key: str
    is_visible: bool
    display_order: Optional[int]
    conditional_format_rule: Optional[dict] = None  # type: ignore[type-arg]


class DisplayConfigUpsertItem(BaseModel):
    screen_key: str
    field_key: str
    is_visible: bool
    display_order: Optional[int] = None
    conditional_format_rule: Optional[dict] = None  # type: ignore[type-arg]


class DisplayConfigUpsertRequest(BaseModel):
    configs: list[DisplayConfigUpsertItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _invalidate_labels_cache(
    redis: Redis,  # type: ignore[type-arg]
    schema_name: str,
    carrier_id: int,
) -> None:
    """
    Removes all per-screen label cache keys for this carrier.
    Pattern: {schema_name}:labels:{carrier_id}:* — one key per screen_key.
    Per V9 S23.1: cache is keyed {schema}:labels:{carrier_id}:{screen_key}.
    """
    pattern = f"{schema_name}:labels:{carrier_id}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


# ---------------------------------------------------------------------------
# Endpoints — Labels (REVIEWER+)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/labels",
    summary="Get label overrides for a carrier and screen (REVIEWER+)",
)
async def get_labels(
    request: Request,
    carrier_id: int = Query(..., description="Carrier ID to fetch label overrides for"),
    screen_key: str = Query(..., description="Screen namespace — e.g. 'dashboard', 'policies'"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    """
    Returns label overrides as a flat dict of field_key → label_text for the
    requested screen_key:
      { "kpi.book_premium": "Total Book Premium", ... }

    Returns {} when no overrides exist for this screen — the frontend falls back
    to DEFAULT_LABELS[screenKey].

    Redis cache key per V9 S23.1:
      {schema_name}:labels:{carrier_id}:{screen_key}  TTL 5 min (300s)
    """
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)

    tenant = request.state.tenant
    cache_key = _labels_cache_key(tenant.schema_name, carrier_id, screen_key)

    # Cache hit
    cached = await redis.get(cache_key)
    if cached is not None:
        result: dict[str, str] = json.loads(cached)
        return result

    # Cache miss — query DB for this screen only
    rows_result = await db.execute(
        text(
            "SELECT field_key, label_text "
            "FROM carrier_ui_labels "
            "WHERE carrier_id = :carrier_id AND screen_key = :screen_key"
        ),
        {"carrier_id": carrier_id, "screen_key": screen_key},
    )
    rows = rows_result.mappings().all()

    flat: dict[str, str] = {row["field_key"]: row["label_text"] for row in rows}

    # Populate cache — one entry per screen
    await redis.set(cache_key, json.dumps(flat), ex=_LABELS_CACHE_TTL)
    return flat


# ---------------------------------------------------------------------------
# Endpoints — Admin Labels (TENANT_ADMIN)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/admin/ui-labels/{carrier_id}",
    response_model=list[LabelOverrideRow],
    summary="List all label overrides for a carrier (TENANT_ADMIN)",
)
async def list_label_overrides(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[LabelOverrideRow]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT label_id, carrier_id, screen_key, field_key, label_text "
            "FROM carrier_ui_labels WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    return [LabelOverrideRow(**dict(row)) for row in result.mappings().all()]


@router.put(
    "/api/v1/admin/ui-labels/{carrier_id}",
    response_model=list[LabelOverrideRow],
    summary="Bulk upsert label overrides for a carrier (TENANT_ADMIN)",
)
async def upsert_label_overrides(
    carrier_id: int,
    body: LabelUpsertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> list[LabelOverrideRow]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    tenant = request.state.tenant

    for item in body.labels:
        await db.execute(
            text(
                """
                INSERT INTO carrier_ui_labels (carrier_id, screen_key, field_key, label_text)
                VALUES (:carrier_id, :screen_key, :field_key, :label_text)
                ON CONFLICT (carrier_id, screen_key, field_key)
                DO UPDATE SET label_text = EXCLUDED.label_text
                """
            ),
            {
                "carrier_id": carrier_id,
                "screen_key": item.screen_key,
                "field_key": item.field_key,
                "label_text": item.label_text,
            },
        )

    await db.commit()
    await _invalidate_labels_cache(redis, tenant.schema_name, carrier_id)

    # Return updated list
    result = await db.execute(
        text(
            "SELECT label_id, carrier_id, screen_key, field_key, label_text "
            "FROM carrier_ui_labels WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    return [LabelOverrideRow(**dict(row)) for row in result.mappings().all()]


@router.delete(
    "/api/v1/admin/ui-labels/{carrier_id}/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a single label override (reset to default) (TENANT_ADMIN)",
)
async def delete_label_override(
    carrier_id: int,
    label_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> None:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    tenant = request.state.tenant

    result = await db.execute(
        text(
            "DELETE FROM carrier_ui_labels "
            "WHERE label_id = :label_id AND carrier_id = :carrier_id"
        ),
        {"label_id": label_id, "carrier_id": carrier_id},
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label override not found.")

    await db.commit()
    await _invalidate_labels_cache(redis, tenant.schema_name, carrier_id)


@router.post(
    "/api/v1/admin/ui-labels/{carrier_id}/export-csv",
    summary="Export all label overrides as CSV (TENANT_ADMIN)",
)
async def export_labels_csv(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> StreamingResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT screen_key, field_key, label_text "
            "FROM carrier_ui_labels WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    rows = result.mappings().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["screen_key", "field_key", "label_text"])
    for row in rows:
        writer.writerow([row["screen_key"], row["field_key"], row["label_text"]])

    output.seek(0)
    filename = f"labels_carrier_{carrier_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/api/v1/admin/ui-labels/{carrier_id}/import-csv",
    response_model=list[LabelOverrideRow],
    summary="Import label overrides from CSV (TENANT_ADMIN)",
)
async def import_labels_csv(
    carrier_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),  # type: ignore[type-arg]
    token: TokenPayload = Depends(get_current_user),
) -> list[LabelOverrideRow]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    tenant = request.state.tenant

    contents = await file.read()
    text_content = contents.decode("utf-8-sig")  # handle BOM from Excel
    reader = csv.DictReader(io.StringIO(text_content))

    required_cols = {"screen_key", "field_key", "label_text"}
    if reader.fieldnames is None or not required_cols.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV must contain columns: {sorted(required_cols)}",
        )

    for row in reader:
        await db.execute(
            text(
                """
                INSERT INTO carrier_ui_labels (carrier_id, screen_key, field_key, label_text)
                VALUES (:carrier_id, :screen_key, :field_key, :label_text)
                ON CONFLICT (carrier_id, screen_key, field_key)
                DO UPDATE SET label_text = EXCLUDED.label_text
                """
            ),
            {
                "carrier_id": carrier_id,
                "screen_key": row["screen_key"].strip(),
                "field_key": row["field_key"].strip(),
                "label_text": row["label_text"].strip(),
            },
        )

    await db.commit()
    await _invalidate_labels_cache(redis, tenant.schema_name, carrier_id)

    result = await db.execute(
        text(
            "SELECT label_id, carrier_id, screen_key, field_key, label_text "
            "FROM carrier_ui_labels WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    return [LabelOverrideRow(**dict(row)) for row in result.mappings().all()]


# ---------------------------------------------------------------------------
# Endpoints — Display Config (TENANT_ADMIN)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/admin/display-config/{carrier_id}",
    response_model=list[DisplayConfigItem],
    summary="Get display config for a carrier (TENANT_ADMIN)",
)
async def get_display_config(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[DisplayConfigItem]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT config_id, carrier_id, screen_key, field_key, is_visible, display_order, conditional_format_rule "
            "FROM carrier_display_config WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, display_order NULLS LAST, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    return [DisplayConfigItem(**dict(row)) for row in result.mappings().all()]


@router.put(
    "/api/v1/admin/display-config/{carrier_id}",
    response_model=list[DisplayConfigItem],
    summary="Bulk upsert display config for a carrier (TENANT_ADMIN)",
)
async def upsert_display_config(
    carrier_id: int,
    body: DisplayConfigUpsertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[DisplayConfigItem]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    for item in body.configs:
        await db.execute(
            text(
                """
                INSERT INTO carrier_display_config
                  (carrier_id, screen_key, field_key, is_visible, display_order, conditional_format_rule)
                VALUES (:carrier_id, :screen_key, :field_key, :is_visible, :display_order, :conditional_format_rule)
                ON CONFLICT (carrier_id, screen_key, field_key)
                DO UPDATE SET
                  is_visible             = EXCLUDED.is_visible,
                  display_order          = EXCLUDED.display_order,
                  conditional_format_rule = EXCLUDED.conditional_format_rule
                """
            ),
            {
                "carrier_id": carrier_id,
                "screen_key": item.screen_key,
                "field_key": item.field_key,
                "is_visible": item.is_visible,
                "display_order": item.display_order,
                "conditional_format_rule": json.dumps(item.conditional_format_rule) if item.conditional_format_rule else None,
            },
        )

    await db.commit()

    result = await db.execute(
        text(
            "SELECT config_id, carrier_id, screen_key, field_key, is_visible, display_order, conditional_format_rule "
            "FROM carrier_display_config WHERE carrier_id = :carrier_id "
            "ORDER BY screen_key, display_order NULLS LAST, field_key"
        ),
        {"carrier_id": carrier_id},
    )
    return [DisplayConfigItem(**dict(row)) for row in result.mappings().all()]
