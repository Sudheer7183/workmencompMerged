"""Fix v_dashboard_summary view fallback and add tenant_registry compat view

Two production bugs fixed in this migration:

1. Dashboard KPI zeros (Est. Earned Premium, Actual Earned Premium, Total Variance):
   The v_dashboard_summary view joined premium_variance only when an ingestion_run
   with status='complete' existed. In fresh or partially-ingested environments the
   subquery returned NULL, causing a LEFT JOIN miss and $0 KPIs.

   Fix: The run-selection subquery now prefers the latest complete run but falls
   back to the latest run of any status, so KPIs are populated as long as
   premium_variance rows exist.

2. Report generation SQL error — UndefinedTableError: relation "public.tenant_registry":
   report_generation_service.py queried a non-existent table `public.tenant_registry`.
   The actual platform-wide tenant registry is `public.tenants` (column: `name`).

   Fix: A backward-compatibility VIEW `public.tenant_registry` is created that
   aliases `public.tenants` with the column name the service expected (`tenant_name`).
   The service code is also corrected to query `public.tenants` directly (see
   app/services/report_generation_service.py), but this view acts as a safety net
   for any other callers that may still reference the old name.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-10 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0010_dashboard_fix_view"
down_revision = "0009_report_jobs_run"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helper: resolve all tenant schema names
# ---------------------------------------------------------------------------

def _get_tenant_schemas(conn: sa.engine.Connection) -> list[str]:
    """Return every schema that was provisioned as a tenant (prefix: tenant_)."""
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM public.tenants WHERE schema_name IS NOT NULL"
        )
    )
    return [row[0] for row in result]


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    conn = op.get_bind()

    # ── Fix 1: recreate v_dashboard_summary in every tenant schema ─────────
    for schema in _get_tenant_schemas(conn):
        conn.execute(
            sa.text(
                f"""
                CREATE OR REPLACE VIEW "{schema}".v_dashboard_summary AS
                SELECT
                    p.carrier_id,
                    COUNT(DISTINCT p.policy_id)                                          AS total_policies,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Active')  AS active_policies,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Cancelled') AS cancelled_policies,
                    COALESCE(SUM(p.premium_written), 0)                                  AS total_book_premium,
                    COALESCE(SUM(pv.est_premium_end), 0)                                 AS total_est_earned_premium,
                    COALESCE(SUM(pv.actual_premium), 0)                                  AS total_actual_earned_premium,
                    COALESCE(SUM(pv.variance_amount), 0)                                 AS total_variance_amount,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'High')     AS risk_high_count,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Medium')   AS risk_medium_count,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Low')      AS risk_low_count
                FROM "{schema}".policies p
                LEFT JOIN "{schema}".premium_variance pv
                    ON pv.pv_id = (
                        -- Always use the single latest pv row per policy by pv_id.
                        -- This is join-key agnostic: works correctly regardless of how many
                        -- ingestion runs exist, what order files were uploaded, or whether
                        -- est/actual values came from different runs. The ingestion_run_id
                        -- join was the root cause of $0 values when policies and premium_variance
                        -- rows were written in different runs for the same carrier.
                        SELECT MAX(pv2.pv_id)
                        FROM "{schema}".premium_variance pv2
                        WHERE pv2.policy_id = p.policy_id
                    )
                WHERE p.deleted_at IS NULL
                GROUP BY p.carrier_id
                """
            )
        )

    # ── Fix 2: create public.tenant_registry as a compat alias for public.tenants ──
    # The report generation service previously queried public.tenant_registry
    # (table does not exist). The service code now queries public.tenants directly,
    # but this view guards against any residual references.
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW public.tenant_registry AS
            SELECT
                slug,
                schema_name,
                name          AS tenant_name,
                tenant_type,
                status,
                config,
                created_at,
                deleted_at
            FROM public.tenants
            """
        )
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    conn = op.get_bind()

    # Remove compat view
    conn.execute(sa.text("DROP VIEW IF EXISTS public.tenant_registry"))

    # Restore v_dashboard_summary to the original (complete-run-only) form
    for schema in _get_tenant_schemas(conn):
        conn.execute(
            sa.text(
                f"""
                CREATE OR REPLACE VIEW "{schema}".v_dashboard_summary AS
                SELECT
                    p.carrier_id,
                    COUNT(DISTINCT p.policy_id)                                          AS total_policies,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Active')  AS active_policies,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Cancelled') AS cancelled_policies,
                    COALESCE(SUM(p.premium_written), 0)                                  AS total_book_premium,
                    COALESCE(SUM(pv.est_premium_end), 0)                                 AS total_est_earned_premium,
                    COALESCE(SUM(pv.actual_premium), 0)                                  AS total_actual_earned_premium,
                    COALESCE(SUM(pv.variance_amount), 0)                                 AS total_variance_amount,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'High')     AS risk_high_count,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Medium')   AS risk_medium_count,
                    COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Low')      AS risk_low_count
                FROM "{schema}".policies p
                LEFT JOIN "{schema}".premium_variance pv
                    ON pv.policy_id = p.policy_id
                    AND pv.ingestion_run_id = (
                        SELECT MAX(ir2.run_id)
                        FROM "{schema}".ingestion_runs ir2
                        WHERE ir2.carrier_id = p.carrier_id
                        AND ir2.status = 'complete'
                    )
                WHERE p.deleted_at IS NULL
                GROUP BY p.carrier_id
                """
            )
        )