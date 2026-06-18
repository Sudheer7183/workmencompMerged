/**
 * ChartTooltip — Shared Recharts tooltip component.
 *
 * Used as the `content` prop on all three dashboard charts.
 * Shows the dimension label, raw count, and percentage of total.
 *
 * No style={{}} for colours — all via BEM classes and CSS custom properties.
 */

import React from "react";
import { useLabels } from "@/hooks/useLabels";

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color?: string;
}

interface ChartTooltipProps {
  /** Recharts injects these when used as a content prop */
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  /** Sum of all values in the dataset — computed in the parent */
  total: number;
}

export function ChartTooltip({
  active,
  payload,
  label,
  total,
}: ChartTooltipProps): React.JSX.Element | null {
  const labelFn = useLabels("dashboard");

  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="chart-tooltip" role="tooltip">
      <div className="chart-tooltip__label">{label ?? payload[0]?.name}</div>
      {payload.map((entry, i) => {
        const pct = total > 0 ? ((entry.value / total) * 100).toFixed(1) : "0.0";
        return (
          <div key={i} className="chart-tooltip__row">
            {payload.length > 1 && (
              <span
                className="chart-tooltip__swatch"
                style={{ backgroundColor: entry.color }}
              />
            )}
            <span className="chart-tooltip__name">{entry.name}</span>
            <span className="chart-tooltip__value">
              {entry.value.toLocaleString()} — {pct}
              {labelFn("chart_tooltip_pct_of_total", "% of total")}
            </span>
          </div>
        );
      })}
    </div>
  );
}
