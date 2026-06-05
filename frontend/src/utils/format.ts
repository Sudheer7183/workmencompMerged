/**
 * Pure formatting utilities — deterministic in/out, no side effects.
 * All functions are explicitly typed; no `any` permitted.
 */

// ---------------------------------------------------------------------------
// Currency
// ---------------------------------------------------------------------------

const _currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const _currencyCompactFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function fmtCurrency(value: number): string {
  return _currencyFmt.format(value);
}

export function fmtCurrencyCompact(value: number): string {
  return _currencyCompactFmt.format(value);
}

// ---------------------------------------------------------------------------
// Percentage — value stored as decimal ratio (0.15 = 15%)
// ---------------------------------------------------------------------------

const _pctFmt = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function fmtPct(value: number): string {
  return _pctFmt.format(value);
}

/**
 * fmtSignedPct — returns "+12.3%", "-12.3%", or "0.0%".
 * Returns "N/A" for null/undefined inputs.
 * Used by VarianceCard and any field where the sign must be explicit.
 */
export function fmtSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  const formatted = _pctFmt.format(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return "0.0%";
}

// ---------------------------------------------------------------------------
// Signed currency — used for variance_amount display
// ---------------------------------------------------------------------------

export function fmtSignedCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  if (value > 0) return `+${fmtCurrency(value)}`;
  return fmtCurrency(value); // already has leading minus from Intl
}

// ---------------------------------------------------------------------------
// Date
// ---------------------------------------------------------------------------

const _dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return _dateFmt.format(new Date(value));
  } catch {
    return value;
  }
}

// ---------------------------------------------------------------------------
// Number
// ---------------------------------------------------------------------------

export function fmtNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

// ---------------------------------------------------------------------------
// Variance class helper — returns BEM modifier CSS class name
// ---------------------------------------------------------------------------

export type VarianceSign = "pos-val" | "neg-val" | "variance-neutral" | "";

export function varianceClass(
  amount: number | null | undefined
): VarianceSign {
  if (amount === null || amount === undefined) return "";
  if (amount > 0) return "pos-val";
  if (amount < 0) return "neg-val";
  return "variance-neutral";
}
