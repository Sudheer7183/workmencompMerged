"""Seed system themes — no-op on public pass, seeds on tenant pass

Revision ID: 0011_seed_tenant_themes
Revises: 0010_dashboard_fix_view
"""
from alembic import op, context
import sqlalchemy as sa

revision = "0011_seed_tenant_themes"
down_revision = "0010_dashboard_fix_view"
branch_labels = None
depends_on = None

_THEMES = [
    {"theme_name":"Default Dark","mode":"dark","is_system":True,"bg":"0f1117","surface":"181c27","surface2":"1e2436","border_col":"2a2f45","text_primary":"e8ecf4","text_muted":"7a84a0","brand":"4ade80","brand_dark":"15803d","accent":"818cf8","color_green":"22c55e","color_amber":"f59e0b","color_red":"ef4444","color_blue":"60a5fa"},
    {"theme_name":"Default Light","mode":"light","is_system":True,"bg":"f8fafc","surface":"ffffff","surface2":"f1f5f9","border_col":"e2e8f0","text_primary":"0f172a","text_muted":"64748b","brand":"16a34a","brand_dark":"15803d","accent":"6366f1","color_green":"16a34a","color_amber":"d97706","color_red":"dc2626","color_blue":"2563eb"},
    {"theme_name":"Corporate Dark","mode":"dark","is_system":True,"bg":"0a0e1a","surface":"111827","surface2":"1f2937","border_col":"374151","text_primary":"f9fafb","text_muted":"9ca3af","brand":"3b82f6","brand_dark":"1d4ed8","accent":"a78bfa","color_green":"10b981","color_amber":"f59e0b","color_red":"ef4444","color_blue":"60a5fa"},
    {"theme_name":"Corporate Light","mode":"light","is_system":True,"bg":"ffffff","surface":"f9fafb","surface2":"f3f4f6","border_col":"d1d5db","text_primary":"111827","text_muted":"6b7280","brand":"1d4ed8","brand_dark":"1e3a8a","accent":"7c3aed","color_green":"059669","color_amber":"d97706","color_red":"dc2626","color_blue":"2563eb"},
]

_INSERT = """
    INSERT INTO "{s}".tenant_themes
      (theme_name,mode,is_system,bg,surface,surface2,border_col,
       text_primary,text_muted,brand,brand_dark,accent,
       color_green,color_amber,color_red,color_blue)
    VALUES
      (:theme_name,:mode,:is_system,:bg,:surface,:surface2,:border_col,
       :text_primary,:text_muted,:brand,:brand_dark,:accent,
       :color_green,:color_amber,:color_red,:color_blue)
    ON CONFLICT DO NOTHING
"""

_FIX = """
    UPDATE "{s}".carrier_theme_config
    SET default_theme_id = (
        SELECT theme_id FROM "{s}".tenant_themes
        WHERE theme_name = 'Default Dark' LIMIT 1
    )
    WHERE default_theme_id NOT IN (
        SELECT theme_id FROM "{s}".tenant_themes
    )
"""


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    if schema == "public":
        return  # no-op — themes only exist in tenant schemas
    conn = op.get_bind()
    for t in _THEMES:
        conn.execute(sa.text(_INSERT.format(s=schema)), t)
    conn.execute(sa.text(_FIX.format(s=schema)))


def downgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    if schema == "public":
        return
    op.get_bind().execute(
        sa.text(f'DELETE FROM "{schema}".tenant_themes WHERE is_system = TRUE')
    )