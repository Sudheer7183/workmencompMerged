"""Initial schema — complete V9 database

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

Creates the entire WC Premium Audit Platform schema in a single migration:
  - Public schema: tenants, carriers, theme_definitions, class_codes
  - Tenant schema (tenant_{slug}): all 25+ operational tables, fact tables, views
  - Theme Addendum S2: tenant_themes, theme_source columns
  - Seeds: 4 system themes, demo carrier, demo tenant, 22 calc rules
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _s() -> str:
    """Return the schema currently being migrated."""
    return context.get_context().version_table_schema or "public"


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        _create_public_schema()
        _seed_public_data()
    else:
        _create_tenant_schema(schema)
        _seed_tenant_data(schema)


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        _drop_public_schema()
    else:
        _drop_tenant_schema(schema)


# ============================================================================
# PUBLIC SCHEMA CREATION
# ============================================================================


def _create_public_schema() -> None:
    """Creates all public-schema tables: tenants, carriers, theme_definitions, class_codes."""

    # ── public.tenants ───────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "tenant_type",
            sa.Text(),
            sa.CheckConstraint(
                "tenant_type IN ('AUDIT_COMPANY','CARRIER','BROKER')",
                name="ck_tenants_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('PROVISIONING','ACTIVE','SUSPENDED','DELETED')",
                name="ck_tenants_status",
            ),
            nullable=False,
            server_default="PROVISIONING",
        ),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("slug", name="pk_tenants"),
        schema="public",
    )
    op.create_index("idx_tenants_status", "tenants", ["status"], schema="public")

    # ── public.carriers ──────────────────────────────────────────────────────
    op.create_table(
        "carriers",
        sa.Column(
            "carrier_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("carrier_name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column(
            "ai_narrative_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.PrimaryKeyConstraint("carrier_id", name="pk_carriers"),
        sa.UniqueConstraint("slug", name="uq_carriers_slug"),
        schema="public",
    )

    # ── public.theme_definitions ─────────────────────────────────────────────
    # 13 CSS token columns, each CHAR(6) — stores hex colour without the '#'.
    op.create_table(
        "theme_definitions",
        sa.Column(
            "theme_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("theme_name", sa.Text(), nullable=False),
        sa.Column(
            "mode",
            sa.Text(),
            sa.CheckConstraint("mode IN ('dark','light')", name="ck_theme_def_mode"),
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        # 13 CSS token columns (hex without '#')
        sa.Column("bg", sa.CHAR(6), nullable=False),
        sa.Column("surface", sa.CHAR(6), nullable=False),
        sa.Column("surface2", sa.CHAR(6), nullable=False),
        sa.Column("border_col", sa.CHAR(6), nullable=False),
        sa.Column("text_primary", sa.CHAR(6), nullable=False),
        sa.Column("text_muted", sa.CHAR(6), nullable=False),
        sa.Column("brand", sa.CHAR(6), nullable=False),
        sa.Column("brand_dark", sa.CHAR(6), nullable=False),
        sa.Column("accent", sa.CHAR(6), nullable=False),
        sa.Column("color_green", sa.CHAR(6), nullable=False),
        sa.Column("color_amber", sa.CHAR(6), nullable=False),
        sa.Column("color_red", sa.CHAR(6), nullable=False),
        sa.Column("color_blue", sa.CHAR(6), nullable=False),
        sa.PrimaryKeyConstraint("theme_id", name="pk_theme_definitions"),
        schema="public",
    )

    # ── public.class_codes ───────────────────────────────────────────────────
    op.create_table(
        "class_codes",
        sa.Column(
            "class_code_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hazard_group", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("class_code_id", name="pk_class_codes"),
        sa.UniqueConstraint("code", name="uq_class_codes_code"),
        schema="public",
    )


# ============================================================================
# PUBLIC SCHEMA SEEDS
# ============================================================================
# Theme Addendum S4 — exact hex values for the 4 system themes.
# ============================================================================

_SYSTEM_THEMES = [
    {
        "theme_name": "Default Dark",
        "mode": "dark",
        "is_system": True,
        "bg": "0f1117",
        "surface": "181c27",
        "surface2": "1e2436",
        "border_col": "2a2f45",
        "text_primary": "e8ecf4",
        "text_muted": "7a84a0",
        "brand": "4ade80",
        "brand_dark": "15803d",
        "accent": "818cf8",
        "color_green": "22c55e",
        "color_amber": "f59e0b",
        "color_red": "ef4444",
        "color_blue": "60a5fa",
    },
    {
        "theme_name": "Default Light",
        "mode": "light",
        "is_system": True,
        "bg": "f8fafc",
        "surface": "ffffff",
        "surface2": "f1f5f9",
        "border_col": "e2e8f0",
        "text_primary": "0f172a",
        "text_muted": "64748b",
        "brand": "16a34a",
        "brand_dark": "15803d",
        "accent": "6366f1",
        "color_green": "16a34a",
        "color_amber": "d97706",
        "color_red": "dc2626",
        "color_blue": "2563eb",
    },
    {
        "theme_name": "Corporate Dark",
        "mode": "dark",
        "is_system": True,
        "bg": "0a0e1a",
        "surface": "111827",
        "surface2": "1f2937",
        "border_col": "374151",
        "text_primary": "f9fafb",
        "text_muted": "9ca3af",
        "brand": "3b82f6",
        "brand_dark": "1d4ed8",
        "accent": "a78bfa",
        "color_green": "10b981",
        "color_amber": "f59e0b",
        "color_red": "ef4444",
        "color_blue": "60a5fa",
    },
    {
        "theme_name": "Corporate Light",
        "mode": "light",
        "is_system": True,
        "bg": "ffffff",
        "surface": "f9fafb",
        "surface2": "f3f4f6",
        "border_col": "d1d5db",
        "text_primary": "111827",
        "text_muted": "6b7280",
        "brand": "1d4ed8",
        "brand_dark": "1e3a8a",
        "accent": "7c3aed",
        "color_green": "059669",
        "color_amber": "d97706",
        "color_red": "dc2626",
        "color_blue": "2563eb",
    },
]


def _seed_public_data() -> None:
    """Seeds: 4 system themes, 1 demo carrier, 1 demo tenant."""
    conn = op.get_bind()

    # 4 system themes
    for theme in _SYSTEM_THEMES:
        conn.execute(
            sa.text(
                """
                INSERT INTO public.theme_definitions
                  (theme_name, mode, is_system,
                   bg, surface, surface2, border_col,
                   text_primary, text_muted,
                   brand, brand_dark, accent,
                   color_green, color_amber, color_red, color_blue)
                VALUES
                  (:theme_name, :mode, :is_system,
                   :bg, :surface, :surface2, :border_col,
                   :text_primary, :text_muted,
                   :brand, :brand_dark, :accent,
                   :color_green, :color_amber, :color_red, :color_blue)
                """
            ),
            theme,
        )

    # Demo carrier (carrier_id will be 1 on a fresh DB)
    conn.execute(
        sa.text(
            """
            INSERT INTO public.carriers (name, slug, contact_email, ai_narrative_enabled)
            VALUES ('Demo Carrier', 'demo-carrier', 'admin@demo-carrier.example.com', TRUE)
            """
        )
    )

    # Demo tenant
    conn.execute(
        sa.text(
            """
            INSERT INTO public.tenants (slug, schema_name, name, tenant_type, status)
            VALUES ('demo', 'tenant_demo', 'Demo Tenant', 'AUDIT_COMPANY', 'ACTIVE')
            """
        )
    )


# ============================================================================
# TENANT SCHEMA CREATION — all 25+ operational tables
# ============================================================================


def _create_tenant_schema(schema: str) -> None:
    """Creates all tables in a tenant schema (tenant_{slug})."""

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("keycloak_id", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Text(),
            sa.CheckConstraint(
                "role IN ('TENANT_ADMIN','AUDITOR','REVIEWER')",
                name=f"ck_users_role_{schema}",
            ),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", name=f"pk_users_{schema}"),
        sa.UniqueConstraint("keycloak_id", name=f"uq_users_keycloak_{schema}"),
        sa.UniqueConstraint("email", name=f"uq_users_email_{schema}"),
        schema=schema,
    )

    # ── tenant_profiles ──────────────────────────────────────────────────────
    op.create_table(
        "tenant_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("legal_name", sa.Text(), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("zip_code", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=f"pk_tenant_profiles_{schema}"),
        schema=schema,
    )

    # ── tenant_contacts ──────────────────────────────────────────────────────
    op.create_table(
        "tenant_contacts",
        sa.Column("contact_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "contact_type",
            sa.Text(),
            sa.CheckConstraint(
                "contact_type IN ('PRIMARY','SECONDARY','BILLING','TECHNICAL')",
                name=f"ck_contacts_type_{schema}",
            ),
            nullable=False,
        ),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("contact_id", name=f"pk_tenant_contacts_{schema}"),
        sa.UniqueConstraint("contact_type", name=f"uq_contacts_type_{schema}"),
        schema=schema,
    )

    # ── tenant_branding ──────────────────────────────────────────────────────
    op.create_table(
        "tenant_branding",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("logo_dark_url", sa.Text(), nullable=True),
        sa.Column("favicon_url", sa.Text(), nullable=True),
        sa.Column("brand_color", sa.CHAR(6), nullable=True),
        sa.PrimaryKeyConstraint("id", name=f"pk_tenant_branding_{schema}"),
        schema=schema,
    )

    # ── tenant_carriers ──────────────────────────────────────────────────────
    op.create_table(
        "tenant_carriers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=f"pk_tenant_carriers_{schema}"),
        sa.UniqueConstraint("carrier_id", name=f"uq_tenant_carriers_carrier_{schema}"),
        schema=schema,
    )

    # ── tenant_calc_config ───────────────────────────────────────────────────
    op.create_table(
        "tenant_calc_config",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("use_calculation_engine", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_tenant_calc_config_{schema}"),
        schema=schema,
    )

    # ── carrier_calc_config ──────────────────────────────────────────────────
    op.create_table(
        "carrier_calc_config",
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("use_calculation_engine", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("carrier_id", name=f"pk_carrier_calc_config_{schema}"),
        schema=schema,
    )

    # ── policyholders ────────────────────────────────────────────────────────
    op.create_table(
        "policyholders",
        sa.Column("policyholder_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("fein", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("policyholder_id", name=f"pk_policyholders_{schema}"),
        sa.UniqueConstraint("carrier_id", "fein", name=f"uq_fein_carrier_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_policyholders_carrier_{schema}", "policyholders", ["carrier_id"], schema=schema)

    # ── policies ─────────────────────────────────────────────────────────────
    op.create_table(
        "policies",
        sa.Column("policy_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("policyholder_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_number", sa.Text(), nullable=False),
        sa.Column("state_code", sa.CHAR(2), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("cancellation_date", sa.Date(), nullable=True),
        sa.Column("premium_written", sa.Numeric(16, 2), nullable=True),
        sa.Column(
            "payment_frequency",
            sa.Text(),
            sa.CheckConstraint(
                "payment_frequency IN ('Monthly','Weekly','Bi-Weekly','Semi-Monthly')",
                name=f"ck_policies_freq_{schema}",
            ),
            nullable=True,
        ),
        sa.Column(
            "owner_status",
            sa.Text(),
            sa.CheckConstraint(
                "owner_status IN ('Included','Excluded')",
                name=f"ck_policies_owner_{schema}",
            ),
            nullable=True,
        ),
        sa.Column(
            "policy_status",
            sa.Text(),
            sa.CheckConstraint(
                "policy_status IN ('Active','Cancelled')",
                name=f"ck_policies_status_{schema}",
            ),
            nullable=False,
            server_default="Active",
        ),
        sa.Column(
            "audit_status",
            sa.Text(),
            sa.CheckConstraint(
                "audit_status IN ('Pending','In-Review','Complete')",
                name=f"ck_policies_audit_status_{schema}",
            ),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column("total_est_payroll", sa.Numeric(16, 2), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("policy_id", name=f"pk_policies_{schema}"),
        sa.UniqueConstraint("carrier_id", "policy_number", name=f"uq_policy_num_carrier_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_policies_carrier_{schema}", "policies", ["carrier_id"], schema=schema)
    op.create_index(f"idx_policies_status_{schema}", "policies", ["policy_status"], schema=schema)
    op.create_index(f"idx_policies_risk_{schema}", "policies", ["risk_level"], schema=schema)

    # ── ingestion_sources ────────────────────────────────────────────────────
    op.create_table(
        "ingestion_sources",
        sa.Column("source_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column(
            "source_type",
            sa.Text(),
            sa.CheckConstraint(
                "source_type IN ('xlsx','csv','xml')",
                name=f"ck_ingestion_src_type_{schema}",
            ),
            nullable=False,
            server_default="xlsx",
        ),
        sa.Column("anchor_string", sa.Text(), nullable=True),
        sa.Column("sheet_name", sa.Text(), nullable=True),
        sa.Column("delimiter", sa.CHAR(1), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("source_id", name=f"pk_ingestion_sources_{schema}"),
        schema=schema,
    )

    # ── ingestion_field_maps ─────────────────────────────────────────────────
    # Stores approved field→canonical mappings per carrier for Pass 1 re-use.
    # Phase 3 schema: carrier_id + source_field → canonical_column
    op.create_table(
        "ingestion_field_maps",
        sa.Column("map_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=False),
        sa.Column("canonical_column", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("map_id", name=f"pk_ingestion_field_maps_{schema}"),
        sa.UniqueConstraint("carrier_id", "source_field", name=f"uq_ifm_carrier_source_{schema}"),
        schema=schema,
    )

    # ── field_mapping_sessions ───────────────────────────────────────────────
    # Phase 3 schema: one session per ingestion_run, tracks auto-mapping state.
    # Status transitions: PENDING_REVIEW → APPROVED | REJECTED
    op.create_table(
        "field_mapping_sessions",
        sa.Column("session_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('PENDING_REVIEW','APPROVED','REJECTED')",
                name=f"ck_fms_status_{schema}",
            ),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("auto_mapped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("flagged_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("session_id", name=f"pk_field_mapping_sessions_{schema}"),
        schema=schema,
    )

    # ── field_mapping_proposals ──────────────────────────────────────────────
    # Phase 3 schema: one row per source column per mapping session.
    # proposed_target is nullable — UNMATCHED proposals have no target.
    op.create_table(
        "field_mapping_proposals",
        sa.Column("proposal_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=False),
        sa.Column("source_sample", sa.Text(), nullable=True),
        sa.Column("inferred_type", sa.Text(), nullable=False, server_default="TEXT"),
        sa.Column("proposed_target", sa.Text(), nullable=True),
        sa.Column(
            "confidence",
            sa.Text(),
            sa.CheckConstraint(
                "confidence IN ('HIGH','MEDIUM','LOW','UNMATCHED')",
                name=f"ck_fmp_confidence_{schema}",
            ),
            nullable=False,
            server_default="UNMATCHED",
        ),
        sa.Column("score", sa.Numeric(precision=6, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("transform_fn", sa.Text(), nullable=False, server_default="none"),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("match_reason", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("proposal_id", name=f"pk_field_mapping_proposals_{schema}"),
        schema=schema,
    )

    # ── ingestion_runs ───────────────────────────────────────────────────────
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('awaiting_mapping','mapping_approved','processing',"
                "'complete','partial','failed','rolled_back','cancelled','rolling_back')",
                name=f"ck_ingestion_runs_status_{schema}",
            ),
            nullable=False,
            server_default="awaiting_mapping",
        ),
        sa.Column("rows_ingested", sa.Integer(), nullable=True),
        sa.Column("rows_skipped", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("rows_failed", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("skip_on_error", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        # Per-run engine mode override (NULL = defer to carrier/tenant default)
        sa.Column("use_calculation_engine", sa.Boolean(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("s3_file_key", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", name=f"pk_ingestion_runs_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_ingestion_runs_carrier_{schema}", "ingestion_runs", ["carrier_id"], schema=schema)

    # ── ingestion_errors ─────────────────────────────────────────────────────
    op.create_table(
        "ingestion_errors",
        sa.Column("error_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("error_id", name=f"pk_ingestion_errors_{schema}"),
        schema=schema,
    )

    # ── ingestion_skipped_rows ───────────────────────────────────────────────
    op.create_table(
        "ingestion_skipped_rows",
        sa.Column("skip_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=False),
        sa.Column("error_codes", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "resolution_status",
            sa.Text(),
            sa.CheckConstraint(
                "resolution_status IN ('PENDING','CORRECTED','DISMISSED')",
                name=f"ck_skip_resolution_{schema}",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("corrected_data", postgresql.JSONB(), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("skip_id", name=f"pk_ingestion_skipped_rows_{schema}"),
        schema=schema,
    )

    # ── ingestion_rollbacks ──────────────────────────────────────────────────
    op.create_table(
        "ingestion_rollbacks",
        sa.Column("rollback_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("initiated_by", sa.Text(), nullable=False),
        sa.Column("initiated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('IN_PROGRESS','COMPLETE','FAILED')",
                name=f"ck_rollback_status_{schema}",
            ),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column("rows_removed", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("rollback_id", name=f"pk_ingestion_rollbacks_{schema}"),
        schema=schema,
    )

    # ── carrier_calc_rules ───────────────────────────────────────────────────
    op.create_table(
        "carrier_calc_rules",
        sa.Column("rule_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("rule_label", sa.Text(), nullable=False),
        sa.Column("rule_description", sa.Text(), nullable=True),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "rule_status",
            sa.Text(),
            sa.CheckConstraint(
                "rule_status IN ('DRAFT','PENDING_REVIEW','ACTIVE','DEACTIVATED')",
                name=f"ck_calc_rules_status_{schema}",
            ),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("submitted_by", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("effective_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("rule_id", name=f"pk_carrier_calc_rules_{schema}"),
        sa.UniqueConstraint("carrier_id", "rule_key", "effective_from", name=f"uq_calc_rule_{schema}"),
        schema=schema,
    )

    # ── rule_audit_log ───────────────────────────────────────────────────────
    op.create_table(
        "rule_audit_log",
        sa.Column("log_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("log_id", name=f"pk_rule_audit_log_{schema}"),
        schema=schema,
    )

    # ── carrier_ui_labels ────────────────────────────────────────────────────
    op.create_table(
        "carrier_ui_labels",
        sa.Column("label_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("screen_key", sa.Text(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=False),
        sa.Column("label_text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("label_id", name=f"pk_carrier_ui_labels_{schema}"),
        sa.UniqueConstraint("carrier_id", "screen_key", "field_key", name=f"uq_label_{schema}"),
        schema=schema,
    )

    # ── carrier_display_config ───────────────────────────────────────────────
    op.create_table(
        "carrier_display_config",
        sa.Column("config_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("screen_key", sa.Text(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("conditional_format_rule", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("config_id", name=f"pk_carrier_display_config_{schema}"),
        schema=schema,
    )

    # ── carrier_theme_config — Theme Addendum S2: theme_source column ────────
    op.create_table(
        "carrier_theme_config",
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("default_theme_id", sa.BigInteger(), nullable=True),
        sa.Column("allow_user_override", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        # Theme Addendum S2 — required column; corrects V9 S11 which omitted it
        sa.Column(
            "theme_source",
            sa.Text(),
            sa.CheckConstraint(
                "theme_source IN ('SYSTEM','CUSTOM')",
                name=f"ck_carrier_theme_source_{schema}",
            ),
            nullable=False,
            server_default="SYSTEM",
        ),
        sa.PrimaryKeyConstraint("carrier_id", name=f"pk_carrier_theme_config_{schema}"),
        schema=schema,
    )

    # ── user_theme_prefs — Theme Addendum S2: theme_source column ────────────
    op.create_table(
        "user_theme_prefs",
        sa.Column("user_keycloak_id", sa.Text(), nullable=False),
        sa.Column("theme_id", sa.BigInteger(), nullable=True),
        # Theme Addendum S2 — required column
        sa.Column(
            "theme_source",
            sa.Text(),
            sa.CheckConstraint(
                "theme_source IN ('SYSTEM','CUSTOM')",
                name=f"ck_user_theme_source_{schema}",
            ),
            nullable=False,
            server_default="SYSTEM",
        ),
        sa.PrimaryKeyConstraint("user_keycloak_id", name=f"pk_user_theme_prefs_{schema}"),
        schema=schema,
    )

    # ── carrier_report_templates ──────────────────────────────────────────────
    op.create_table(
        "carrier_report_templates",
        sa.Column("template_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("primary_colour", sa.CHAR(6), nullable=True),
        sa.Column("secondary_colour", sa.CHAR(6), nullable=True),
        sa.Column("contact_block", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("template_id", name=f"pk_carrier_report_templates_{schema}"),
        sa.UniqueConstraint("carrier_id", name=f"uq_report_template_carrier_{schema}"),
        schema=schema,
    )

    # ── report_jobs ───────────────────────────────────────────────────────────
    op.create_table(
        "report_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=True),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("output_format", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('QUEUED','PROCESSING','COMPLETE','FAILED')",
                name=f"ck_report_jobs_status_{schema}",
            ),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("job_id", name=f"pk_report_jobs_{schema}"),
        schema=schema,
    )

    # ── premium_variance (fact table with GENERATED columns) ─────────────────
    op.create_table(
        "premium_variance",
        sa.Column("pv_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("est_premium_end", sa.Numeric(16, 2), nullable=False),
        sa.Column("actual_premium", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "variance_amount",
            sa.Numeric(16, 2),
            sa.Computed("actual_premium - est_premium_end", persisted=True),
            nullable=False,
        ),
        # Engine-derived — NULL when calc engine is off
        sa.Column("variance_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pv_id", name=f"pk_premium_variance_{schema}"),
        sa.UniqueConstraint("policy_id", "ingestion_run_id", name=f"uq_pv_policy_run_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_pv_policy_run_{schema}", "premium_variance", ["policy_id", "ingestion_run_id"], schema=schema)
    op.create_index(f"idx_pv_carrier_{schema}", "premium_variance", ["carrier_id"], schema=schema)

    # ── payroll_variance_policy (fact table with GENERATED columns) ───────────
    op.create_table(
        "payroll_variance_policy",
        sa.Column("pvp_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("est_payroll", sa.Numeric(16, 2), nullable=False),
        sa.Column("actual_payroll_reported", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "reported_over_under",
            sa.Numeric(16, 2),
            sa.Computed("actual_payroll_reported - est_payroll", persisted=True),
            nullable=False,
        ),
        # Engine-derived — NULL when calc engine is off
        sa.Column("reported_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("actual_payroll_classified", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "classified_over_under",
            sa.Numeric(16, 2),
            sa.Computed("actual_payroll_classified - est_payroll", persisted=True),
            nullable=False,
        ),
        # Engine-derived — NULL when calc engine is off
        sa.Column("classified_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pvp_id", name=f"pk_payroll_variance_policy_{schema}"),
        sa.UniqueConstraint("policy_id", "ingestion_run_id", name=f"uq_pvp_policy_run_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_pvp_carrier_{schema}", "payroll_variance_policy", ["carrier_id"], schema=schema)

    # ── payroll_variance_class (finest-grain fact table) ──────────────────────
    op.create_table(
        "payroll_variance_class",
        sa.Column("pvc_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("class_code_id", sa.BigInteger(), nullable=False),
        sa.Column("state_code", sa.CHAR(2), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("est_payroll", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("actual_reported", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "reported_over_under",
            sa.Numeric(16, 2),
            sa.Computed("actual_reported - est_payroll", persisted=True),
            nullable=False,
        ),
        sa.Column("reported_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("actual_classified", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "classified_over_under",
            sa.Numeric(16, 2),
            sa.Computed("actual_classified - est_payroll", persisted=True),
            nullable=False,
        ),
        sa.Column("classified_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pvc_id", name=f"pk_payroll_variance_class_{schema}"),
        sa.UniqueConstraint(
            "policy_id", "state_code", "class_code_id", "ingestion_run_id",
            name=f"uq_pvc_policy_state_code_run_{schema}",
        ),
        schema=schema,
    )
    op.create_index(f"idx_pvc_carrier_{schema}", "payroll_variance_class", ["carrier_id"], schema=schema)

    # ── zero_payroll ──────────────────────────────────────────────────────────
    op.create_table(
        "zero_payroll",
        sa.Column("zp_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("policyholder_name", sa.Text(), nullable=True),
        sa.Column("policy_number", sa.Text(), nullable=True),
        sa.Column("state_code", sa.CHAR(2), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("payroll_frequency", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("zp_id", name=f"pk_zero_payroll_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_zp_policy_date_{schema}", "zero_payroll", ["policy_id", "report_date"], schema=schema)
    op.create_index(f"idx_zp_carrier_{schema}", "zero_payroll", ["carrier_id"], schema=schema)

    # ── missing_payroll ───────────────────────────────────────────────────────
    op.create_table(
        "missing_payroll",
        sa.Column("mp_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("policyholder_name", sa.Text(), nullable=True),
        sa.Column("policy_number", sa.Text(), nullable=True),
        sa.Column("state_code", sa.CHAR(2), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("payroll_frequency", sa.Text(), nullable=True),
        sa.Column("days_since_last_run", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("mp_id", name=f"pk_missing_payroll_{schema}"),
        schema=schema,
    )
    op.create_index(f"idx_mp_carrier_{schema}", "missing_payroll", ["carrier_id"], schema=schema)

    # ── cleanup_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "cleanup_runs",
        sa.Column("cleanup_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("initiated_by", sa.Text(), nullable=False),
        sa.Column("initiated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('IN_PROGRESS','COMPLETE','FAILED')",
                name=f"ck_cleanup_status_{schema}",
            ),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column("policies_archived", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("cleanup_id", name=f"pk_cleanup_runs_{schema}"),
        schema=schema,
    )

    # ── tenant_themes — Theme Addendum S2 (corrects V9 S11) ──────────────────
    op.create_table(
        "tenant_themes",
        sa.Column("theme_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("theme_name", sa.Text(), nullable=False),
        sa.Column(
            "mode",
            sa.Text(),
            sa.CheckConstraint(
                "mode IN ('dark','light')",
                name=f"ck_tenant_themes_mode_{schema}",
            ),
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        # 13 CSS token columns (hex without '#')
        sa.Column("bg", sa.CHAR(6), nullable=False),
        sa.Column("surface", sa.CHAR(6), nullable=False),
        sa.Column("surface2", sa.CHAR(6), nullable=False),
        sa.Column("border_col", sa.CHAR(6), nullable=False),
        sa.Column("text_primary", sa.CHAR(6), nullable=False),
        sa.Column("text_muted", sa.CHAR(6), nullable=False),
        sa.Column("brand", sa.CHAR(6), nullable=False),
        sa.Column("brand_dark", sa.CHAR(6), nullable=False),
        sa.Column("accent", sa.CHAR(6), nullable=False),
        sa.Column("color_green", sa.CHAR(6), nullable=False),
        sa.Column("color_amber", sa.CHAR(6), nullable=False),
        sa.Column("color_red", sa.CHAR(6), nullable=False),
        sa.Column("color_blue", sa.CHAR(6), nullable=False),
        sa.Column("based_on_name", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("theme_id", name=f"pk_tenant_themes_{schema}"),
        schema=schema,
    )

    # ── v_dashboard_summary (VIEW) ────────────────────────────────────────────
    # Uses the GENERATED variance_amount column — always available regardless of engine mode.
    op.execute(
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
            -- variance_amount is a GENERATED column — always non-NULL
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


# ============================================================================
# TENANT SCHEMA SEEDS
# ============================================================================
# 22 calculation rules from V9 S18.3
# ============================================================================

_DEFAULT_CALC_RULES = [
    # ── LOCKED rules — arithmetic guaranteed by GENERATED columns.
    # Stored for reference + history; is_editable = FALSE.
    {
        "rule_key": "variance_amount",
        "rule_label": "Premium Variance Amount",
        "rule_description": "Actual premium minus estimated premium. Always computed (GENERATED column).",
        "expression": "actual_premium - est_premium_end",
        "is_editable": False,
    },
    {
        "rule_key": "reported_over_under",
        "rule_label": "Reported Over / Under",
        "rule_description": "Actual reported payroll minus estimated payroll (GENERATED column).",
        "expression": "actual_payroll_reported - est_payroll",
        "is_editable": False,
    },
    {
        "rule_key": "classified_over_under",
        "rule_label": "Classified Over / Under",
        "rule_description": "Actual classified payroll minus estimated payroll (GENERATED column).",
        "expression": "actual_payroll_classified - est_payroll",
        "is_editable": False,
    },
    # ── EDITABLE rules — evaluated by simpleeval in Phase 3
    {
        "rule_key": "variance_pct",
        "rule_label": "Premium Variance %",
        "rule_description": "Variance amount as a percentage of estimated premium. NULL when est = 0.",
        "expression": "variance_amount / est_premium_end if est_premium_end != 0 else None",
        "is_editable": True,
    },
    {
        "rule_key": "reported_pct",
        "rule_label": "Actual Reported % of Estimated",
        "rule_description": "Actual reported payroll as a percentage of estimated payroll. NULL when est = 0.",
        "expression": "actual_payroll_reported / est_payroll if est_payroll != 0 else None",
        "is_editable": True,
    },
    {
        "rule_key": "classified_pct",
        "rule_label": "Actual Classified % of Estimated",
        "rule_description": "Actual classified payroll as a percentage of estimated payroll. NULL when est = 0.",
        "expression": "actual_payroll_classified / est_payroll if est_payroll != 0 else None",
        "is_editable": True,
    },
    {
        "rule_key": "class_reported_pct",
        "rule_label": "Class Reported % of Estimated",
        "rule_description": "Class-code-level actual reported as a percentage of estimated. NULL when est = 0.",
        "expression": "actual_reported / est_payroll if est_payroll != 0 else None",
        "is_editable": True,
    },
    {
        "rule_key": "class_classified_pct",
        "rule_label": "Class Classified % of Estimated",
        "rule_description": "Class-code-level actual classified as a percentage of estimated. NULL when est = 0.",
        "expression": "actual_classified / est_payroll if est_payroll != 0 else None",
        "is_editable": True,
    },
    {
        "rule_key": "completion_ratio",
        "rule_label": "Policy Completion Ratio",
        "rule_description": "Days elapsed as a proportion of total policy term.",
        "expression": "days_elapsed / policy_days",
        "is_editable": True,
    },
    {
        "rule_key": "expected_submissions",
        "rule_label": "Expected Submissions",
        "rule_description": "Expected number of payroll submissions for the policy term.",
        "expression": "policy_days / cycle_days",
        "is_editable": True,
    },
    {
        "rule_key": "submission_rate",
        "rule_label": "Submission Rate %",
        "rule_description": "Actual payroll submissions as a percentage of expected submissions.",
        "expression": "submitted_count / expected_submissions * 100",
        "is_editable": True,
    },
    {
        "rule_key": "risk_threshold_high",
        "rule_label": "High Risk Rule",
        "rule_description": "High risk when variance exceeds 30% AND missing payrolls exist.",
        "expression": "abs(variance_pct) > 30 and missing_payrolls > 0",
        "is_editable": True,
    },
    {
        "rule_key": "risk_threshold_medium",
        "rule_label": "Medium Risk Rule",
        "rule_description": "Medium risk when variance exceeds 30% OR missing payrolls exist.",
        "expression": "abs(variance_pct) > 30 or missing_payrolls > 0",
        "is_editable": True,
    },
    {
        "rule_key": "risk_threshold_target",
        "rule_label": "Target Variance Threshold (Dashboard)",
        "rule_description": "Variance percentage threshold shown on the dashboard target widget.",
        "expression": "30",
        "is_editable": True,
    },
    {
        "rule_key": "officer_max_payroll",
        "rule_label": "Officer Max Inclusion Payroll",
        "rule_description": "Maximum officer payroll included in WC premium calculation.",
        "expression": "52000",
        "is_editable": True,
    },
    {
        "rule_key": "officer_min_payroll",
        "rule_label": "Officer Min Inclusion Payroll",
        "rule_description": "Minimum officer payroll included in WC premium calculation.",
        "expression": "15600",
        "is_editable": True,
    },
    {
        "rule_key": "zero_payroll_flag",
        "rule_label": "Zero Payroll Detection",
        "rule_description": "Flags a payroll submission where reported wages equal zero.",
        "expression": "wages == 0.0",
        "is_editable": True,
    },
    {
        "rule_key": "missing_payroll_flag",
        "rule_label": "Missing Payroll Detection",
        "rule_description": "Flags a gap greater than 1.5 times the expected submission cycle.",
        "expression": "days_since_last_run > cycle_days * 1.5",
        "is_editable": True,
    },
    {
        "rule_key": "freq_cycle_weekly",
        "rule_label": "Weekly Cycle Days",
        "rule_description": "Number of days in a weekly payroll cycle.",
        "expression": "7",
        "is_editable": True,
    },
    {
        "rule_key": "freq_cycle_biweekly",
        "rule_label": "Bi-Weekly Cycle Days",
        "rule_description": "Number of days in a bi-weekly payroll cycle.",
        "expression": "14",
        "is_editable": True,
    },
    {
        "rule_key": "freq_cycle_semimonthly",
        "rule_label": "Semi-Monthly Cycle Days",
        "rule_description": "Number of days in a semi-monthly payroll cycle.",
        "expression": "15",
        "is_editable": True,
    },
    {
        "rule_key": "freq_cycle_monthly",
        "rule_label": "Monthly Cycle Days",
        "rule_description": "Number of days in a monthly payroll cycle.",
        "expression": "30",
        "is_editable": True,
    },
]


def _seed_tenant_data(schema: str) -> None:
    """Seeds the tenant_demo schema with config, carrier link, and 22 calc rules."""
    conn = op.get_bind()

    # Only seed the demo tenant schema
    if schema != "tenant_demo":
        return

    # Resolve demo carrier_id (seeded in public schema)
    result = conn.execute(
        sa.text("SELECT carrier_id FROM public.carriers WHERE slug = 'demo-carrier'")
    )
    row = result.fetchone()
    if row is None:
        raise RuntimeError("Demo carrier not found in public.carriers — public schema must be migrated first.")
    demo_carrier_id: int = row[0]

    # tenant_calc_config — single row, engine ON
    conn.execute(
        sa.text(
            f'INSERT INTO "{schema}".tenant_calc_config (use_calculation_engine) VALUES (TRUE)'
        )
    )

    # tenant_carriers — link demo carrier
    conn.execute(
        sa.text(
            f'INSERT INTO "{schema}".tenant_carriers (carrier_id, is_active) VALUES (:cid, TRUE)'
        ),
        {"cid": demo_carrier_id},
    )

    # carrier_calc_config — engine ON for demo carrier
    conn.execute(
        sa.text(
            f'INSERT INTO "{schema}".carrier_calc_config (carrier_id, use_calculation_engine) VALUES (:cid, TRUE)'
        ),
        {"cid": demo_carrier_id},
    )

    # carrier_theme_config — Default Dark (theme_id = 1), theme_source = SYSTEM
    conn.execute(
        sa.text(
            f"""
            INSERT INTO "{schema}".carrier_theme_config
              (carrier_id, default_theme_id, allow_user_override, theme_source)
            VALUES (:cid, 1, TRUE, 'SYSTEM')
            """
        ),
        {"cid": demo_carrier_id},
    )

    # 22 calculation rules (all ACTIVE)
    for rule in _DEFAULT_CALC_RULES:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO "{schema}".carrier_calc_rules
                  (carrier_id, rule_key, rule_label, rule_description,
                   expression, is_editable, rule_status)
                VALUES
                  (:cid, :rule_key, :rule_label, :rule_description,
                   :expression, :is_editable, 'ACTIVE')
                """
            ),
            {
                "cid": demo_carrier_id,
                "rule_key": rule["rule_key"],
                "rule_label": rule["rule_label"],
                "rule_description": rule["rule_description"],
                "expression": rule["expression"],
                "is_editable": rule["is_editable"],
            },
        )


