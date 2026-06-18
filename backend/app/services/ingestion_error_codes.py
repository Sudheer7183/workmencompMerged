from __future__ import annotations

"""
IngestionErrorCode — 8 classification codes per V9 S17.2.

Used by IngestionRowError to classify row-level failures during run_post_approval().
The code is stored in ingestion_errors.error_type and ingestion_skipped_rows.error_codes[].
"""

from enum import StrEnum


class IngestionErrorCode(StrEnum):
    """Eight error codes exactly as specified in V9 S17.2."""

    FIELD_TYPE_MISMATCH    = "FIELD_TYPE_MISMATCH"
    """A field value cannot be coerced to its expected type (e.g. non-numeric premium)."""

    REQUIRED_FIELD_NULL    = "REQUIRED_FIELD_NULL"
    """A required field (e.g. policy_number) is null or blank."""

    POLICY_NOT_FOUND       = "POLICY_NOT_FOUND"
    """Policy lookup or upsert failed — no matching policy record could be created."""

    POLICYHOLDER_DUPLICATE = "POLICYHOLDER_DUPLICATE"
    """Policyholder upsert raised a duplicate constraint exception."""

    DATE_PARSE_FAILURE     = "DATE_PARSE_FAILURE"
    """A date field contains a value that cannot be parsed as a valid date."""

    MAPPING_NOT_FOUND      = "MAPPING_NOT_FOUND"
    """No approved mapping proposal exists for a required source column."""

    TRANSFORM_FAILURE      = "TRANSFORM_FAILURE"
    """A transform_fn expression raised an exception during evaluation."""

    BATCH_HARD_FAILURE     = "BATCH_HARD_FAILURE"
    """An unrecoverable error (e.g. empty CSV, parse error) that aborts the entire run."""


class IngestionRowError(Exception):
    """
    Raised inside row-level try/except blocks to signal a skippable row error.

    Attributes:
        code:    The IngestionErrorCode classifying this failure.
        message: Human-readable description (stored in skip_reason).
        row_data: The raw row dict captured before the failure (stored in raw_data JSONB).
    """

    def __init__(
        self,
        code: IngestionErrorCode,
        message: str,
        row_data: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code: IngestionErrorCode = code
        self.message: str = message
        self.row_data: dict = row_data or {}
