"""
Field descriptors — human-readable metadata for every key in SAFE_NAMES.

These are served via GET /api/v1/admin/calc-rules/available-fields and
consumed by the frontend ExpressionBuilder drag-and-drop widget.

RULE: One FieldDescriptor entry for every key in SAFE_NAMES (excluding
Python built-ins True, False, None which are not user-facing fields).

The SAFE_NAMES dictionary lives in audit_calculation_service.py and must
not be modified. This file is the companion descriptor registry.
"""
from __future__ import annotations

from pydantic import BaseModel


class FieldDescriptor(BaseModel):
    """Human-readable description of a single SAFE_NAMES variable."""

    name: str         # Exact SAFE_NAMES key, e.g. "actual_premium"
    label: str        # Human-readable display name
    description: str  # One-sentence explanation of what this field represents
    data_type: str    # "number" | "integer" | "boolean"
    category: str     # "payroll" | "premium" | "class_code" | "officer" | "submission"
    example_value: str  # Representative value for tooltip display


# ---------------------------------------------------------------------------
# FIELD_DESCRIPTORS — one entry per SAFE_NAMES key (excluding True/False/None)
# ---------------------------------------------------------------------------
FIELD_DESCRIPTORS: list[FieldDescriptor] = [
    # ── Premium fields ───────────────────────────────────────────────────────
    FieldDescriptor(
        name="actual_premium",
        label="Actual Premium (Audited)",
        description="The premium amount as determined by the completed audit.",
        data_type="number",
        category="premium",
        example_value="14250.00",
    ),
    FieldDescriptor(
        name="est_premium_end",
        label="Estimated Premium (End of Term)",
        description="The projected premium at the end of the policy term.",
        data_type="number",
        category="premium",
        example_value="13800.00",
    ),
    FieldDescriptor(
        name="variance_amount",
        label="Premium Variance Amount ($)",
        description="The dollar difference between actual and estimated premium.",
        data_type="number",
        category="premium",
        example_value="450.00",
    ),
    FieldDescriptor(
        name="variance_pct",
        label="Premium Variance (%)",
        description="The variance as a percentage of estimated premium (decimal, e.g. 0.25 = 25%).",
        data_type="number",
        category="premium",
        example_value="0.033",
    ),
    # ── Payroll fields ───────────────────────────────────────────────────────
    FieldDescriptor(
        name="actual_payroll_reported",
        label="Actual Payroll (Reported)",
        description="The payroll amount as reported by the employer on audit submissions.",
        data_type="number",
        category="payroll",
        example_value="285000.00",
    ),
    FieldDescriptor(
        name="actual_payroll_classified",
        label="Actual Payroll (Classified)",
        description="The payroll amount after classification by class code.",
        data_type="number",
        category="payroll",
        example_value="280000.00",
    ),
    FieldDescriptor(
        name="est_payroll",
        label="Estimated Payroll",
        description="The payroll amount estimated at policy inception.",
        data_type="number",
        category="payroll",
        example_value="275000.00",
    ),
    FieldDescriptor(
        name="reported_over_under",
        label="Reported Payroll Over/Under ($)",
        description="Dollar difference: actual reported payroll minus estimated payroll.",
        data_type="number",
        category="payroll",
        example_value="10000.00",
    ),
    FieldDescriptor(
        name="classified_over_under",
        label="Classified Payroll Over/Under ($)",
        description="Dollar difference: actual classified payroll minus estimated payroll.",
        data_type="number",
        category="payroll",
        example_value="5000.00",
    ),
    FieldDescriptor(
        name="wages",
        label="Wages",
        description="Total wages reported for the policy period.",
        data_type="number",
        category="payroll",
        example_value="240000.00",
    ),
    # ── Submission tracking fields ───────────────────────────────────────────
    FieldDescriptor(
        name="submitted_count",
        label="Submitted Payroll Count",
        description="Number of payroll submissions received for this policy.",
        data_type="integer",
        category="submission",
        example_value="11",
    ),
    FieldDescriptor(
        name="expected_submissions",
        label="Expected Submission Count",
        description="Number of payroll submissions expected for the policy period.",
        data_type="number",
        category="submission",
        example_value="12",
    ),
    FieldDescriptor(
        name="missing_payrolls",
        label="Missing Payroll Count",
        description="Number of expected payroll submissions that were not received.",
        data_type="integer",
        category="submission",
        example_value="1",
    ),
    FieldDescriptor(
        name="days_elapsed",
        label="Days Elapsed",
        description="Number of calendar days elapsed since policy inception.",
        data_type="integer",
        category="submission",
        example_value="245",
    ),
    FieldDescriptor(
        name="cycle_days",
        label="Payroll Cycle Days",
        description="Length of the payroll cycle in days (e.g. 30 for monthly, 14 for biweekly).",
        data_type="integer",
        category="submission",
        example_value="30",
    ),
    FieldDescriptor(
        name="policy_days",
        label="Policy Term Days",
        description="Total duration of the policy period in days.",
        data_type="integer",
        category="submission",
        example_value="365",
    ),
    FieldDescriptor(
        name="completion_ratio",
        label="Completion Ratio",
        description="Ratio of submitted to expected submissions (0.0 – 1.0).",
        data_type="number",
        category="submission",
        example_value="0.917",
    ),
    FieldDescriptor(
        name="days_since_last_run",
        label="Days Since Last Run",
        description="Calendar days since the most recent ingestion run for this policy.",
        data_type="integer",
        category="submission",
        example_value="7",
    ),
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

_DESCRIPTOR_BY_NAME: dict[str, FieldDescriptor] = {
    fd.name: fd for fd in FIELD_DESCRIPTORS
}


def get_descriptor(name: str) -> FieldDescriptor | None:
    """Returns the FieldDescriptor for a SAFE_NAMES key, or None if not found."""
    return _DESCRIPTOR_BY_NAME.get(name)


def get_all_descriptors() -> list[FieldDescriptor]:
    """Returns all descriptors, ordered by category then name."""
    return sorted(FIELD_DESCRIPTORS, key=lambda fd: (fd.category, fd.name))