# ============================================================================
# DOWNGRADE — drop all objects in reverse creation order
# ============================================================================


def _drop_public_schema() -> None:
    op.drop_table("class_codes", schema="public")
    op.drop_table("theme_definitions", schema="public")
    op.drop_table("carriers", schema="public")
    op.drop_table("tenants", schema="public")


def _drop_tenant_schema(schema: str) -> None:
    # Drop view first
    op.execute(f'DROP VIEW IF EXISTS "{schema}".v_dashboard_summary')
    for table in [
        "tenant_themes", "cleanup_runs", "missing_payroll", "zero_payroll",
        "payroll_variance_class", "payroll_variance_policy", "premium_variance",
        "report_jobs", "carrier_report_templates", "user_theme_prefs",
        "carrier_theme_config", "carrier_display_config", "carrier_ui_labels",
        "rule_audit_log", "carrier_calc_rules", "ingestion_rollbacks",
        "ingestion_skipped_rows", "ingestion_errors", "ingestion_runs",
        "field_mapping_proposals", "field_mapping_sessions",
        "ingestion_field_maps", "ingestion_sources",
        "policies", "policyholders", "carrier_calc_config",
        "tenant_calc_config", "tenant_carriers", "tenant_branding",
        "tenant_contacts", "tenant_profiles", "users",
    ]:
        op.drop_table(table, schema=schema, if_exists=True)