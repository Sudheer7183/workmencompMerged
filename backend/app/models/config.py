"""
ORM Models — Phase 6 Config Tables.

Covers six tables that were defined in the 0001_initial_schema.py migration
but had no corresponding ORM models until Phase 6:

  carrier_ui_labels      — carrier-specific UI string overrides
  carrier_display_config — column visibility, ordering, conditional formatting
  carrier_theme_config   — which theme is the default for a carrier
  tenant_themes          — custom themes created by TENANT_ADMIN
  user_theme_prefs       — per-user theme override (when carrier allows it)
  cleanup_runs           — audit log for database cleanup operations

All tables live in the tenant schema (search_path controls resolution).
References: V9 S11.11, Theme Addendum S2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Identity, Integer, Text, CHAR
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CarrierUiLabel(Base):
    """
    carrier_ui_labels — carrier-specific display string overrides.

    Each row overrides one label key within a given screen namespace.
    The resolution chain: carrier override → DEFAULT_LABELS fallback.
    Reference: V9 S23.
    """

    __tablename__ = "carrier_ui_labels"

    label_id:   Mapped[int] = mapped_column(BigInteger(), Identity(), primary_key=True)
    carrier_id: Mapped[int] = mapped_column(BigInteger(), nullable=False, index=True)
    screen_key: Mapped[str] = mapped_column(Text(), nullable=False)
    field_key:  Mapped[str] = mapped_column(Text(), nullable=False)
    label_text: Mapped[str] = mapped_column(Text(), nullable=False)


class CarrierDisplayConfig(Base):
    """
    carrier_display_config — column visibility, ordering, and conditional
    formatting rules per screen and field.

    Reference: V9 S23.
    """

    __tablename__ = "carrier_display_config"

    config_id:               Mapped[int]           = mapped_column(BigInteger(), Identity(), primary_key=True)
    carrier_id:              Mapped[int]            = mapped_column(BigInteger(), nullable=False, index=True)
    screen_key:              Mapped[str]            = mapped_column(Text(), nullable=False)
    field_key:               Mapped[str]            = mapped_column(Text(), nullable=False)
    is_visible:              Mapped[bool]           = mapped_column(Boolean(), nullable=False, server_default="TRUE")
    display_order:           Mapped[Optional[int]]  = mapped_column(Integer(), nullable=True)
    conditional_format_rule: Mapped[Optional[dict]] = mapped_column(JSONB(), nullable=True)  # type: ignore[type-arg]


class CarrierThemeConfig(Base):
    """
    carrier_theme_config — which theme is the default for a carrier, and
    whether users are permitted to override it.

    One row per carrier_id; upserted by the carrier theme config endpoints.
    Reference: V9 S24, Addendum S2.
    """

    __tablename__ = "carrier_theme_config"

    carrier_id:          Mapped[int]  = mapped_column(BigInteger(), primary_key=True)
    theme_source:        Mapped[str]  = mapped_column(Text(), nullable=False, server_default="SYSTEM")
    default_theme_id:    Mapped[int]  = mapped_column(BigInteger(), nullable=False, server_default="1")
    allow_user_override: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="TRUE")


class TenantTheme(Base):
    """
    tenant_themes — custom themes created by TENANT_ADMIN.

    is_system is always FALSE for rows in this table; the four system
    themes live in public.theme_definitions and are never written here.
    All 13 CSS token columns store hex colour WITHOUT the leading '#'.
    Reference: Addendum S2, S4, S5.
    """

    __tablename__ = "tenant_themes"

    theme_id:      Mapped[int]           = mapped_column(BigInteger(), Identity(), primary_key=True)
    theme_name:    Mapped[str]           = mapped_column(Text(), nullable=False)
    mode:          Mapped[str]           = mapped_column(Text(), nullable=False)
    is_system:     Mapped[bool]          = mapped_column(Boolean(), nullable=False, server_default="FALSE")

    # 13 CSS token columns — hex without '#', CHAR(6)
    bg:            Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    surface:       Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    surface2:      Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    border_col:    Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    text_primary:  Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    text_muted:    Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    brand:         Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    brand_dark:    Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    accent:        Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    color_green:   Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    color_amber:   Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    color_red:     Mapped[str]           = mapped_column(CHAR(6), nullable=False)
    color_blue:    Mapped[str]           = mapped_column(CHAR(6), nullable=False)

    based_on_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_by:    Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(nullable=False)
    updated_at:    Mapped[datetime]      = mapped_column(nullable=False)


class UserThemePref(Base):
    """
    user_theme_prefs — per-user theme override, applied when the carrier's
    allow_user_override flag is TRUE.

    Primary key is the user's Keycloak subject ID (text).
    Reference: V9 S24, Addendum S8.
    """

    __tablename__ = "user_theme_prefs"

    user_keycloak_id: Mapped[str] = mapped_column(Text(), primary_key=True)
    theme_source:     Mapped[str] = mapped_column(Text(), nullable=False, server_default="SYSTEM")
    theme_id:         Mapped[int] = mapped_column(BigInteger(), nullable=False)


class CleanupRun(Base):
    """
    cleanup_runs — immutable audit log for database cleanup operations.

    Written by CleanupService.execute(). Never deleted by the cleanup
    process itself — this table is always preserved.
    Reference: V9 S22.
    """

    __tablename__ = "cleanup_runs"

    cleanup_id:        Mapped[int]               = mapped_column(BigInteger(), Identity(), primary_key=True)
    initiated_by:      Mapped[str]               = mapped_column(Text(), nullable=False)
    initiated_at:      Mapped[datetime]           = mapped_column(nullable=False)
    status:            Mapped[str]               = mapped_column(Text(), nullable=False, server_default="IN_PROGRESS")
    policies_archived: Mapped[Optional[int]]      = mapped_column(nullable=True)
    completed_at:      Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_detail:      Mapped[Optional[str]]      = mapped_column(Text(), nullable=True)
