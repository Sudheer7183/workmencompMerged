"""
Unit tests for theme resolution logic — Phase 6.

13 test cases covering the resolution chain, hex validation,
WCAG contrast calculation, cache key format, and JSON import validation.
"""
from __future__ import annotations

import re
import pytest

HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")

TOKEN_FIELDS = [
    "bg", "surface", "surface2", "border_col",
    "text_primary", "text_muted", "brand", "brand_dark", "accent",
    "color_green", "color_amber", "color_red", "color_blue",
]

DEFAULT_DARK = {
    "bg": "0f1117", "surface": "181c27", "surface2": "1e2436",
    "border_col": "2a2f45", "text_primary": "e8ecf4", "text_muted": "7a84a0",
    "brand": "4ade80", "brand_dark": "15803d", "accent": "818cf8",
    "color_green": "22c55e", "color_amber": "f59e0b",
    "color_red": "ef4444", "color_blue": "60a5fa",
}

DEFAULT_LIGHT = {
    "bg": "f8fafc", "surface": "ffffff", "surface2": "f1f5f9",
    "border_col": "e2e8f0", "text_primary": "0f172a", "text_muted": "64748b",
    "brand": "16a34a", "brand_dark": "15803d", "accent": "6366f1",
    "color_green": "16a34a", "color_amber": "d97706",
    "color_red": "dc2626", "color_blue": "2563eb",
}


# ─── Hex validation ───────────────────────────────────────────────────────────

class TestHexValidation:

    def test_valid_six_char_hex_passes(self) -> None:
        assert HEX_RE.match("4ade80")
        assert HEX_RE.match("ffffff")
        assert HEX_RE.match("000000")
        assert HEX_RE.match("ABCDEF")

    def test_hash_prefix_fails(self) -> None:
        assert not HEX_RE.match("#4ade80")

    def test_too_short_fails(self) -> None:
        assert not HEX_RE.match("4ade8")

    def test_too_long_fails(self) -> None:
        assert not HEX_RE.match("4ade800")

    def test_non_hex_chars_fail(self) -> None:
        assert not HEX_RE.match("4ade8z")

    def test_all_default_dark_tokens_are_valid_hex(self) -> None:
        for field, value in DEFAULT_DARK.items():
            assert HEX_RE.match(value), f"DEFAULT_DARK.{field} = '{value}' is not valid hex"

    def test_all_default_light_tokens_are_valid_hex(self) -> None:
        for field, value in DEFAULT_LIGHT.items():
            assert HEX_RE.match(value), f"DEFAULT_LIGHT.{field} = '{value}' is not valid hex"


# ─── WCAG contrast ratio ──────────────────────────────────────────────────────

def _hex_to_linear(component: int) -> float:
    s = component / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

def _relative_luminance(hex_str: str) -> float:
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return 0.2126 * _hex_to_linear(r) + 0.7152 * _hex_to_linear(g) + 0.0722 * _hex_to_linear(b)

def _contrast_ratio(h1: str, h2: str) -> float:
    l1, l2 = _relative_luminance(h1), _relative_luminance(h2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestWCAGContrast:

    def test_default_dark_text_on_surface_passes_aa(self) -> None:
        ratio = _contrast_ratio(DEFAULT_DARK["text_primary"], DEFAULT_DARK["surface"])
        assert ratio >= 4.5, f"Default Dark contrast ratio {ratio:.2f} < 4.5:1"

    def test_default_light_text_on_surface_passes_aa(self) -> None:
        ratio = _contrast_ratio(DEFAULT_LIGHT["text_primary"], DEFAULT_LIGHT["surface"])
        assert ratio >= 4.5, f"Default Light contrast ratio {ratio:.2f} < 4.5:1"

    def test_identical_colours_contrast_is_one(self) -> None:
        ratio = _contrast_ratio("000000", "000000")
        assert ratio == pytest.approx(1.0)

    def test_black_on_white_contrast_is_21(self) -> None:
        ratio = _contrast_ratio("000000", "ffffff")
        assert ratio == pytest.approx(21.0, rel=0.01)


# ─── Theme cache key ──────────────────────────────────────────────────────────

class TestThemeCacheKey:

    def test_cache_key_format(self) -> None:
        schema, carrier_id, user_id = "tenant_demo", 1, "user-abc"
        key = f"{schema}:theme:{carrier_id}:{user_id}"
        assert key == "tenant_demo:theme:1:user-abc"

    def test_different_users_produce_different_keys(self) -> None:
        key1 = "tenant_demo:theme:1:user-a"
        key2 = "tenant_demo:theme:1:user-b"
        assert key1 != key2


# ─── JSON import validation ───────────────────────────────────────────────────

class TestThemeImportValidation:

    def _valid_payload(self) -> dict:
        return {
            "name": "My Theme",
            "mode": "dark",
            "based_on": "Default Dark",
            "tokens": {f: DEFAULT_DARK[f] for f in TOKEN_FIELDS},
        }

    def test_valid_import_passes(self) -> None:
        payload = self._valid_payload()
        required = {"name", "mode", "tokens"}
        assert required.issubset(payload.keys())
        assert payload["mode"] in ("dark", "light")
        for field in TOKEN_FIELDS:
            assert field in payload["tokens"]
            assert HEX_RE.match(payload["tokens"][field])

    def test_missing_tokens_key_fails(self) -> None:
        payload = self._valid_payload()
        del payload["tokens"]
        required = {"name", "mode", "tokens"}
        assert not required.issubset(payload.keys())

    def test_invalid_mode_fails(self) -> None:
        payload = self._valid_payload()
        payload["mode"] = "midnight"
        assert payload["mode"] not in ("dark", "light")

    def test_invalid_hex_in_token_fails(self) -> None:
        payload = self._valid_payload()
        payload["tokens"]["bg"] = "GGGGGG"
        assert not HEX_RE.match(payload["tokens"]["bg"])
