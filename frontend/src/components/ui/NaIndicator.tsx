/**
 * NaIndicator — CRITICAL component
 *
 * Renders N/A when the calculation engine is off OR the value is null/undefined.
 * Renders the formatted value when both conditions are met.
 *
 * This enforces the invariant from V9 S7: engine-derived fields must never
 * show a stale or misleading value when the engine is off.
 *
 * Usage:
 *   <NaIndicator engineOn={engineOn} value={variancePct} format="pct" />
 *   <NaIndicator engineOn={engineOn} value={submissionRate} format="pct" />
 *   <NaIndicator engineOn={true} value={someAlwaysAvailableValue} format="currency" />
 */

import React from "react";
import { useLabels } from "@/hooks/useLabels";

export type NaIndicatorFormat = "currency" | "pct" | "number" | "raw";

interface NaIndicatorProps {
  /** Whether the calculation engine is on for this policy/carrier */
  engineOn: boolean;
  /** The engine-derived value — null when engine has not run */
  value: number | string | null | undefined;
  format?: NaIndicatorFormat;
  /** Override the N/A label text */
  naLabel?: string;
  className?: string;
}

function formatValue(value: number | string, format: NaIndicatorFormat): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return String(value);

  switch (format) {
    case "currency":
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(num);

    case "pct":
      // Value stored as decimal ratio (0.173 = 17.3%)
      return new Intl.NumberFormat("en-US", {
        style: "percent",
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }).format(num);

    case "number":
      return new Intl.NumberFormat("en-US").format(num);

    case "raw":
    default:
      return String(value);
  }
}

export function NaIndicator({
  engineOn,
  value,
  format = "raw",
  naLabel,
  className,
}: NaIndicatorProps): React.JSX.Element {
  const labels = useLabels();
  const displayNa = !engineOn || value === null || value === undefined;

  if (displayNa) {
    return (
      <span className={`na-value${className ? ` ${className}` : ""}`}>
        {naLabel ?? labels.na_label}
      </span>
    );
  }

  return (
    <span className={className}>
      {formatValue(value, format)}
    </span>
  );
}
