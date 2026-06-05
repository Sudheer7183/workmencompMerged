import React from "react";

// ============================================================================
// RiskBadge — High / Medium / Low / Unassigned
// ============================================================================

interface RiskBadgeProps {
  risk: string | null | undefined;
}

const RISK_CLASS: Record<string, string> = {
  High:   "badge badge-red",
  Medium: "badge badge-amber",
  Low:    "badge badge-green",
};

export function RiskBadge({ risk }: RiskBadgeProps): React.JSX.Element {
  if (!risk) return <span className="badge badge-muted">—</span>;
  return <span className={RISK_CLASS[risk] ?? "badge badge-muted"}>{risk}</span>;
}

// ============================================================================
// StatusBadge — Active / Cancelled
// ============================================================================

interface StatusBadgeProps {
  status: string | null | undefined;
}

export function StatusBadge({ status }: StatusBadgeProps): React.JSX.Element {
  if (!status) return <span className="badge badge-muted">—</span>;
  const cls = status === "Active" ? "badge badge-green" : "badge badge-red";
  return <span className={cls}>{status}</span>;
}

// ============================================================================
// AuditStatusBadge — Pending / In-Review / Complete
// ============================================================================

interface AuditStatusBadgeProps {
  status: string | null | undefined;
}

const AUDIT_CLASS: Record<string, string> = {
  Pending:    "badge badge-muted",
  "In-Review": "badge badge-amber",
  Complete:   "badge badge-green",
};

export function AuditStatusBadge({ status }: AuditStatusBadgeProps): React.JSX.Element {
  if (!status) return <span className="badge badge-muted">—</span>;
  return <span className={AUDIT_CLASS[status] ?? "badge badge-muted"}>{status}</span>;
}

// ============================================================================
// VarianceCard — single card showing amount + pct with colour coding
// ============================================================================

interface VarianceCardProps {
  label: string;
  amount: number | null | undefined;
  pct: number | null | undefined;
  engineOn: boolean;
}

function varianceClass(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "";
  if (amount > 0) return "variance-positive";
  if (amount < 0) return "variance-negative";
  return "variance-neutral";
}

export function VarianceCard({
  label,
  amount,
  pct,
  engineOn,
}: VarianceCardProps): React.JSX.Element {
  const colorClass = varianceClass(amount);

  const formatCurrency = (v: number): string =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(v);

  const formatPct = (v: number): string =>
    new Intl.NumberFormat("en-US", { style: "percent", minimumFractionDigits: 1 }).format(v);

  return (
    <div className="card-sm" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <span style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase",
                     letterSpacing: "0.5px", color: "var(--text-muted)" }}>
        {label}
      </span>
      <span className={`font-mono ${colorClass}`} style={{ fontSize: "18px", fontWeight: 600 }}>
        {amount !== null && amount !== undefined ? formatCurrency(amount) : <span className="na-value">N/A</span>}
      </span>
      <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
        {engineOn && pct !== null && pct !== undefined
          ? formatPct(pct)
          : <span className="na-value">N/A</span>}
      </span>
    </div>
  );
}

// ============================================================================
// PayrollPill — one of the 5 submission metrics pills
// ============================================================================

interface PayrollPillProps {
  label: string;
  value: number | string | null | undefined;
  engineOn: boolean;
  /** Set to true for always-available values (actual_received, zero_payroll_count) */
  alwaysAvailable?: boolean;
}

export function PayrollPill({
  label,
  value,
  engineOn,
  alwaysAvailable = false,
}: PayrollPillProps): React.JSX.Element {
  const showValue = alwaysAvailable || (engineOn && value !== null && value !== undefined);

  return (
    <div className="pill">
      <span className="pill-label">{label}</span>
      <span className="pill-value">
        {showValue && value !== null && value !== undefined
          ? String(value)
          : <span className="na-value" style={{ fontSize: "14px" }}>N/A</span>}
      </span>
    </div>
  );
}
