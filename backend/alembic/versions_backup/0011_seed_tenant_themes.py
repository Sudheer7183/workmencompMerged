"""Seed system themes into tenant_themes for all existing tenants

Root cause:
  The initial schema migration creates the tenant_themes table per tenant but
  never inserts the 4 system themes (Default Dark, Default Light, Corporate Dark,
  Corporate Light) into it.  The carrier_theme_config seed sets default_theme_id=1
  which references a row that does not exist — causing the UndefinedTableError /
  no-row error when any theme endpoint is called.

Fix:
  For every active tenant schema found in public.tenants:
    1. INSERT the 4 system themes into {schema}.tenant_themes (ON CONFLICT DO NOTHING
       so re-running is safe).
    2. Ensure carrier_theme_config rows reference a valid theme_id (update any row
       that still points to the non-existent id=1 placeholder).

Down migration:
  Removes the seeded system theme rows from all tenant schemas.
  Does NOT drop the table — that was created in 0001.

Revision: 0011_seed_tenant_themes
"""

revision = "0011_seed_tenant_themes"
down_revision = "0010_dashboard_fix_view"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# System theme data — Addendum S4 exact hex values
# ---------------------------------------------------------------------------

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

_INSERT_THEME_SQL = """
    INSERT INTO "{schema}".tenant_themes
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
    ON CONFLICT DO NOTHING
"""

# After inserting, the 4 system themes will have theme_id 1-4 (on a fresh tenant).
# Resolve the real theme_id for "Default Dark" and update carrier_theme_config rows
# that still reference the non-existent placeholder id=1 (which is what the seed set).
_FIX_CARRIER_THEME_SQL = """
    UPDATE "{schema}".carrier_theme_config
    SET    default_theme_id = (
               SELECT theme_id
               FROM   "{schema}".tenant_themes
               WHERE  theme_name = 'Default Dark'
               LIMIT  1
           )
    WHERE  default_theme_id NOT IN (
               SELECT theme_id FROM "{schema}".tenant_themes
           )
"""


def upgrade() -> None:
    conn = op.get_bind()

    # Fetch all active tenant schema names
    result = conn.execute(
        sa.text("SELECT schema_name FROM public.tenants WHERE status = 'ACTIVE'")
    )
    schemas = [row[0] for row in result.fetchall()]

    for schema in schemas:
        # 1. Seed the 4 system themes
        for theme in _SYSTEM_THEMES:
            conn.execute(
                sa.text(_INSERT_THEME_SQL.format(schema=schema)),
                theme,
            )

        # 2. Fix any carrier_theme_config rows pointing to a non-existent theme_id
        conn.execute(sa.text(_FIX_CARRIER_THEME_SQL.format(schema=schema)))


def downgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(
        sa.text("SELECT schema_name FROM public.tenants WHERE status = 'ACTIVE'")
    )
    schemas = [row[0] for row in result.fetchall()]

    for schema in schemas:
        conn.execute(
            sa.text(
                f'DELETE FROM "{schema}".tenant_themes WHERE is_system = TRUE'
            )
        )