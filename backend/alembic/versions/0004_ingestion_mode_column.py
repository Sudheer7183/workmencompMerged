"""Add ingestion_mode column to ingestion_runs for App1/App2 routing toggle.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-05

ingestion_mode distinguishes two ingestion pipelines:
  - 'calc_engine'  (Application 2) — raw files are parsed and calculations run
  - 'display_only' (Application 1) — pre-calculated files are stored as-is
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_ingestion_mode_column"
down_revision = "0003_phase3_mapping_gate"
branch_labels = None
depends_on = None


def _get_tenant_schemas(conn) -> list[str]:
    """Returns all tenant schema names (everything except public and system schemas)."""
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('public', 'information_schema') "
            "AND schema_name NOT LIKE 'pg_%'"
        )
    )
    return [row[0] for row in result.fetchall()]


def upgrade() -> None:
    conn = op.get_bind()
    tenant_schemas = _get_tenant_schemas(conn)

    for schema in tenant_schemas:
        # Add ingestion_mode with a CHECK constraint so the value is always valid.
        # Default is 'calc_engine' so all existing runs (from before this migration)
        # are treated as calculation-engine runs, preserving backward compatibility.
        op.execute(
            f"""
            ALTER TABLE "{schema}".ingestion_runs
              ADD COLUMN IF NOT EXISTS ingestion_mode VARCHAR(20)
                NOT NULL DEFAULT 'calc_engine'
                CHECK (ingestion_mode IN ('calc_engine', 'display_only'))
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    tenant_schemas = _get_tenant_schemas(conn)

    for schema in tenant_schemas:
        op.execute(
            f'ALTER TABLE "{schema}".ingestion_runs DROP COLUMN IF EXISTS ingestion_mode'
        )