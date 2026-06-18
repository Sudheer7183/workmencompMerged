"""Add run_id column to report_jobs

Phase 5: The initial schema did not include run_id on report_jobs.
This column is required for exception_report and ingestion_audit_trail
report types, which are scoped to a specific ingestion run.

Revision ID: 0009
Revises: 0008
Create Date: 2026-01-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0009_report_jobs_run"
down_revision: str = "0008_field_map_col_rename2"
branch_labels = None
depends_on = None


def _get_schema_names(conn) -> list[str]:  # type: ignore[no-untyped-def]
    """Return all tenant schema names (excludes public, pg_*, information_schema)."""
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('public', 'information_schema') "
            "AND schema_name NOT LIKE 'pg_%'"
        )
    )
    return [row[0] for row in result]


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    """Returns True if the column already exists — prevents duplicate add_column errors."""
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": schema, "table": table, "col": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    for schema in _get_schema_names(conn):
        # Guard: skip if run_id already exists (idempotent across re-runs and new tenants)
        if not _column_exists(conn, schema, "report_jobs", "run_id"):
            op.add_column(
                "report_jobs",
                sa.Column("run_id", sa.BigInteger(), nullable=True),
                schema=schema,
            )


def downgrade() -> None:
    conn = op.get_bind()
    for schema in _get_schema_names(conn):
        op.drop_column("report_jobs", "run_id", schema=schema)