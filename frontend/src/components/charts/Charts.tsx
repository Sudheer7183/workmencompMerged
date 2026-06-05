import React from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

// ============================================================================
// DonutChart — wraps Recharts PieChart with a centred label
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
}

export function DonutChart({
  data,
  height = 220,
  innerLabel,
  innerSubLabel,
}: DonutChartProps): React.JSX.Element {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius="58%"
            outerRadius="80%"
            paddingAngle={2}
            dataKey="value"
            startAngle={90}
            endAngle={-270}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} stroke="none" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: "12px",
              color: "var(--text-primary)",
            }}
            formatter={(value: number, name: string) => [
              `${value} (${total > 0 ? ((value / total) * 100).toFixed(1) : 0}%)`,
              name,
            ]}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: "12px", color: "var(--text-muted)" }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Centre label */}
      {(innerLabel || innerSubLabel) && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            textAlign: "center",
            pointerEvents: "none",
            marginTop: "-14px", // offset for legend
          }}
        >
          {innerLabel && (
            <div
              className="font-mono"
              style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)" }}
            >
              {innerLabel}
            </div>
          )}
          {innerSubLabel && (
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              {innerSubLabel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// StackedBarChart — grouped bar chart for State & Risk
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
}

export function StackedBarChart({ data, height = 240 }: StackedBarChartProps): React.JSX.Element {
  const chartData = data.map((d) => ({
    name: d.state_code,
    High: d.high_count,
    Medium: d.medium_count,
    Low: d.low_count,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} barCategoryGap="30%">
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--border)"
          vertical={false}
        />
        <XAxis
          dataKey="name"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            fontSize: "12px",
            color: "var(--text-primary)",
          }}
          cursor={{ fill: "color-mix(in srgb, var(--border) 50%, transparent)" }}
        />
        <Legend
          iconType="square"
          iconSize={8}
          wrapperStyle={{ fontSize: "12px", color: "var(--text-muted)" }}
        />
        <Bar dataKey="High"   stackId="a" fill="var(--color-red)"   radius={[0,0,0,0]} />
        <Bar dataKey="Medium" stackId="a" fill="var(--color-amber)" radius={[0,0,0,0]} />
        <Bar dataKey="Low"    stackId="a" fill="var(--color-green)" radius={[4,4,0,0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
