"""
Test data factories — plain dataclass builders (no factory_boy dependency).
Each factory returns a dict of column values that can be passed to a raw INSERT
or to a SQLAlchemy ORM constructor.

Designed to be used with the mock_db fixture in unit tests and with
the real async session in integration tests.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any


def make_policy(
    policy_id: int = 1,
    carrier_id: int = 1,
    policyholder_id: int = 1,
    policy_number: str = "WC-TEST-001",
    state_code: str = "CA",
    policy_status: str = "Active",
    audit_status: str = "Pending",
    risk_level: str | None = None,
    payment_frequency: str = "Monthly",
    effective_date: date = date(2024, 1, 1),
    expiration_date: date = date(2025, 1, 1),
    premium_written: Decimal = Decimal("120000"),
) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "carrier_id": carrier_id,
        "policyholder_id": policyholder_id,
        "policy_number": policy_number,
        "state_code": state_code,
        "effective_date": effective_date,
        "expiration_date": expiration_date,
        "cancellation_date": None,
        "premium_written": premium_written,
        "payment_frequency": payment_frequency,
        "owner_status": "Included",
        "policy_status": policy_status,
        "audit_status": audit_status,
        "risk_level": risk_level,
        "total_est_payroll": None,
        "deleted_at": None,
    }


def make_policyholder(
    policyholder_id: int = 1,
    carrier_id: int = 1,
    name: str = "Test Manufacturing Inc.",
    fein: str = "12-3456789",
) -> dict[str, Any]:
    return {
        "policyholder_id": policyholder_id,
        "carrier_id": carrier_id,
        "name": name,
        "fein": fein,
        "address": "123 Test St, Los Angeles, CA 90001",
        "deleted_at": None,
    }


def make_premium_variance(
    policy_id: int = 1,
    carrier_id: int = 1,
    ingestion_run_id: int = 1,
    est_premium_end: Decimal = Decimal("100000"),
    actual_premium: Decimal = Decimal("115000"),
    variance_pct: Decimal | None = Decimal("0.15"),
    as_of_date: date = date(2024, 6, 30),
) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "carrier_id": carrier_id,
        "ingestion_run_id": ingestion_run_id,
        "as_of_date": as_of_date,
        "est_premium_end": est_premium_end,
        "actual_premium": actual_premium,
        # variance_amount is GENERATED — do not include in INSERT
        "variance_pct": variance_pct,
    }


def make_payroll_variance_policy(
    policy_id: int = 1,
    carrier_id: int = 1,
    ingestion_run_id: int = 1,
    est_payroll: Decimal = Decimal("500000"),
    actual_payroll_reported: Decimal = Decimal("540000"),
    actual_payroll_classified: Decimal = Decimal("530000"),
    reported_pct: Decimal | None = Decimal("1.08"),
    classified_pct: Decimal | None = Decimal("1.06"),
    as_of_date: date = date(2024, 6, 30),
) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "carrier_id": carrier_id,
        "ingestion_run_id": ingestion_run_id,
        "as_of_date": as_of_date,
        "est_payroll": est_payroll,
        "actual_payroll_reported": actual_payroll_reported,
        # reported_over_under is GENERATED
        "reported_pct": reported_pct,
        "actual_payroll_classified": actual_payroll_classified,
        # classified_over_under is GENERATED
        "classified_pct": classified_pct,
    }


def make_ingestion_run(
    run_id: int = 1,
    carrier_id: int = 1,
    source_id: int = 1,
    status: str = "complete",
    rows_ingested: int = 50,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "carrier_id": carrier_id,
        "source_id": source_id,
        "uploaded_by": "test@demo.example.com",
        "status": status,
        "rows_ingested": rows_ingested,
        "rows_skipped": 0,
        "rows_failed": 0,
        "skip_on_error": False,
        "use_calculation_engine": None,
        "error_detail": None,
        "s3_file_key": None,
    }
