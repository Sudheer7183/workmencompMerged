from __future__ import annotations

"""
text_utils — shared text normalisation helpers.

These were previously private (_normalise, _find_col) inside ingestion_service.py.
Phase 3 promotes them to a shared utility so AutoMappingService can reuse the
same logic without duplication.  ingestion_service.py now imports from here.
"""


def normalise(value: object) -> str:
    """
    Lowercase, strip whitespace and punctuation for fuzzy column matching.

    Examples:
      normalise("Policy Number")  -> "policy number"
      normalise("PolicyNumber")   -> "policynumber"
      normalise("POLICY NUMBER")  -> "policy number"
      normalise("  Est. Payroll") -> "est payroll"
    """
    if value is None:
        return ""
    return "".join(
        c for c in str(value).lower() if c.isalnum() or c == " "
    ).strip()


def find_col(mapping: dict[str, int], *aliases: str) -> int | None:
    """
    Returns the first column index (1-based) matching any alias.

    Uses substring matching in both directions so that "Policy Number"
    matches a normalised key of "policy number" and vice versa.
    """
    for alias in aliases:
        norm = normalise(alias)
        if norm in mapping:
            return mapping[norm]
        for key, idx in mapping.items():
            if norm in key or key in norm:
                return idx
    return None


def infer_type(sample_value: object) -> str:
    """
    Infers the canonical data type of a sample cell value.

    Returns one of: 'TEXT', 'NUMERIC', 'DATE', 'BOOLEAN', 'INTEGER'.
    Used by AutoMappingService for type-compatibility scoring.
    """
    from datetime import date, datetime
    from decimal import Decimal, InvalidOperation

    if sample_value is None:
        return "TEXT"

    # Already a date/datetime object (from openpyxl)
    if isinstance(sample_value, (date, datetime)):
        return "DATE"

    # Already a bool
    if isinstance(sample_value, bool):
        return "BOOLEAN"

    # Already an int
    if isinstance(sample_value, int):
        return "INTEGER"

    # Already a float/Decimal
    if isinstance(sample_value, (float, Decimal)):
        return "NUMERIC"

    s = str(sample_value).strip()

    # Boolean check
    if s.lower() in ("yes", "no", "true", "false", "y", "n"):
        return "BOOLEAN"

    # Date string check (common formats)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime as _dt
            _dt.strptime(s, fmt)
            return "DATE"
        except ValueError:
            pass

    # Numeric check (strip currency/comma)
    cleaned = s.replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        Decimal(cleaned)
        # Distinguish integer from decimal
        return "INTEGER" if "." not in cleaned else "NUMERIC"
    except InvalidOperation:
        pass

    return "TEXT"


# ---------------------------------------------------------------------------
# Type compatibility table — used by AutoMappingService Pass 3
# ---------------------------------------------------------------------------

_COMPATIBLE_TYPES: dict[str, frozenset[str]] = {
    "TEXT":    frozenset({"TEXT"}),
    "NUMERIC": frozenset({"NUMERIC", "INTEGER"}),
    "INTEGER": frozenset({"INTEGER", "NUMERIC"}),
    "DATE":    frozenset({"DATE"}),
    "BOOLEAN": frozenset({"BOOLEAN"}),
}


def types_are_compatible(inferred: str, canonical: str) -> bool:
    """
    Returns True when the inferred source type is compatible with the
    canonical target column type.

    NUMERIC ↔ INTEGER are considered compatible (widening is safe).
    All other cross-type pairings are incompatible.
    """
    return inferred in _COMPATIBLE_TYPES.get(canonical, frozenset())
