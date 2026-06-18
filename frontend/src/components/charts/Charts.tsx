// /**
//  * Charts — Phase 7 UX Remediation.
//  *
//  * DonutChart:    Recharts PieChart with custom ChartTooltip + click navigation.
//  * StackedBarChart: Recharts BarChart with custom ChartTooltip + StateMultiSelect filter.
//  *
//  * Clickthrough navigation: parent passes onNavigate callback.
//  * All strings via useLabels(). No style={{}} for colours.
//  */

// import React, { useMemo, useState } from "react";
// import {
//   Cell,
//   Legend,
//   Pie,
//   PieChart,
//   ResponsiveContainer,
//   Tooltip,
//   Bar,
//   BarChart,
//   CartesianGrid,
//   XAxis,
//   YAxis,
// } from "recharts";
// import { ChartTooltip } from "@/components/dashboard/ChartTooltip";
// import { StateMultiSelect } from "@/components/dashboard/StateMultiSelect";

// // ============================================================================
// // DonutChart — wraps Recharts PieChart with a centred label
// // ============================================================================

// interface DonutSlice {
//   name: string;
//   value: number;
//   color: string;
// }

// interface DonutChartProps {
//   data: DonutSlice[];
//   height?: number;
//   innerLabel?: string;
//   innerSubLabel?: string;
//   /** Optional: called when a slice is clicked. Receives the slice object. */
//   onSliceClick?: (slice: DonutSlice) => void;
// }

// export function DonutChart({
//   data,
//   height = 220,
//   innerLabel,
//   innerSubLabel,
//   onSliceClick,
// }: DonutChartProps): React.JSX.Element {
//   const total = useMemo(() => data.reduce((s, d) => s + d.value, 0), [data]);

//   return (
//     <div style={{ position: "relative", width: "100%", height }}>
//       <ResponsiveContainer width="100%" height="100%">
//         <PieChart>
//           <Pie
//             data={data}
//             cx="50%"
//             cy="50%"
//             innerRadius="58%"
//             outerRadius="80%"
//             paddingAngle={2}
//             dataKey="value"
//             startAngle={90}
//             endAngle={-270}
//             onClick={onSliceClick ? (entry) => onSliceClick(entry as DonutSlice) : undefined}
//             cursor={onSliceClick ? "pointer" : undefined}
//           >
//             {data.map((entry, i) => (
//               <Cell key={i} fill={entry.color} stroke="none" />
//             ))}
//           </Pie>
//           <Tooltip content={<ChartTooltip total={total} />} />
//           <Legend
//             iconType="circle"
//             iconSize={8}
//             wrapperStyle={{ fontSize: "12px", color: "var(--text-muted)" }}
//           />
//         </PieChart>
//       </ResponsiveContainer>

//       {/* Centre label */}
//       {(innerLabel || innerSubLabel) && (
//         <div
//           style={{
//             position: "absolute",
//             top: "50%",
//             left: "50%",
//             transform: "translate(-50%, -50%)",
//             textAlign: "center",
//             pointerEvents: "none",
//             marginTop: "-14px", // offset for legend
//           }}
//         >
//           {innerLabel && (
//             <div
//               className="font-mono"
//               style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)" }}
//             >
//               {innerLabel}
//             </div>
//           )}
//           {innerSubLabel && (
//             <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
//               {innerSubLabel}
//             </div>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }

// // ============================================================================
// // StackedBarChart — grouped bar chart for State & Risk with multi-select filter
// // ============================================================================

// interface StateRiskRow {
//   state_code: string;
//   high_count: number;
//   medium_count: number;
//   low_count: number;
// }

// interface StackedBarChartProps {
//   data: StateRiskRow[];
//   height?: number;
//   /** Optional: called when a bar segment is clicked. Receives { state, risk }. */
//   onBarClick?: (state: string, risk: string) => void;
// }

// export function StackedBarChart({
//   data,
//   height = 240,
//   onBarClick,
// }: StackedBarChartProps): React.JSX.Element {
//   // Derive sorted unique state codes from data
//   const allStateCodes = useMemo(
//     () => data.map((d) => d.state_code).sort(),
//     [data]
//   );

//   const [selectedStates, setSelectedStates] = useState<Set<string>>(
//     () => new Set(allStateCodes)
//   );

//   // Re-sync selection when data changes (e.g. initial load)
//   const prevAllRef = React.useRef<string>(allStateCodes.join(","));
//   if (prevAllRef.current !== allStateCodes.join(",")) {
//     prevAllRef.current = allStateCodes.join(",");
//     // Trigger sync on next render via side-effect free pattern
//   }

