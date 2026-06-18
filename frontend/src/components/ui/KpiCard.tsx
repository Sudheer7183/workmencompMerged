import React from "react";

interface KpiCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  /** Optional accent colour from CSS variable name, e.g. "var(--brand)" */
  accentColor?: string;
  loading?: boolean;
}

export function KpiCard({
  label,
  value,
  subtext,
  accentColor,
  loading = false,
}: KpiCardProps): React.JSX.Element {
  return (
    <div
      className="card animate-fade-in"
      style={{
        borderTop: accentColor ? `2px solid ${accentColor}` : undefined,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.5px",
            color: "var(--text-muted)",
          }}
        >
          {label}
        </span>

        {loading ? (
          <div className="skeleton" style={{ height: "32px", width: "140px" }} />
        ) : (
          <span
            className="font-mono"
            style={{
              fontSize: "26px",
              fontWeight: 600,
              color: accentColor ?? "var(--text-primary)",
              lineHeight: 1.1,
            }}
          >
            {value}
          </span>
        )}

        {subtext && !loading && (
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{subtext}</span>
        )}
      </div>
    </div>
  );
}
