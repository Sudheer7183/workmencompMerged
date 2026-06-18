"""Fix v_dashboard_summary view — schema-aware (no tenant iteration on public pass)

Revision ID: 0010_dashboard_fix_view
Revises: 0009_report_jobs_run
"""
from __future__ import annotations
from alembic import op, context
import sqlalchemy as sa

revision = "0010_dashboard_fix_view"
down_revision = "0009_report_jobs_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    conn = op.get_bind()

    if schema == "public":
        # Public pass: only create the compat alias view.
        # Do NOT touch tenant schemas here — tenant_demo is seeded into
        # public.tenants by 0001 but its PostgreSQL schema does not exist yet.
        conn.execute(sa.text("""
            CREATE OR REPLACE VIEW public.tenant_registry AS
            SELECT slug, schema_name, name AS tenant_name,
                   tenant_type, status, config, created_at, deleted_at
            FROM public.tenants
        """))
    else:
        # Tenant pass: create the dashboard view for this specific schema.
        # Runs when ALEMBIC_TARGET_SCHEMA is set (provisioning) — schema exists.
        conn.execute(sa.text(f"""
            CREATE OR REPLACE VIEW "{schema}".v_dashboard_summary AS
            SELECT
                p.carrier_id,
                COUNT(DISTINCT p.policy_id) AS total_policies,
                COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Active') AS active_policies,
                COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Cancelled') AS cancelled_policies,
                COALESCE(SUM(p.premium_written), 0) AS total_book_premium,
                COALESCE(SUM(pv.est_premium_end), 0) AS total_est_earned_premium,
                COALESCE(SUM(pv.actual_premium), 0) AS total_actual_earned_premium,
                COALESCE(SUM(pv.variance_amount), 0) AS total_variance_amount,
                COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'High') AS risk_high_count,
                COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Medium') AS risk_medium_count,
                COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Low') AS risk_low_count
            FROM "{schema}".policies p
            LEFT JOIN "{schema}".premium_variance pv
                ON pv.pv_id = (
                    SELECT MAX(pv2.pv_id)
                    FROM "{schema}".premium_variance pv2
                    WHERE pv2.policy_id = p.policy_id
                )
            WHERE p.deleted_at IS NULL
            GROUP BY p.carrier_id
        """))


def downgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    conn = op.get_bind()
    if schema == "public":
        conn.execute(sa.text("DROP VIEW IF EXISTS public.tenant_registry"))
    else:
        conn.execute(sa.text(f'DROP VIEW IF EXISTS "{schema}".v_dashboard_summary'))