//   const filteredData = useMemo(
//     () => data.filter((d) => selectedStates.has(d.state_code)),
//     [data, selectedStates]
//   );

//   const chartData = filteredData.map((d) => ({
//     name: d.state_code,
//     High: d.high_count,
//     Medium: d.medium_count,
//     Low: d.low_count,
//   }));

//   const total = useMemo(
//     () => filteredData.reduce((s, d) => s + d.high_count + d.medium_count + d.low_count, 0),
//     [filteredData]
//   );

//   function handleBarClick(barData: Record<string, unknown>, risk: string): void {
//     if (!onBarClick) return;
//     // Recharts Bar onClick: first arg is the row data object ({ name, High, Medium, Low })
//     const stateName = barData?.name;
//     if (typeof stateName === "string" && stateName) {
//       onBarClick(stateName, risk);
//     }
//   }

//   return (
//     <div className="stacked-bar-chart">
//       {allStateCodes.length > 1 && (
//         <div className="stacked-bar-chart__filter">
//           <StateMultiSelect
//             options={allStateCodes}
//             selected={selectedStates.size > 0 ? selectedStates : new Set(allStateCodes)}
//             onChange={(next) => setSelectedStates(next)}
//           />
//         </div>
//       )}

//       <ResponsiveContainer width="100%" height={height}>
//         <BarChart data={chartData} barCategoryGap="30%">
//           <CartesianGrid
//             strokeDasharray="3 3"
//             stroke="var(--border)"
//             vertical={false}
//           />
//           <XAxis
//             dataKey="name"
//             tick={{ fill: "var(--text-muted)", fontSize: 11 }}
//             axisLine={false}
//             tickLine={false}
//           />
//           <YAxis
//             tick={{ fill: "var(--text-muted)", fontSize: 11 }}
//             axisLine={false}
//             tickLine={false}
//             allowDecimals={false}
//           />
//           <Tooltip content={<ChartTooltip total={total} />} />
//           <Legend
//             iconType="square"
//             iconSize={8}
//             wrapperStyle={{ fontSize: "12px", color: "var(--text-muted)" }}
//           />
//           <Bar
//             dataKey="High"
//             stackId="a"
//             fill="var(--color-red)"
//             radius={[0, 0, 0, 0]}
//             cursor={onBarClick ? "pointer" : undefined}
//             className={onBarClick ? "stacked-bar-chart__segment--clickable" : undefined}
//             onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "High")}
//           />
//           <Bar
//             dataKey="Medium"
//             stackId="a"
//             fill="var(--color-amber)"
//             radius={[0, 0, 0, 0]}
//             cursor={onBarClick ? "pointer" : undefined}
//             className={onBarClick ? "stacked-bar-chart__segment--clickable" : undefined}
//             onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "Medium")}
//           />
//           <Bar
//             dataKey="Low"
//             stackId="a"
//             fill="var(--color-green)"
//             radius={[4, 4, 0, 0]}
//             cursor={onBarClick ? "pointer" : undefined}
//             className={onBarClick ? "stacked-bar-chart__segment--clickable" : undefined}
//             onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "Low")}
//           />
//         </BarChart>
//       </ResponsiveContainer>
//     </div>
//   );
// }


/**
 * Charts — Phase 7 UX Remediation.
 *
 * DonutChart:      Recharts PieChart — large donut matching target design.
 * GroupedBarChart: Recharts BarChart — grouped (not stacked) bars per state,
 *                  matching the target design with separate bar per risk level.
 *
 * Clickthrough navigation: parent passes onNavigate callback.
 * All colours use CSS variables — no inline hex values.
 */

import React, { useMemo, useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip } from "@/components/dashboard/ChartTooltip";
import { StateMultiSelect } from "@/components/dashboard/StateMultiSelect";

// ============================================================================
// DonutChart — large centred donut matching target design
// ============================================================================

interface DonutSlice {
  name: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSlice[];
  height?: number;
  innerLabel?: string;
  innerSubLabel?: string;
  onSliceClick?: (slice: DonutSlice) => void;
}

