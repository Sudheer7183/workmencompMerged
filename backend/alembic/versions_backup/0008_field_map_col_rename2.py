"""Phase 4 — Complete ingestion_field_maps schema for Phase 4.

Renames canonical_column → target_column and adds transform_fn,
file_type, and is_active columns. All operations are idempotent.

The Phase 4 API layer uses target_column throughout but the database column
was originally created as canonical_column in migration 0003. This migration
renames the column in every tenant schema.

Revision ID: 0007_field_map_col_rename
Revises: 0006_phase4_field_maps
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_field_map_col_rename2"
down_revision = "0007_field_map_col_rename"
branch_labels = None
depends_on = None


def _get_tenant_schemas(connection) -> list[str]:
    """Returns all tenant schema names (excludes public, information_schema, pg_*)."""
    result = connection.execute(
        sa.text("""
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog', 'pg_toast')
              AND schema_name NOT LIKE 'pg_%'
        """)
    )
    return [r[0] for r in result]


def _column_exists(connection, schema: str, table: str, column: str) -> bool:
    """Returns True if the column already exists in the given schema.table."""
    result = connection.execute(
        sa.text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name   = :table
              AND column_name  = :column
        """),
        {"schema": schema, "table": table, "column": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    connection = op.get_bind()
    schemas = _get_tenant_schemas(connection)

    for schema in schemas:
        # ── 1. Rename canonical_column → target_column ────────────────────────
        has_canonical = _column_exists(connection, schema, "ingestion_field_maps", "canonical_column")
        has_target    = _column_exists(connection, schema, "ingestion_field_maps", "target_column")

        if has_canonical and not has_target:
            connection.execute(sa.text(
                f'ALTER TABLE "{schema}".ingestion_field_maps '
                f'RENAME COLUMN canonical_column TO target_column'
            ))
        elif not has_canonical and not has_target:
            # Clean schema — add fresh
            op.add_column(
                "ingestion_field_maps",
                sa.Column("target_column", sa.Text(), nullable=False, server_default=""),
                schema=schema,
            )
        # has_target already True → already correct, skip.

        # ── 2. Add transform_fn column ────────────────────────────────────────
        if not _column_exists(connection, schema, "ingestion_field_maps", "transform_fn"):
            op.add_column(
                "ingestion_field_maps",
                sa.Column(
                    "transform_fn",
                    sa.Text(),
                    nullable=False,
                    server_default=sa.text("'as-is'"),
                ),
                schema=schema,
            )

        # ── 3. Add file_type column ───────────────────────────────────────────
        if not _column_exists(connection, schema, "ingestion_field_maps", "file_type"):
            op.add_column(
                "ingestion_field_maps",
                sa.Column("file_type", sa.Text(), nullable=True),
                schema=schema,
            )

        # ── 4. Add is_active column ───────────────────────────────────────────
        if not _column_exists(connection, schema, "ingestion_field_maps", "is_active"):
            op.add_column(
                "ingestion_field_maps",
                sa.Column(
                    "is_active",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("TRUE"),
                ),
                schema=schema,
            )


def downgrade() -> None:
    connection = op.get_bind()
    schemas = _get_tenant_schemas(connection)

    for schema in schemas:
        # Rename target_column back to canonical_column
        has_target    = _column_exists(connection, schema, "ingestion_field_maps", "target_column")
        has_canonical = _column_exists(connection, schema, "ingestion_field_maps", "canonical_column")

        if has_target and not has_canonical:
            connection.execute(sa.text(
                f'ALTER TABLE "{schema}".ingestion_field_maps '
                f'RENAME COLUMN target_column TO canonical_column'
            ))

        # Drop added columns
        if _column_exists(connection, schema, "ingestion_field_maps", "transform_fn"):
            op.drop_column("ingestion_field_maps", "transform_fn", schema=schema)

        if _column_exists(connection, schema, "ingestion_field_maps", "file_type"):
            op.drop_column("ingestion_field_maps", "file_type", schema=schema)

        if _column_exists(connection, schema, "ingestion_field_maps", "is_active"):
            op.drop_column("ingestion_field_maps", "is_active", schema=schema)