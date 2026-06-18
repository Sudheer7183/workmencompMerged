"""Add policy_id column to ingestion_runs in all tenant schemas.

This allows run_audit to look up the correct policy for display_only
ingestion runs — where premium_variance and payroll_variance_policy
are never written (no calc engine), making the previous UNION-based
policy lookup always return empty and fall back to the wrong policy.

Revision ID: 0014_ingestion_runs_policy_id
Revises:     0013_add_platform_themes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0014_ingestion_runs_policy_id"
down_revision = "0013_add_platform_themes"
branch_labels = None
depends_on = None


def _get_tenant_schemas(conn) -> list[str]:
    rows = conn.execute(
        text("SELECT schema_name FROM tenants WHERE schema_name IS NOT NULL")
    ).fetchall()
    return [r[0] for r in rows]


def upgrade() -> None:
    conn = op.get_bind()
    schemas = _get_tenant_schemas(conn)
    for schema in schemas:
        # Add nullable policy_id column — NULL for old runs, populated for new ones
        conn.execute(text(
            f"ALTER TABLE \"{schema}\".ingestion_runs "
            f"ADD COLUMN IF NOT EXISTS policy_id BIGINT"
        ))
        # Also add ingestion_mode so display_only runs are identifiable
        conn.execute(text(
            f"ALTER TABLE \"{schema}\".ingestion_runs "
            f"ADD COLUMN IF NOT EXISTS ingestion_mode TEXT "
            f"DEFAULT 'calc_engine'"
        ))
        conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_ingestion_runs_policy_{schema} "
            f"ON \"{schema}\".ingestion_runs (policy_id) WHERE policy_id IS NOT NULL"
        ))


def downgrade() -> None:
    conn = op.get_bind()
    schemas = _get_tenant_schemas(conn)
    for schema in schemas:
        conn.execute(text(
            f"ALTER TABLE \"{schema}\".ingestion_runs "
            f"DROP COLUMN IF EXISTS policy_id, "
            f"DROP COLUMN IF EXISTS ingestion_mode"
        ))