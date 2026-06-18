"""Phase 4 — Add file_type and is_active to ingestion_field_maps.

Revision ID: 0006_phase4_field_maps
Revises: 0005_add_raw_file_bytes
Create Date: 2026-06-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_phase4_field_maps"
down_revision = "0005_add_raw_file_bytes"
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
        # Add file_type column only if it does not already exist.
        # NULL means "applies to all file types".
        if not _column_exists(connection, schema, "ingestion_field_maps", "file_type"):
            op.add_column(
                "ingestion_field_maps",
                sa.Column("file_type", sa.Text(), nullable=True),
                schema=schema,
            )

        # Add is_active column only if it does not already exist.
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
        if _column_exists(connection, schema, "ingestion_field_maps", "is_active"):
            op.drop_column("ingestion_field_maps", "is_active", schema=schema)

        if _column_exists(connection, schema, "ingestion_field_maps", "file_type"):
            op.drop_column("ingestion_field_maps", "file_type", schema=schema)