from __future__ import annotations

"""
Data Sources API — Phase 4 (V9 S15.2 Tab 1).
Field Maps API — Phase 4 (V9 S15.2 Tab 2).

Routes registered at /api/v1/admin/data-sources and /api/v1/admin/field-maps.
All endpoints require TENANT_ADMIN role.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import TokenPayload, get_current_user, verify_role, verify_tenant
from app.schemas.auth import Role

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

async def _verify_carrier_belongs_to_tenant(
    carrier_id: int,
    token: TokenPayload,
    db: AsyncSession,
) -> None:
    """
    Raises 403 if the carrier is not linked to the current tenant.

    The db session is already scoped to the tenant schema via get_db
    (search_path is set by TenantMiddleware), so no schema prefix is needed.
    Querying bare tenant_carriers resolves to the correct tenant schema.
    """
    result = await db.execute(
        text(
            "SELECT 1 FROM tenant_carriers "
            "WHERE carrier_id = :cid AND is_active = TRUE"
        ),
        {"cid": carrier_id},
    )
    if result.fetchone() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Carrier {carrier_id} does not belong to your tenant.",
        )


# ---------------------------------------------------------------------------
# Data Sources — CRUD
# ---------------------------------------------------------------------------

class DataSourceCreateRequest(BaseModel):
    carrier_id: int
    source_name: str
    source_type: str = "xlsx"
    anchor_string: str | None = None
    sheet_name: str | None = None
    delimiter: str | None = None


class DataSourceUpdateRequest(BaseModel):
    source_name: str | None = None
    source_type: str | None = None
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


def _row_to_datasource(r: Any) -> DataSourceResponse:
    return DataSourceResponse(
        source_id=r["source_id"],
        carrier_id=r["carrier_id"],
        source_name=r["source_name"],
        source_type=r["source_type"],
        anchor_string=r["anchor_string"],
        sheet_name=r["sheet_name"],
        delimiter=r["delimiter"],
        is_active=r["is_active"],
        created_at=str(r["created_at"]),
    )


@router.get(
    "/data-sources",
    response_model=list[DataSourceResponse],
    summary="List all active data sources for a carrier (TENANT_ADMIN)",
)
async def list_data_sources(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[DataSourceResponse]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await _verify_carrier_belongs_to_tenant(carrier_id, token, db)

    rows = (await db.execute(
        text("""
            SELECT source_id, carrier_id, source_name, source_type,
                   anchor_string, sheet_name, delimiter, is_active, created_at
            FROM ingestion_sources
            WHERE carrier_id = :cid AND is_active = TRUE
            ORDER BY source_id
        """),
        {"cid": carrier_id},
    )).mappings().all()

    return [_row_to_datasource(r) for r in rows]


@router.post(
    "/data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new data source configuration (TENANT_ADMIN)",
)
async def create_data_source(
    body: DataSourceCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> DataSourceResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await _verify_carrier_belongs_to_tenant(body.carrier_id, token, db)

    if body.source_type not in ("xlsx", "csv", "xml"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_type must be one of: xlsx, csv, xml",
        )

    row = (await db.execute(
        text("""
            INSERT INTO ingestion_sources
              (carrier_id, source_name, source_type, anchor_string, sheet_name, delimiter,
               is_active, created_at)
            VALUES (:cid, :name, :stype, :anchor, :sheet, :delim, TRUE, now())
            RETURNING source_id, carrier_id, source_name, source_type,
                      anchor_string, sheet_name, delimiter, is_active, created_at
        """),
        {
            "cid": body.carrier_id,
            "name": body.source_name,
            "stype": body.source_type,
            "anchor": body.anchor_string,
            "sheet": body.sheet_name,
            "delim": body.delimiter,
        },
    )).mappings().one()
    await db.commit()
    return _row_to_datasource(row)


@router.put(
    "/data-sources/{source_id}",
    response_model=DataSourceResponse,
    summary="Update a data source configuration (TENANT_ADMIN)",
)
async def update_data_source(
    source_id: int,
    body: DataSourceUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> DataSourceResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    existing = (await db.execute(
        text("SELECT carrier_id FROM ingestion_sources WHERE source_id = :sid AND is_active = TRUE"),
        {"sid": source_id},
    )).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
    await _verify_carrier_belongs_to_tenant(existing[0], token, db)

    # Build SET clause only for provided fields.
    updates: list[str] = []
    params: dict[str, Any] = {"sid": source_id}
    if body.source_name is not None:
        updates.append("source_name = :name")
        params["name"] = body.source_name
    if body.source_type is not None:
        if body.source_type not in ("xlsx", "csv", "xml"):
            raise HTTPException(status_code=422, detail="source_type must be xlsx, csv, or xml")
        updates.append("source_type = :stype")
        params["stype"] = body.source_type
    if body.anchor_string is not None:
        updates.append("anchor_string = :anchor")
        params["anchor"] = body.anchor_string
    if body.sheet_name is not None:
        updates.append("sheet_name = :sheet")
        params["sheet"] = body.sheet_name
    if body.delimiter is not None:
        updates.append("delimiter = :delim")
        params["delim"] = body.delimiter

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    row = (await db.execute(
        text(f"""
            UPDATE ingestion_sources
            SET {', '.join(updates)}
            WHERE source_id = :sid
            RETURNING source_id, carrier_id, source_name, source_type,
                      anchor_string, sheet_name, delimiter, is_active, created_at
        """),
        params,
    )).mappings().one()
    await db.commit()
    return _row_to_datasource(row)


@router.delete(
    "/data-sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete a data source (TENANT_ADMIN)",
)
async def delete_data_source(
    source_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> None:
    """Soft delete — sets is_active = FALSE. Does not hard-delete."""
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    existing = (await db.execute(
        text("SELECT carrier_id FROM ingestion_sources WHERE source_id = :sid AND is_active = TRUE"),
        {"sid": source_id},
    )).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
    await _verify_carrier_belongs_to_tenant(existing[0], token, db)

    await db.execute(
        text("UPDATE ingestion_sources SET is_active = FALSE WHERE source_id = :sid"),
        {"sid": source_id},
    )
    await db.commit()


@router.post(
    "/data-sources/{source_id}/test",
    summary="Test a data source by uploading a sample file and extracting column names (TENANT_ADMIN)",
)
async def test_data_source(
    source_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Upload a sample file and return detected column names.
    Used to verify the source configuration (anchor_string, sheet_name, delimiter).
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    existing = (await db.execute(
        text("SELECT carrier_id, source_type, anchor_string, sheet_name, delimiter FROM ingestion_sources WHERE source_id = :sid"),
        {"sid": source_id},
    )).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
    await _verify_carrier_belongs_to_tenant(existing[0], token, db)

    source_type = existing[1]
    file_bytes = await file.read()
    columns: list[str] = []

    try:
        if source_type == "xlsx":
            import openpyxl
            from io import BytesIO
            wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
            ws = wb.worksheets[0]
            for row in ws.iter_rows(min_row=1, max_row=20, values_only=True):
                non_empty = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if len(non_empty) >= 2:
                    columns = non_empty
                    break
            wb.close()
        elif source_type == "csv":
            import csv as _csv
            decoded = file_bytes.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="replace")
            sample = decoded[:2048]
            try:
                dialect = _csv.Sniffer().sniff(sample, delimiters=",\t|;")
                delimiter = dialect.delimiter
            except _csv.Error:
                delimiter = existing[4] or ","
            reader = _csv.DictReader(_io_module.StringIO(decoded), delimiter=delimiter)
            columns = list(reader.fieldnames or [])
        elif source_type == "xml":
            import xml.etree.ElementTree as ET
            root = ET.fromstring(file_bytes)
            # Return top-level tag names as "columns".
            columns = [child.tag for child in root.iter() if child.tag not in columns][:20]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}")

    return {
        "source_id": source_id,
        "source_type": source_type,
        "detected_columns": columns,
        "column_count": len(columns),
    }


# ---------------------------------------------------------------------------
# Field Maps — Tab 2 backend
# ---------------------------------------------------------------------------

class FieldMapEntryIn(BaseModel):
    source_field: str
    target_column: str
    canonical_column: str | None = None  # alias for backward compat
    file_type: str | None = None
    transform_fn: str = "as-is"


class FieldMapOut(BaseModel):
    map_id: int
    carrier_id: int
    source_field: str
    target_column: str
    file_type: str | None
    transform_fn: str
    is_active: bool
    created_at: str


class BulkFieldMapRequest(BaseModel):
    mappings: list[FieldMapEntryIn]


def _row_to_fieldmap(r: Any) -> FieldMapOut:
    return FieldMapOut(
        map_id=r["map_id"],
        carrier_id=r["carrier_id"],
        source_field=r["source_field"],
        target_column=r.get("target_column") or r.get("canonical_column", ""),
        file_type=r.get("file_type"),
        transform_fn=r.get("transform_fn") or "as-is",
        is_active=r["is_active"],
        created_at=str(r["created_at"]),
    )


@router.get(
    "/field-maps",
    response_model=list[FieldMapOut],
    summary="List field maps for a carrier (TENANT_ADMIN)",
)
async def list_field_maps(
    carrier_id: int,
    request: Request,
    file_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[FieldMapOut]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await _verify_carrier_belongs_to_tenant(carrier_id, token, db)

    query = "SELECT * FROM ingestion_field_maps WHERE carrier_id = :cid AND is_active = TRUE"
    params: dict[str, Any] = {"cid": carrier_id}
    if file_type:
        query += " AND (file_type = :ft OR file_type IS NULL)"
        params["ft"] = file_type
    query += " ORDER BY map_id"

    rows = (await db.execute(text(query), params)).mappings().all()
    return [_row_to_fieldmap(r) for r in rows]


@router.put(
    "/field-maps/{carrier_id}",
    response_model=list[FieldMapOut],
    summary="Bulk upsert field maps for a carrier (TENANT_ADMIN)",
)
async def bulk_upsert_field_maps(
    carrier_id: int,
    body: BulkFieldMapRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[FieldMapOut]:
    """
    Bulk upsert operation for field maps.
    Uses INSERT ... ON CONFLICT (carrier_id, source_field) DO UPDATE.
    All submitted mappings are marked is_active=TRUE.
    Existing mappings for this carrier that are NOT in the submitted list remain untouched.
    """
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await _verify_carrier_belongs_to_tenant(carrier_id, token, db)

    if not body.mappings:
        raise HTTPException(status_code=422, detail="mappings list must not be empty")

    upserted: list[FieldMapOut] = []
    for entry in body.mappings:
        row = (await db.execute(
            text("""
                INSERT INTO ingestion_field_maps
                  (carrier_id, source_field, target_column, transform_fn, file_type, is_active, created_at)
                VALUES (:cid, :sf, :tc, :tfn, :ft, TRUE, now())
                ON CONFLICT (carrier_id, source_field)
                DO UPDATE SET
                  target_column = EXCLUDED.target_column,
                  transform_fn  = EXCLUDED.transform_fn,
                  file_type     = EXCLUDED.file_type,
                  is_active     = TRUE
                RETURNING *
            """),
            {
                "cid": carrier_id,
                "sf": entry.source_field,
                "tc": entry.target_column or entry.canonical_column or "",
                "tfn": entry.transform_fn,
                "ft": entry.file_type,
            },
        )).mappings().one()
        upserted.append(_row_to_fieldmap(row))

    await db.commit()
    return upserted


@router.delete(
    "/field-maps/{map_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete a field map entry (TENANT_ADMIN)",
)
async def delete_field_map(
    map_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> None:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    existing = (await db.execute(
        text("SELECT carrier_id FROM ingestion_field_maps WHERE map_id = :mid AND is_active = TRUE"),
        {"mid": map_id},
    )).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Field map {map_id} not found")
    await _verify_carrier_belongs_to_tenant(existing[0], token, db)

    await db.execute(
        text("UPDATE ingestion_field_maps SET is_active = FALSE WHERE map_id = :mid"),
        {"mid": map_id},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Missing import needed for test endpoint
# ---------------------------------------------------------------------------
import io as _io_module