export function DonutChart({
  data,
  height = 260,
  innerLabel,
  innerSubLabel,
  onSliceClick,
}: DonutChartProps): React.JSX.Element {
  const total = useMemo(() => data.reduce((s, d) => s + d.value, 0), [data]);

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="48%"
            innerRadius="52%"
            outerRadius="75%"
            paddingAngle={3}
            dataKey="value"
            startAngle={90}
            endAngle={-270}
            onClick={onSliceClick ? (entry) => onSliceClick(entry as DonutSlice) : undefined}
            cursor={onSliceClick ? "pointer" : undefined}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} stroke="none" />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip total={total} />} />
          <Legend
            iconType="circle"
            iconSize={10}
            wrapperStyle={{
              fontSize: "13px",
              color: "var(--text-muted)",
              paddingTop: "8px",
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Centre label — large bold number matching target */}
      {(innerLabel || innerSubLabel) && (
        <div
          style={{
            position: "absolute",
            top: "46%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          {innerLabel && (
            <div
              style={{
                fontSize: "32px",
                fontWeight: 800,
                lineHeight: 1,
                color: "var(--text-primary)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {innerLabel}
            </div>
          )}
          {innerSubLabel && (
            <div
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                marginTop: "4px",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {innerSubLabel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// GroupedBarChart — separate bar per risk level per state (target design)
// Previously this was a stacked bar chart. The target image shows grouped bars.
// ============================================================================

interface StateRiskRow {
  state_code: string;
  high_count: number;
  medium_count: number;
  low_count: number;
}

interface StackedBarChartProps {
  data: StateRiskRow[];
  height?: number;
  onBarClick?: (state: string, risk: string) => void;
}

// Keep export name StackedBarChart for backward-compatibility with DashboardPage
export function StackedBarChart({
  data,
  height = 280,
  onBarClick,
}: StackedBarChartProps): React.JSX.Element {
  const allStateCodes = useMemo(
    () => data.map((d) => d.state_code).sort(),
    [data]
  );

  const [selectedStates, setSelectedStates] = useState<Set<string>>(
    () => new Set(allStateCodes)
  );

  const prevAllRef = React.useRef<string>(allStateCodes.join(","));
  if (prevAllRef.current !== allStateCodes.join(",")) {
    prevAllRef.current = allStateCodes.join(",");
  }

  const filteredData = useMemo(
    () => data.filter((d) => selectedStates.has(d.state_code)),
    [data, selectedStates]
  );

  const chartData = filteredData.map((d) => ({
    name: d.state_code,
    High:   d.high_count,
    Medium: d.medium_count,
    Low:    d.low_count,
  }));

  const total = useMemo(
    () => filteredData.reduce((s, d) => s + d.high_count + d.medium_count + d.low_count, 0),
    [filteredData]
  );

  function handleBarClick(barData: Record<string, unknown>, risk: string): void {
    if (!onBarClick) return;
    const stateName = barData?.name;
    if (typeof stateName === "string" && stateName) {
      onBarClick(stateName, risk);
    }
  }

  return (
    <div className="stacked-bar-chart">
      {allStateCodes.length > 1 && (
        <div className="stacked-bar-chart__filter">
          <StateMultiSelect
            options={allStateCodes}
            selected={selectedStates.size > 0 ? selectedStates : new Set(allStateCodes)}
            onChange={(next) => setSelectedStates(next)}
          />
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        {/* barCategoryGap controls space between state groups;
            barGap controls space between bars within a group.
            NO stackId — each risk level is its own bar (grouped, not stacked). */}
        <BarChart data={chartData} barCategoryGap="28%" barGap={3}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border)"
            vertical={false}
          />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<ChartTooltip total={total} />} />
          <Legend
            iconType="square"
            iconSize={10}
            wrapperStyle={{ fontSize: "13px", color: "var(--text-muted)", paddingTop: "8px" }}
          />
          {/* High — red, leftmost bar in each group */}
          <Bar
            dataKey="High"
            fill="var(--color-red)"
            radius={[3, 3, 0, 0]}
            cursor={onBarClick ? "pointer" : undefined}
            onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "High")}
          />
          {/* Medium — amber, middle bar */}
          <Bar
            dataKey="Medium"
            fill="var(--color-amber)"
            radius={[3, 3, 0, 0]}
            cursor={onBarClick ? "pointer" : undefined}
            onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "Medium")}
          />
          {/* Low — green, rightmost bar */}
          <Bar
            dataKey="Low"
            fill="var(--color-green)"
            radius={[3, 3, 0, 0]}
            cursor={onBarClick ? "pointer" : undefined}
            onClick={(barData: Record<string, unknown>) => handleBarClick(barData, "Low")}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
