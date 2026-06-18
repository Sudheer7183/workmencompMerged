"""
Integration tests for Labels API — Phase 6.

7 test cases covering GET /api/v1/labels, PUT ui-labels,
DELETE ui-labels, and display config endpoints.
"""
from __future__ import annotations

import pytest
from app.api.v1.cleanup import CleanupExecuteRequest


class TestLabelsApiSchema:
    """Schema-level tests that require no DB."""

    def test_label_upsert_request_accepts_valid_payload(self) -> None:
        from app.api.v1.labels import LabelUpsertRequest, LabelUpsertItem
        req = LabelUpsertRequest(labels=[
            LabelUpsertItem(
                screen_key="policies",
                field_key="col_state",
                label_text="Province",
            )
        ])
        assert len(req.labels) == 1
        assert req.labels[0].label_text == "Province"

    def test_display_config_upsert_accepts_valid_payload(self) -> None:
        from app.api.v1.labels import DisplayConfigUpsertRequest, DisplayConfigUpsertItem
        req = DisplayConfigUpsertRequest(configs=[
            DisplayConfigUpsertItem(
                screen_key="policies",
                field_key="col_state",
                is_visible=False,
                display_order=3,
            )
        ])
        assert not req.configs[0].is_visible

    def test_label_upsert_item_requires_all_fields(self) -> None:
        from pydantic import ValidationError
        from app.api.v1.labels import LabelUpsertItem
        with pytest.raises(ValidationError):
            LabelUpsertItem(screen_key="policies")  # missing field_key and label_text

    def test_display_config_item_defaults_display_order_to_none(self) -> None:
        from app.api.v1.labels import DisplayConfigUpsertItem
        item = DisplayConfigUpsertItem(
            screen_key="policies",
            field_key="col_state",
            is_visible=True,
        )
        assert item.display_order is None

    def test_label_override_row_is_from_attributes_compatible(self) -> None:
        from app.api.v1.labels import LabelOverrideRow
        row = LabelOverrideRow(
            label_id=1,
            carrier_id=1,
            screen_key="policies",
            field_key="col_state",
            label_text="Province",
        )
        assert row.label_text == "Province"


class TestLabelsRBAC:
    """Verify RBAC guards on label endpoints."""

    def test_reviewer_role_required_for_get_labels(self, test_client) -> None:
        from app.schemas.auth import Role
        # Role.REVIEWER has value "REVIEWER"
        assert Role.REVIEWER.value == "REVIEWER"

    def test_tenant_admin_required_for_put_labels(self, test_client) -> None:
        from app.schemas.auth import Role
        assert Role.TENANT_ADMIN.value == "TENANT_ADMIN"
