"""Phase 7C — carrier_llm_config table + ingestion_runs narrative columns

Revision ID: 0012_phase7c_llm_config
Revises: 0011_seed_tenant_themes
"""
from alembic import op, context
import sqlalchemy as sa

revision = "0012_phase7c_llm_config"
down_revision = "0011_seed_tenant_themes"
branch_labels = None
depends_on = None


def _s() -> str:
    """
    Return the schema currently being migrated.
    Reads version_table_schema which env.py sets correctly for every
    schema (public, tenant_demo, tenant_newdomain, etc.).
    Never relies on -x CLI args which are not passed by env.py.
    """
    return context.get_context().version_table_schema or "public"


def upgrade() -> None:
    schema = _s()

    if schema == "public":
        # No public-schema changes in this migration.
        return

    # ── carrier_llm_config (tenant schema) ──────────────────────────────────
    # One row per carrier; seeded as unconfigured (all nullable fields NULL).
    # Updated in-place when TENANT_ADMIN configures a provider.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.carrier_llm_config (
            config_id       BIGSERIAL PRIMARY KEY,
            carrier_id      BIGINT    NOT NULL UNIQUE,
            provider_name   VARCHAR(50),
            model_name      VARCHAR(100),
            api_key_enc     TEXT,
            api_base_url    TEXT,
            is_active       BOOLEAN   NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by      TEXT      NOT NULL DEFAULT 'system'
        )
    """)

    # ── ingestion_runs — narrative columns ───────────────────────────────────
    # ADD COLUMN IF NOT EXISTS makes this idempotent on re-run.
    op.execute(f"""
        ALTER TABLE {schema}.ingestion_runs
        ADD COLUMN IF NOT EXISTS narrative_text          TEXT,
        ADD COLUMN IF NOT EXISTS narrative_provider      VARCHAR(50),
        ADD COLUMN IF NOT EXISTS narrative_generated_at  TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS narrative_is_fallback   BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # ── Seed placeholder llm_config row for existing tenant_carriers ─────────
    # For tenants that already have carriers assigned (pre-7C), seed the
    # placeholder row so the config screen shows "unconfigured" rather than 404.
    op.execute(f"""
        INSERT INTO {schema}.carrier_llm_config (carrier_id, is_active, created_by)
        SELECT tc.carrier_id, FALSE, 'migration'
        FROM   {schema}.tenant_carriers tc
        LEFT JOIN {schema}.carrier_llm_config clc ON clc.carrier_id = tc.carrier_id
        WHERE  clc.carrier_id IS NULL
          AND  tc.is_active = TRUE
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    schema = _s()

    if schema == "public":
        return

    op.execute(f"""
        ALTER TABLE {schema}.ingestion_runs
        DROP COLUMN IF EXISTS narrative_text,
        DROP COLUMN IF EXISTS narrative_provider,
        DROP COLUMN IF EXISTS narrative_generated_at,
        DROP COLUMN IF EXISTS narrative_is_fallback
    """)

    op.execute(f"DROP TABLE IF EXISTS {schema}.carrier_llm_config")