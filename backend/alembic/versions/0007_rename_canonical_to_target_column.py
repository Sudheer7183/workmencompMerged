"""Phase 4 — Rename canonical_column to target_column in ingestion_field_maps.

The Phase 4 API layer uses target_column throughout but the database column
was originally created as canonical_column in migration 0003. This migration
renames the column in every tenant schema.

Revision ID: 0007_rename_canonical_to_target_column
Revises: 0006_phase4_field_maps
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_field_map_col_rename"
down_revision = "0006_phase4_field_maps"
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
        # Only rename if the old column exists and the new one does not yet exist.
        # This guard makes the migration safe to re-run and safe against partial
        # application across multiple tenant schemas.
        has_old = _column_exists(connection, schema, "ingestion_field_maps", "canonical_column")
        has_new = _column_exists(connection, schema, "ingestion_field_maps", "target_column")

        if has_old and not has_new:
            # ALTER TABLE ... RENAME COLUMN is not supported by op.alter_column —
            # use raw DDL via execute for safety and clarity.
            connection.execute(sa.text(
                f'ALTER TABLE "{schema}".ingestion_field_maps '
                f'RENAME COLUMN canonical_column TO target_column'
            ))
        elif not has_old and not has_new:
            # Neither column exists — add target_column fresh (edge case: clean schema)
            op.add_column(
                "ingestion_field_maps",
                sa.Column("target_column", sa.Text(), nullable=False, server_default=""),
                schema=schema,
            )
        # If has_new is already True, the column is already correct — skip silently.


def downgrade() -> None:
    connection = op.get_bind()
    schemas = _get_tenant_schemas(connection)

    for schema in schemas:
        has_new = _column_exists(connection, schema, "ingestion_field_maps", "target_column")
        has_old = _column_exists(connection, schema, "ingestion_field_maps", "canonical_column")

        if has_new and not has_old:
            connection.execute(sa.text(
                f'ALTER TABLE "{schema}".ingestion_field_maps '
                f'RENAME COLUMN target_column TO canonical_column'
            ))