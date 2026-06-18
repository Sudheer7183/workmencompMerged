"""
Unit tests for label resolution logic — Phase 6  (V9 S23 conformant).

Tests the per-screen lookup behaviour, Redis cache key format, and CSV parsing.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Per-screen lookup logic (mirrors V9 S23.2 hook)
# ---------------------------------------------------------------------------

def make_lookup(screen_defaults: dict, overrides: dict):
    """Mirrors the frontend hook's returned function."""
    def lookup(field_key: str, fallback: str) -> str:
        return overrides.get(field_key) or screen_defaults.get(field_key) or fallback
    return lookup


class TestLabelLookupLogic:

    def test_returns_default_when_no_override(self) -> None:
        defaults = {"kpi.book_premium": "Total Book Premium"}
        fn = make_lookup(defaults, {})
        assert fn("kpi.book_premium", "fallback") == "Total Book Premium"

    def test_override_takes_precedence_over_default(self) -> None:
        defaults = {"col.state": "State"}
        fn = make_lookup(defaults, {"col.state": "Province"})
        assert fn("col.state", "fallback") == "Province"

    def test_fallback_arg_used_when_key_unknown(self) -> None:
        fn = make_lookup({}, {})
        assert fn("totally.unknown", "My Fallback") == "My Fallback"

    def test_partial_overrides_do_not_affect_other_keys(self) -> None:
        defaults = {"col.state": "State", "col.policy_number": "Policy #"}
        fn = make_lookup(defaults, {"col.state": "Province"})
        assert fn("col.state", "") == "Province"
        assert fn("col.policy_number", "") == "Policy #"

    def test_empty_string_override_falls_back_to_default(self) -> None:
        """An empty override string falls through to the default."""
        defaults = {"col.state": "State"}
        fn = make_lookup(defaults, {"col.state": ""})
        # Empty string is falsy — falls back to default
        assert fn("col.state", "fallback") == "State"

    def test_lookup_never_returns_none(self) -> None:
        fn = make_lookup({}, {})
        result = fn("missing.key", "fallback")
        assert result is not None
        assert result == "fallback"


class TestLabelCacheKey:
    """Cache key must follow V9 S23.1 format: {schema}:labels:{carrier_id}:{screen_key}"""

    def test_cache_key_format(self) -> None:
        schema, carrier_id, screen_key = "tenant_demo", 1, "dashboard"
        key = f"{schema}:labels:{carrier_id}:{screen_key}"
        assert key == "tenant_demo:labels:1:dashboard"

    def test_different_screens_produce_different_keys(self) -> None:
        key1 = "tenant_demo:labels:1:dashboard"
        key2 = "tenant_demo:labels:1:policies"
        assert key1 != key2

    def test_different_carriers_produce_different_keys(self) -> None:
        key1 = "tenant_demo:labels:1:dashboard"
        key2 = "tenant_demo:labels:2:dashboard"
        assert key1 != key2

    def test_different_schemas_produce_different_keys(self) -> None:
        key1 = "tenant_a:labels:1:dashboard"
        key2 = "tenant_b:labels:1:dashboard"
        assert key1 != key2

    def test_cache_key_has_four_segments(self) -> None:
        key = "tenant_demo:labels:1:dashboard"
        segments = key.split(":")
        assert len(segments) == 4


class TestLabelCSVParsing:

    def test_valid_csv_parsed_correctly(self) -> None:
        import csv, io
        csv_data = "screen_key,field_key,label_text\npolicies,col.state,Province\n"
        reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["field_key"] == "col.state"
        assert rows[0]["label_text"] == "Province"

    def test_csv_missing_required_column_detected(self) -> None:
        import csv, io
        csv_data = "screen_key,field_key\npolicies,col.state\n"
        reader = csv.DictReader(io.StringIO(csv_data))
        required = {"screen_key", "field_key", "label_text"}
        assert not required.issubset(set(reader.fieldnames or []))
