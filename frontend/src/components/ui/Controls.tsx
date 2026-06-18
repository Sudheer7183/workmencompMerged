import React from "react";

// ============================================================================
// FilterBar — dropdown filters + search input
// ============================================================================

interface FilterOption {
  value: string;
  label: string;
}

interface FilterBarProps {
  search?: string;
  onSearchChange?: (v: string) => void;
  searchPlaceholder?: string;
  filters?: Array<{
    value: string;
    onChange: (v: string) => void;
    options: FilterOption[];
    placeholder: string;
  }>;
  rightSlot?: React.ReactNode;
}

export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  filters = [],
  rightSlot,
}: FilterBarProps): React.JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        flexWrap: "wrap",
        marginBottom: "var(--space-4)",
      }}
    >
      {onSearchChange !== undefined && (
        <input
          className="input"
          style={{ maxWidth: "240px" }}
          type="search"
          placeholder={searchPlaceholder}
          value={search ?? ""}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      )}

      {filters.map((f, i) => (
        <select
          key={i}
          className="input select"
          style={{ maxWidth: "180px" }}
          value={f.value}
          onChange={(e) => f.onChange(e.target.value)}
        >
          <option value="">{f.placeholder}</option>
          {f.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ))}

      {rightSlot && <div style={{ marginLeft: "auto" }}>{rightSlot}</div>}
    </div>
  );
}

// ============================================================================
// Breadcrumb
// ============================================================================

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items }: BreadcrumbProps): React.JSX.Element {
  return (
    <nav
      aria-label="Breadcrumb"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-2)",
        fontSize: "13px",
        color: "var(--text-muted)",
        marginBottom: "var(--space-4)",
      }}
    >
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && (
            <span style={{ opacity: 0.5, fontSize: "11px" }}>›</span>
          )}
          {item.href ? (
            <a
              href={item.href}
              style={{ color: "var(--text-muted)", textDecoration: "none" }}
            >
              {item.label}
            </a>
          ) : (
            <span style={{ color: i === items.length - 1 ? "var(--text-primary)" : undefined }}>
              {item.label}
            </span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

// ============================================================================
// TenantLogo — renders logo image or fallback initials
// ============================================================================

interface TenantLogoProps {
  logoUrl?: string | null;
  tenantName?: string;
  size?: number;
}

export function TenantLogo({
  logoUrl,
  tenantName = "T",
  size = 32,
}: TenantLogoProps): React.JSX.Element {
  const initials = tenantName
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={tenantName}
        style={{
          width: size,
          height: size,
          objectFit: "contain",
          borderRadius: "var(--radius-sm)",
        }}
      />
    );
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "var(--radius-sm)",
        background: "var(--brand)",
        color: "var(--bg)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 700,
        fontSize: Math.round(size * 0.4),
        flexShrink: 0,
        fontFamily: "'DM Sans', sans-serif",
      }}
    >
      {initials}
    </div>
  );
}

// ============================================================================
// TargetVarianceWidget — 2-card callout on the Dashboard
// ============================================================================

interface TargetVarianceWidgetProps {
  policiesAbove: number;
  totalVarianceAbove: number;
  thresholdPct?: number;
  loading?: boolean;
}

export function TargetVarianceWidget({
  policiesAbove,
  totalVarianceAbove,
  thresholdPct = 30,
  loading = false,
}: TargetVarianceWidgetProps): React.JSX.Element {
  const formatCurrency = (v: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact" }).format(v);

  return (
    <div
      className="card"
      style={{
        borderColor: "color-mix(in srgb, var(--color-amber) 40%, var(--border))",
        borderLeft: "3px solid var(--color-amber)",
      }}
    >
      <div
        style={{
          fontSize: "11px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          color: "var(--color-amber)",
          marginBottom: "var(--space-3)",
        }}
      >
        Policies above {thresholdPct}% variance threshold
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-6)" }}>
        <div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
            Policies Above Threshold
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: "28px", width: "60px" }} />
          ) : (
            <div className="font-mono" style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-amber)" }}>
              {policiesAbove}
            </div>
          )}
        </div>

        <div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
            Total Variance Above
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: "28px", width: "100px" }} />
          ) : (
            <div className="font-mono" style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-red)" }}>
              {formatCurrency(totalVarianceAbove)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
