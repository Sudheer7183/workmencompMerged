"""Phase 2: tenant branding, JWKS cache, multi-tenant audit log columns

Revision ID: 0002_phase2_tenant_branding
Revises: 0001
Create Date: 2026-01-01

Adds Phase 2 columns / tables that were not part of the original 0001 schema:
  - public.tenants           : onboarding_completed, brand_color columns
  - public.carriers          : logo_url, website columns
  - tenant schema            : user_activity_log table
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


# ── revision identifiers ──────────────────────────────────────────────────────
revision:       str = "0002_phase2_tenant_branding"
down_revision:  str = "0001"
branch_labels       = None
depends_on          = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_tenant_schemas() -> list[str]:
    """Return all tenant_* schemas that exist in the current DB."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'tenant_%'"
        )
    )
    return [row[0] for row in result]


def _column_exists(conn: sa.engine.Connection, schema: str, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": schema, "table": table, "col": column},
    )
    return result.scalar() > 0  # type: ignore[operator]


def _table_exists(conn: sa.engine.Connection, schema: str, table: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return result.scalar() > 0  # type: ignore[operator]


# ── upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()

    # ── public.tenants additions ──────────────────────────────────────────────
    if not _column_exists(conn, "public", "tenants", "onboarding_completed"):
        op.add_column(
            "tenants",
            sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="false"),
            schema="public",
        )

    if not _column_exists(conn, "public", "tenants", "brand_color"):
        op.add_column(
            "tenants",
            sa.Column("brand_color", sa.String(7), nullable=True),
            schema="public",
        )

    if not _column_exists(conn, "public", "tenants", "logo_url"):
        op.add_column(
            "tenants",
            sa.Column("logo_url", sa.Text(), nullable=True),
            schema="public",
        )

    if not _column_exists(conn, "public", "tenants", "primary_contact_name"):
        op.add_column(
            "tenants",
            sa.Column("primary_contact_name", sa.String(255), nullable=True),
            schema="public",
        )

    if not _column_exists(conn, "public", "tenants", "primary_contact_email"):
        op.add_column(
            "tenants",
            sa.Column("primary_contact_email", sa.String(255), nullable=True),
            schema="public",
        )

    if not _column_exists(conn, "public", "tenants", "primary_contact_phone"):
        op.add_column(
            "tenants",
            sa.Column("primary_contact_phone", sa.String(50), nullable=True),
            schema="public",
        )

    # ── public.carriers additions ─────────────────────────────────────────────
    if not _column_exists(conn, "public", "carriers", "logo_url"):
        op.add_column(
            "carriers",
            sa.Column("logo_url", sa.Text(), nullable=True),
            schema="public",
        )

    if not _column_exists(conn, "public", "carriers", "website"):
        op.add_column(
            "carriers",
            sa.Column("website", sa.Text(), nullable=True),
            schema="public",
        )

    # ── Per-tenant schema additions ───────────────────────────────────────────
    for schema in _get_tenant_schemas():
        _upgrade_tenant_schema(conn, schema)


def _upgrade_tenant_schema(conn: sa.engine.Connection, schema: str) -> None:
    """Add Phase 2 structures to a single tenant schema."""

    # user_activity_log (new table)
    if not _table_exists(conn, schema, "user_activity_log"):
        op.execute(
            sa.text(f"""
                CREATE TABLE {schema}.user_activity_log (
                    log_id          BIGSERIAL PRIMARY KEY,
                    user_email      VARCHAR(255) NOT NULL,
                    action          VARCHAR(100) NOT NULL,
                    resource_type   VARCHAR(100),
                    resource_id     BIGINT,
                    detail          JSONB,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )
        op.execute(
            sa.text(
                f"CREATE INDEX ix_{schema}_user_activity_log_email "
                f"ON {schema}.user_activity_log (user_email)"
            )
        )

    # tenant_branding table (branding overrides per tenant, replaces direct tenants row)
    if not _table_exists(conn, schema, "tenant_branding"):
        op.execute(
            sa.text(f"""
                CREATE TABLE {schema}.tenant_branding (
                    branding_id     SERIAL PRIMARY KEY,
                    carrier_id      INTEGER NOT NULL,
                    logo_url        TEXT,
                    brand_color     VARCHAR(7),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    conn = op.get_bind()

    for schema in _get_tenant_schemas():
        for tbl in ("user_activity_log", "tenant_branding"):
            if _table_exists(conn, schema, tbl):
                op.execute(sa.text(f"DROP TABLE IF EXISTS {schema}.{tbl} CASCADE"))

    for col in ("onboarding_completed", "brand_color", "logo_url",
                "primary_contact_name", "primary_contact_email", "primary_contact_phone"):
        if _column_exists(conn, "public", "tenants", col):
            op.drop_column("tenants", col, schema="public")

    for col in ("logo_url", "website"):
        if _column_exists(conn, "public", "carriers", col):
            op.drop_column("carriers", col, schema="public")
