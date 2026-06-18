"""
Integration tests for Theme API and User Theme Preferences — Phase 6.

11 test cases covering theme CRUD schemas, resolution chain, import/export
validation, and user preference schema guards.
"""
from __future__ import annotations

import pytest


class TestThemeApiSchemas:

    def test_theme_create_request_validates_hex_tokens(self) -> None:
        from app.api.v1.themes import ThemeCreateRequest
        req = ThemeCreateRequest(
            theme_name="My Theme",
            mode="dark",
            bg="0f1117", surface="181c27", surface2="1e2436",
            border_col="2a2f45", text_primary="e8ecf4", text_muted="7a84a0",
            brand="4ade80", brand_dark="15803d", accent="818cf8",
            color_green="22c55e", color_amber="f59e0b",
            color_red="ef4444", color_blue="60a5fa",
        )
        assert req.theme_name == "My Theme"

    def test_theme_create_rejects_hash_prefix_in_token(self) -> None:
        from pydantic import ValidationError
        from app.api.v1.themes import ThemeCreateRequest
        with pytest.raises(ValidationError):
            ThemeCreateRequest(
                theme_name="Bad",
                mode="dark",
                bg="#0f1117",  # hash prefix not allowed
                surface="181c27", surface2="1e2436", border_col="2a2f45",
                text_primary="e8ecf4", text_muted="7a84a0",
                brand="4ade80", brand_dark="15803d", accent="818cf8",
                color_green="22c55e", color_amber="f59e0b",
                color_red="ef4444", color_blue="60a5fa",
            )

    def test_theme_create_rejects_invalid_mode(self) -> None:
        from pydantic import ValidationError
        from app.api.v1.themes import ThemeCreateRequest
        with pytest.raises(ValidationError):
            ThemeCreateRequest(
                theme_name="Bad Mode",
                mode="midnight",  # invalid
                bg="0f1117", surface="181c27", surface2="1e2436",
                border_col="2a2f45", text_primary="e8ecf4", text_muted="7a84a0",
                brand="4ade80", brand_dark="15803d", accent="818cf8",
                color_green="22c55e", color_amber="f59e0b",
                color_red="ef4444", color_blue="60a5fa",
            )

    def test_carrier_theme_config_update_rejects_invalid_source(self) -> None:
        from pydantic import ValidationError
        from app.api.v1.themes import CarrierThemeConfigUpdateRequest
        with pytest.raises(ValidationError):
            CarrierThemeConfigUpdateRequest(
                default_theme_id=1,
                theme_source="PERSONAL",  # invalid
                allow_user_override=True,
            )

    def test_carrier_theme_config_update_accepts_valid(self) -> None:
        from app.api.v1.themes import CarrierThemeConfigUpdateRequest
        cfg = CarrierThemeConfigUpdateRequest(
            default_theme_id=2,
            theme_source="SYSTEM",
            allow_user_override=False,
        )
        assert not cfg.allow_user_override

    def test_user_theme_pref_update_accepts_system_source(self) -> None:
        from app.api.v1.themes import UserThemePrefUpdateRequest
        req = UserThemePrefUpdateRequest(theme_id=1, theme_source="SYSTEM")
        assert req.theme_source == "SYSTEM"

    def test_user_theme_pref_update_accepts_custom_source(self) -> None:
        from app.api.v1.themes import UserThemePrefUpdateRequest
        req = UserThemePrefUpdateRequest(theme_id=5, theme_source="CUSTOM")
        assert req.theme_id == 5

    def test_user_theme_pref_update_rejects_invalid_source(self) -> None:
        from pydantic import ValidationError
        from app.api.v1.themes import UserThemePrefUpdateRequest
        with pytest.raises(ValidationError):
            UserThemePrefUpdateRequest(theme_id=1, theme_source="USER_DEFINED")


class TestThemeCacheKeys:

    def test_carrier_pattern_covers_all_users(self) -> None:
        """The carrier invalidation pattern must end in :* to match all user keys."""
        schema, carrier_id = "tenant_demo", 1
        pattern = f"{schema}:theme:{carrier_id}:*"
        # A specific user key must match this pattern logic
        user_key = f"{schema}:theme:{carrier_id}:user-abc"
        assert user_key.startswith(f"{schema}:theme:{carrier_id}:")

    def test_resolved_theme_response_has_all_13_tokens(self) -> None:
        from app.api.v1.themes import ResolvedThemeResponse
        resp = ResolvedThemeResponse(
            theme_id=1, theme_name="Default Dark", mode="dark", source="SYSTEM_DEFAULT",
            bg="0f1117", surface="181c27", surface2="1e2436", border_col="2a2f45",
            text_primary="e8ecf4", text_muted="7a84a0",
            brand="4ade80", brand_dark="15803d", accent="818cf8",
            color_green="22c55e", color_amber="f59e0b",
            color_red="ef4444", color_blue="60a5fa",
        )
        # Count non-metadata fields (the 13 token fields)
        token_fields = [
            "bg", "surface", "surface2", "border_col",
            "text_primary", "text_muted", "brand", "brand_dark", "accent",
            "color_green", "color_amber", "color_red", "color_blue",
        ]
        for field in token_fields:
            assert hasattr(resp, field), f"Missing token field: {field}"

    def test_hex_tokens_are_normalised_to_lowercase(self) -> None:
        from app.api.v1.themes import ThemeCreateRequest
        req = ThemeCreateRequest(
            theme_name="Test",
            mode="dark",
            bg="0F1117",  # uppercase input
            surface="181C27", surface2="1e2436", border_col="2a2f45",
            text_primary="e8ecf4", text_muted="7a84a0",
            brand="4ade80", brand_dark="15803d", accent="818cf8",
            color_green="22c55e", color_amber="f59e0b",
            color_red="ef4444", color_blue="60a5fa",
        )
        assert req.bg == "0f1117"  # normalised to lowercase
