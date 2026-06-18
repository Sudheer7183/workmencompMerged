"""
Unit tests for field_descriptors.py.

Verifies that every SAFE_NAMES key (excluding Python built-ins) has a
corresponding FieldDescriptor entry with required fields populated.
"""
from __future__ import annotations

import pytest

from app.rules.field_descriptors import FIELD_DESCRIPTORS, get_descriptor, get_all_descriptors
from app.services.audit_calculation_service import SAFE_NAMES

# SAFE_NAMES keys that are Python built-ins (not user-facing fields)
_BUILTIN_SAFE_NAMES = {"True", "False", "None"}

# User-facing SAFE_NAMES keys that should have descriptors
_EXPECTED_FIELD_NAMES = {
    key for key in SAFE_NAMES.keys() if key not in _BUILTIN_SAFE_NAMES
}


class TestFieldDescriptors:
    def test_all_safe_names_have_descriptors(self):
        """Every user-facing SAFE_NAMES key must have a FieldDescriptor."""
        descriptor_names = {fd.name for fd in FIELD_DESCRIPTORS}
        missing = _EXPECTED_FIELD_NAMES - descriptor_names
        assert not missing, f"Missing descriptors for SAFE_NAMES keys: {sorted(missing)}"

    def test_no_extra_descriptors(self):
        """No descriptor should reference a key not in SAFE_NAMES."""
        descriptor_names = {fd.name for fd in FIELD_DESCRIPTORS}
        extra = descriptor_names - _EXPECTED_FIELD_NAMES
        assert not extra, f"Extra descriptors not in SAFE_NAMES: {sorted(extra)}"

    def test_all_descriptors_have_required_fields(self):
        """Each descriptor must have non-empty label, description, data_type, category."""
        for fd in FIELD_DESCRIPTORS:
            assert fd.label, f"{fd.name}: label is empty"
            assert fd.description, f"{fd.name}: description is empty"
            assert fd.data_type in {"number", "integer", "boolean"}, \
                f"{fd.name}: unexpected data_type '{fd.data_type}'"
            assert fd.category in {"payroll", "premium", "class_code", "officer", "submission"}, \
                f"{fd.name}: unexpected category '{fd.category}'"
            assert fd.example_value, f"{fd.name}: example_value is empty"

    def test_get_descriptor_by_name(self):
        fd = get_descriptor("actual_premium")
        assert fd is not None
        assert fd.name == "actual_premium"
        assert fd.category == "premium"

    def test_get_descriptor_returns_none_for_unknown(self):
        assert get_descriptor("nonexistent_field") is None

    def test_get_all_descriptors_returns_sorted_list(self):
        descriptors = get_all_descriptors()
        assert len(descriptors) == len(FIELD_DESCRIPTORS)
        # Should be sorted by category then name
        for i in range(len(descriptors) - 1):
            a = descriptors[i]
            b = descriptors[i + 1]
            assert (a.category, a.name) <= (b.category, b.name), \
                f"Order wrong: {a.name} ({a.category}) > {b.name} ({b.category})"

    def test_no_duplicate_names(self):
        names = [fd.name for fd in FIELD_DESCRIPTORS]
        assert len(names) == len(set(names)), "Duplicate descriptor names found"

    def test_descriptors_cover_payroll_category(self):
        payroll_fields = [fd for fd in FIELD_DESCRIPTORS if fd.category == "payroll"]
        assert len(payroll_fields) >= 5, "Expected at least 5 payroll fields"

    def test_descriptors_cover_premium_category(self):
        premium_fields = [fd for fd in FIELD_DESCRIPTORS if fd.category == "premium"]
        assert len(premium_fields) >= 3, "Expected at least 3 premium fields"
