/**
 * DashboardPage — Phase 2.
 *
 * API calls use axios (configured in AuthContext with Authorization + X-Tenant-Slug
 * headers) so all requests are properly authenticated and tenant-scoped.
 * The Vite dev-server proxy forwards /api/* to the FastAPI backend at
 * http://backend:8000 — so relative URLs like /api/v1/... always resolve
 * correctly in both local dev and Docker Compose environments.
 */
import React from "react";
import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { KpiCard } from "@/components/ui/KpiCard";
import { TargetVarianceWidget } from "@/components/ui/Controls";
import { DonutChart } from "@/components/charts/Charts";
import { StackedBarChart } from "@/components/charts/Charts";

// ---------------------------------------------------------------------------
// API types
// ---------------------------------------------------------------------------

interface DashboardSummary {
  carrier_id: number;
  kpi: {
    total_book_premium: number;
    total_est_earned_premium: number;
    total_actual_earned_premium: number;
    total_variance_amount: number;
  };
  policy_status: { active_count: number; cancelled_count: number };
  risk_distribution: {
    high_count: number;
    medium_count: number;
    low_count: number;
    unassigned_count: number;
  };
  state_risk_profiles: Array<{
    state_code: string;
    high_count: number;
    medium_count: number;
    low_count: number;
  }>;
  target_variance: {
    policies_above_threshold: number;
    total_variance_above_threshold: number;
    threshold_pct: number;
  };
}

/**
 * Fetches dashboard summary via axios.
 *
 * axios.defaults.headers.common is populated by AuthContext immediately after
 * Keycloak authentication:
 *   Authorization: Bearer <jwt>
 *   X-Tenant-Slug:  <slug>   (required by TenantMiddleware on localhost)
 *
 * The relative URL /api/v1/dashboard/summary is proxied by Vite to the
 * FastAPI backend — it never hits the frontend origin.
 */
async function fetchDashboardSummary(carrierId: number): Promise<DashboardSummary> {
  const { data } = await axios.get<DashboardSummary>(
    `/api/v1/dashboard/summary?carrier_id=${carrierId}`
  );
  return data;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function fmtCurrency(v: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(v);
}

// ---------------------------------------------------------------------------
// DashboardPage
// ---------------------------------------------------------------------------

export function DashboardPage(): React.JSX.Element {
  const { carrierId } = useTenantCarrier();
  const labels = useLabels();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-summary", carrierId],
    queryFn: () => fetchDashboardSummary(carrierId),
    // Do not attempt to fetch when carrierId hasn't been resolved yet
    enabled: carrierId > 0,
  });

  if (isError) {
    return (
      <div className="page-content">
        <div className="error-banner">{labels.error_generic}</div>
      </div>
    );
  }

  const statusDonutData = [
    { name: labels.chart_active_policies,    value: data?.policy_status.active_count ?? 0,    color: "var(--color-green)" },
    { name: labels.chart_cancelled_policies, value: data?.policy_status.cancelled_count ?? 0, color: "var(--color-red)"   },
  ];

  const riskDonutData = [
    { name: labels.risk_high,       value: data?.risk_distribution.high_count ?? 0,       color: "var(--color-red)"   },
    { name: labels.risk_medium,     value: data?.risk_distribution.medium_count ?? 0,     color: "var(--color-amber)" },
    { name: labels.risk_low,        value: data?.risk_distribution.low_count ?? 0,        color: "var(--color-green)" },
    { name: labels.risk_unassigned, value: data?.risk_distribution.unassigned_count ?? 0, color: "var(--border)"      },
  ].filter((d) => d.value > 0);

  const totalPolicies =
    (data?.policy_status.active_count ?? 0) + (data?.policy_status.cancelled_count ?? 0);

  return (
    <main className="page-content animate-fade-in">
      {/* ── Page heading ──────────────────────────────────────────────────── */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 700 }}>{labels.dashboard_title}</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}>
          {labels.dashboard_subtitle}
        </p>
      </div>

      {/* ── 4 KPI cards ───────────────────────────────────────────────────── */}
      <div className="grid-4" style={{ marginBottom: "var(--space-6)" }}>
        <KpiCard
          label={labels.kpi_total_book_premium}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_book_premium)}
          accentColor="var(--brand)"
          loading={isLoading}
        />
        <KpiCard
          label={labels.kpi_total_est_earned}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_est_earned_premium)}
          loading={isLoading}
        />
        <KpiCard
          label={labels.kpi_total_actual_earned}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_actual_earned_premium)}
          loading={isLoading}
        />
        <KpiCard
          label={labels.kpi_total_variance}
          value={isLoading ? "…" : fmtCurrency(data!.kpi.total_variance_amount)}
          accentColor={
            (data?.kpi.total_variance_amount ?? 0) > 0
              ? "var(--color-red)"
              : "var(--color-green)"
          }
          loading={isLoading}
        />
      </div>

      {/* ── Target variance callout ────────────────────────────────────────── */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <TargetVarianceWidget
          policiesAbove={data?.target_variance.policies_above_threshold ?? 0}
          totalVarianceAbove={data?.target_variance.total_variance_above_threshold ?? 0}
          thresholdPct={data?.target_variance.threshold_pct ?? 30}
          loading={isLoading}
        />
      </div>

      {/* ── 2 donuts ──────────────────────────────────────────────────────── */}
      <div className="grid-2" style={{ marginBottom: "var(--space-6)" }}>
        <div className="card">
          <div className="section-title">{labels.chart_policy_status_title}</div>
          {isLoading ? (
            <div className="skeleton" style={{ height: "220px" }} />
          ) : (
            <DonutChart
              data={statusDonutData}
              innerLabel={String(totalPolicies)}
              innerSubLabel="Total"
            />
          )}
        </div>

        <div className="card">
          <div className="section-title">{labels.chart_risk_distribution_title}</div>
          {isLoading ? (
            <div className="skeleton" style={{ height: "220px" }} />
          ) : (
            <DonutChart
              data={riskDonutData}
              innerLabel={String(totalPolicies)}
              innerSubLabel="Policies"
            />
          )}
        </div>
      </div>

      {/* ── State & Risk bar chart ─────────────────────────────────────────── */}
      <div className="card">
        <div className="section-title">{labels.chart_state_risk_title}</div>
        {isLoading ? (
          <div className="skeleton" style={{ height: "240px" }} />
        ) : (data?.state_risk_profiles.length ?? 0) === 0 ? (
          <div className="empty-state">
            <span>No state data available yet.</span>
          </div>
        ) : (
          <StackedBarChart data={data!.state_risk_profiles} />
        )}
      </div>
    </main>
  );
}
