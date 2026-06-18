"""Phase 7 — Add public.platform_themes table for Super Admin theme management.

The existing public.theme_definitions table uses the 13-column hex schema
and is read by themes.py for the tenant theme resolution chain. It must NOT
be altered.

This migration adds a separate public.platform_themes table that uses the
modern JSONB token schema — this is what platform.py (Super Admin panel)
reads and writes. The two tables are fully independent:

  public.theme_definitions  →  tenant theme resolution fallback (old schema, untouched)
  public.platform_themes    →  super admin Platform Themes panel (new JSONB schema)

Revision ID: 0013_add_platform_themes
Revises:     0012_phase7c_llm_config
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_add_platform_themes"
down_revision = "0012_phase7c_llm_config"
branch_labels = None
depends_on = None

_SEED_THEMES = [
    {
        "theme_name": "Default Dark",
        "base_mode": "dark",
        "is_default": True,
        "tokens": {
            "--bg": "#0f1117", "--surface": "#181c27", "--surface-2": "#1e2436",
            "--border": "#2a2f45", "--text-primary": "#e8ecf4", "--text-muted": "#7a84a0",
            "--brand": "#4ade80", "--brand-dark": "#15803d", "--accent": "#818cf8",
            "--color-green": "#22c55e", "--color-amber": "#f59e0b",
            "--color-red": "#ef4444", "--color-blue": "#60a5fa",
        },
    },
    {
        "theme_name": "Default Light",
        "base_mode": "light",
        "is_default": False,
        "tokens": {
            "--bg": "#f8fafc", "--surface": "#ffffff", "--surface-2": "#f1f5f9",
            "--border": "#e2e8f0", "--text-primary": "#0f172a", "--text-muted": "#64748b",
            "--brand": "#16a34a", "--brand-dark": "#15803d", "--accent": "#6366f1",
            "--color-green": "#16a34a", "--color-amber": "#d97706",
            "--color-red": "#dc2626", "--color-blue": "#2563eb",
        },
    },
    {
        "theme_name": "Corporate Dark",
        "base_mode": "dark",
        "is_default": False,
        "tokens": {
            "--bg": "#0a0e1a", "--surface": "#111827", "--surface-2": "#1f2937",
            "--border": "#374151", "--text-primary": "#f9fafb", "--text-muted": "#9ca3af",
            "--brand": "#3b82f6", "--brand-dark": "#1d4ed8", "--accent": "#a78bfa",
            "--color-green": "#10b981", "--color-amber": "#f59e0b",
            "--color-red": "#ef4444", "--color-blue": "#60a5fa",
        },
    },
    {
        "theme_name": "Corporate Light",
        "base_mode": "light",
        "is_default": False,
        "tokens": {
            "--bg": "#ffffff", "--surface": "#f9fafb", "--surface-2": "#f3f4f6",
            "--border": "#d1d5db", "--text-primary": "#111827", "--text-muted": "#6b7280",
            "--brand": "#1d4ed8", "--brand-dark": "#1e3a8a", "--accent": "#7c3aed",
            "--color-green": "#059669", "--color-amber": "#d97706",
            "--color-red": "#dc2626", "--color-blue": "#2563eb",
        },
    },
]


def upgrade() -> None:
    import json

    # Create the new platform_themes table — completely separate from theme_definitions
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.platform_themes (
            theme_id    BIGSERIAL    PRIMARY KEY,
            theme_name  TEXT         NOT NULL UNIQUE,
            base_mode   TEXT         NOT NULL DEFAULT 'dark'
                            CONSTRAINT ck_platform_themes_base_mode
                            CHECK (base_mode IN ('dark', 'light')),
            tokens      JSONB        NOT NULL DEFAULT '{}',
            is_default  BOOLEAN      NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)

    # Enforce only one default at a time
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_themes_one_default
            ON public.platform_themes (is_default)
            WHERE is_default = TRUE
    """)

    # Seed the four built-in platform themes
    for theme in _SEED_THEMES:
        op.execute(
            sa.text(
                "INSERT INTO public.platform_themes "
                "(theme_name, base_mode, tokens, is_default) "
                "VALUES (:name, :mode, cast(:tokens as jsonb), :is_default) "
                "ON CONFLICT (theme_name) DO NOTHING"
            ).bindparams(
                name=theme["theme_name"],
                mode=theme["base_mode"],
                tokens=json.dumps(theme["tokens"]),
                is_default=theme["is_default"],
            )
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_platform_themes_one_default")
    op.execute("DROP TABLE IF EXISTS public.platform_themes")