// /**
//  * DashboardPage — Phase 7 UX Remediation.
//  *
//  * Changes from Phase 2:
//  *  - DonutChart slices are clickable → navigate to /policies with pre-set filters
//  *  - StackedBarChart bars are clickable → navigate to /policies with state + risk filters
//  *  - DashboardPoliciesTable added below TargetVarianceWidget
//  *  - ViewAllButton label sourced from useLabels()
//  *  - All hardcoded label strings replaced with useLabels() consumption
//  */

// import React from "react";
// import axios from "axios";
// import { useNavigate } from "react-router-dom";
// import { useQuery } from "@tanstack/react-query";
// import { useTenantCarrier } from "@/context/TenantCarrierContext";
// import { useLabels } from "@/hooks/useLabels";
// import { KpiCard } from "@/components/ui/KpiCard";
// import { TargetVarianceWidget } from "@/components/ui/Controls";
// import { DonutChart } from "@/components/charts/Charts";
// import { StackedBarChart } from "@/components/charts/Charts";
// import { DashboardPoliciesTable } from "@/components/dashboard/DashboardPoliciesTable";

// // ---------------------------------------------------------------------------
// // API types
// // ---------------------------------------------------------------------------

// interface DashboardSummary {
//   carrier_id: number;
//   kpi: {
//     total_book_premium: number;
//     total_est_earned_premium: number;
//     total_actual_earned_premium: number;
//     total_variance_amount: number;
//   };
//   policy_status: { active_count: number; cancelled_count: number };
//   risk_distribution: {
//     high_count: number;
//     medium_count: number;
//     low_count: number;
//     unassigned_count: number;
//   };
//   state_risk_profiles: Array<{
//     state_code: string;
//     high_count: number;
//     medium_count: number;
//     low_count: number;
//   }>;
//   target_variance: {
//     policies_above_threshold: number;
//     total_variance_above_threshold: number;
//     threshold_pct: number;
//   };
// }

// async function fetchDashboardSummary(carrierId: number): Promise<DashboardSummary> {
//   const { data } = await axios.get<DashboardSummary>(
//     `/api/v1/dashboard/summary?carrier_id=${carrierId}`
//   );
//   return data;
// }

// // ---------------------------------------------------------------------------
// // Formatters
// // ---------------------------------------------------------------------------

// function fmtCurrency(v: number): string {
//   return new Intl.NumberFormat("en-US", {
//     style: "currency",
//     currency: "USD",
//     notation: "compact",
//     maximumFractionDigits: 1,
//   }).format(v);
// }

// // ---------------------------------------------------------------------------
// // DashboardPage
// // ---------------------------------------------------------------------------

// export function DashboardPage(): React.JSX.Element {
//   const { carrierId } = useTenantCarrier();
//   const label = useLabels("dashboard");
//   const label_shared = useLabels("shared");
//   const navigate = useNavigate();

//   const { data, isLoading, isError } = useQuery({
//     queryKey: ["dashboard-summary", carrierId],
//     queryFn: () => fetchDashboardSummary(carrierId),
//     enabled: carrierId > 0,
//   });

//   if (isError) {
//     return (
//       <div className="page-content">
//         <div className="error-banner">{label_shared("error_generic", "Something went wrong. Please try again.")}</div>
//       </div>
//     );
//   }

//   // ── Chart data ─────────────────────────────────────────────────────────────

//   const statusDonutData = [
//     { name: label("chart.active_policies", "Active"),    value: data?.policy_status.active_count ?? 0,    color: "var(--color-green)" },
//     { name: label("chart.cancelled_policies", "Cancelled"), value: data?.policy_status.cancelled_count ?? 0, color: "var(--color-red)"   },
//   ];

//   const riskDonutData = [
//     { name: label("risk.high", "High"),       value: data?.risk_distribution.high_count ?? 0,       color: "var(--color-red)"   },
//     { name: label("risk.medium", "Medium"),     value: data?.risk_distribution.medium_count ?? 0,     color: "var(--color-amber)" },
//     { name: label("risk.low", "Low"),        value: data?.risk_distribution.low_count ?? 0,        color: "var(--color-green)" },
//     { name: label("risk.unassigned", "Unassigned"), value: data?.risk_distribution.unassigned_count ?? 0, color: "var(--border)"      },
//   ].filter((d) => d.value > 0);

//   const totalPolicies =
//     (data?.policy_status.active_count ?? 0) + (data?.policy_status.cancelled_count ?? 0);

//   // ── Chart click handlers → navigate to /policies with pre-set filters ──────

//   function handleStatusSliceClick(slice: { name: string }): void {
//     // Map display name back to filter value
//     const statusMap: Record<string, string> = {
//       [label("chart.active_policies", "Active")]: "Active",
//       [label("chart.cancelled_policies", "Cancelled")]: "Cancelled",
//     };
//     const status = statusMap[slice.name] ?? slice.name;
//     navigate("/policies", { state: { status } });
//   }

//   function handleRiskSliceClick(slice: { name: string }): void {
//     const riskMap: Record<string, string> = {
//       [label("risk.high", "High")]: "High",
//       [label("risk.medium", "Medium")]: "Medium",
//       [label("risk.low", "Low")]: "Low",
//     };
//     const risk = riskMap[slice.name] ?? slice.name;
//     navigate("/policies", { state: { risk } });
//   }

//   function handleBarClick(state: string, risk: string): void {
//     navigate("/policies", { state: { state, risk } });
//   }

//   return (
//     <main className="page-content animate-fade-in">
//       {/* ── Page heading ──────────────────────────────────────────────────── */}
//       <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-6)" }}>
//         <div>
//           <h1 style={{ fontSize: "20px", fontWeight: 700 }}>
//             {label("title", "Audit Dashboard")}
//           </h1>
//           <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}>
//             {label("subtitle", "Workers Compensation Premium Audit Overview")}
//           </p>
//         </div>
//         <button
//           className="btn btn--secondary btn--sm"
//           type="button"
//           onClick={() => navigate("/policies")}
//           data-testid="btn-view-all-policies"
//         >
//           {label("btn_view_all_policies", "View All Policies →")}
//         </button>
//       </div>

//       {/* ── 4 KPI cards ───────────────────────────────────────────────────── */}
//       <div className="grid-4" style={{ marginBottom: "var(--space-6)" }}>
//         <KpiCard
//           label={label("kpi.book_premium", "Total Book Premium")}
//           value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_book_premium)}
//           accentColor="var(--brand)"
//           loading={isLoading}
//         />
//         <KpiCard
//           label={label("kpi.est_earned", "Est. Earned Premium")}
//           value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_est_earned_premium)}
//           loading={isLoading}
//         />
//         <KpiCard
//           label={label("kpi.actual_earned", "Actual Earned Premium")}
//           value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_actual_earned_premium)}
//           loading={isLoading}
//         />
//         <KpiCard
//           label={label("kpi.variance", "Total Variance")}
//           value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_variance_amount)}
//           accentColor={
//             (data?.kpi.total_variance_amount ?? 0) > 0
//               ? "var(--color-red)"
//               : "var(--color-green)"
//           }
//           loading={isLoading}
//         />
//       </div>

//       {/* ── Target variance callout ────────────────────────────────────────── */}
//       <div style={{ marginBottom: "var(--space-6)" }}>
//         <TargetVarianceWidget
//           policiesAbove={data?.target_variance.policies_above_threshold ?? 0}
//           totalVarianceAbove={data?.target_variance.total_variance_above_threshold ?? 0}
//           thresholdPct={data?.target_variance.threshold_pct ?? 30}
//           loading={isLoading}
//         />
//       </div>

//       {/* ── 2 donuts ──────────────────────────────────────────────────────── */}
//       <div className="grid-2" style={{ marginBottom: "var(--space-6)" }}>
//         <div className="card">
//           <div className="section-title">{label("chart.status_dist", "Policy Status")}</div>
//           {isLoading ? (
//             <div className="skeleton" style={{ height: "220px" }} />
//           ) : (
//             <DonutChart
//               data={statusDonutData}
//               innerLabel={String(totalPolicies)}
//               innerSubLabel="Total"
//               onSliceClick={handleStatusSliceClick}
//             />
//           )}
//         </div>

//         <div className="card">
//           <div className="section-title">{label("chart.risk_dist", "Risk Distribution")}</div>
//           {isLoading ? (
//             <div className="skeleton" style={{ height: "220px" }} />
//           ) : (
//             <DonutChart
//               data={riskDonutData}
//               innerLabel={String(totalPolicies)}
//               innerSubLabel="Policies"
//               onSliceClick={handleRiskSliceClick}
//             />
//           )}
//         </div>
//       </div>

//       {/* ── State & Risk bar chart ─────────────────────────────────────────── */}
//       <div className="card" style={{ marginBottom: "var(--space-6)" }}>
//         <div className="section-title">{label("chart.state_risk", "Policies by State & Risk")}</div>
//         {isLoading ? (
//           <div className="skeleton" style={{ height: "240px" }} />
//         ) : (data?.state_risk_profiles.length ?? 0) === 0 ? (
//           <div className="empty-state">
//             <span>No state data available yet.</span>
//           </div>
//         ) : (
//           <StackedBarChart
//             data={data?.state_risk_profiles ?? []}
//             onBarClick={handleBarClick}
//           />
//         )}
//       </div>

//       {/* ── Top 10 Policies snapshot ───────────────────────────────────────── */}
//       <div className="card">
//         <DashboardPoliciesTable carrierId={carrierId} />
//       </div>
//     </main>
//   );
// }


/**
 * DashboardPage — Phase 7 UX Remediation.
 *
 * Changes from Phase 2:
 *  - DonutChart slices are clickable → navigate to /policies with pre-set filters
 *  - StackedBarChart bars are clickable → navigate to /policies with state + risk filters
 *  - DashboardPoliciesTable added below TargetVarianceWidget
 *  - ViewAllButton label sourced from useLabels()
 *  - All hardcoded label strings replaced with useLabels() consumption
 */

/**
 * DashboardPage — Phase 7 UX Remediation.
 *
 * Changes from Phase 2:
 *  - DonutChart slices are clickable → navigate to /policies with pre-set filters
 *  - StackedBarChart bars are clickable → navigate to /policies with state + risk filters
 *  - DashboardPoliciesTable added below TargetVarianceWidget
 *  - ViewAllButton label sourced from useLabels()
 *  - All hardcoded label strings replaced with useLabels() consumption
 */

import React from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { KpiCard } from "@/components/ui/KpiCard";
import { TargetVarianceWidget } from "@/components/ui/Controls";
import { DonutChart } from "@/components/charts/Charts";
import { StackedBarChart } from "@/components/charts/Charts";
import { DashboardPoliciesTable } from "@/components/dashboard/DashboardPoliciesTable";

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
  const label = useLabels("dashboard");
  const label_shared = useLabels("shared");
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-summary", carrierId],
    queryFn: () => fetchDashboardSummary(carrierId),
    enabled: carrierId > 0,
  });

  if (isError) {
    return (
      <div className="page-content">
        <div className="error-banner">{label_shared("error_generic", "Something went wrong. Please try again.")}</div>
      </div>
    );
  }

  // ── Chart data ─────────────────────────────────────────────────────────────

  const statusDonutData = [
    { name: label("chart.active_policies", "Active"),    value: data?.policy_status.active_count ?? 0,    color: "var(--color-green)" },
    { name: label("chart.cancelled_policies", "Cancelled"), value: data?.policy_status.cancelled_count ?? 0, color: "var(--color-red)"   },
  ];

  const riskDonutData = [
    { name: label("risk.high", "High"),       value: data?.risk_distribution.high_count ?? 0,       color: "var(--color-red)"   },
    { name: label("risk.medium", "Medium"),     value: data?.risk_distribution.medium_count ?? 0,     color: "var(--color-amber)" },
    { name: label("risk.low", "Low"),        value: data?.risk_distribution.low_count ?? 0,        color: "var(--color-green)" },
    { name: label("risk.unassigned", "Unassigned"), value: data?.risk_distribution.unassigned_count ?? 0, color: "var(--border)"      },
  ].filter((d) => d.value > 0);

  const totalPolicies =
    (data?.policy_status.active_count ?? 0) + (data?.policy_status.cancelled_count ?? 0);

  // ── Chart click handlers → navigate to /policies with pre-set filters ──────

  function handleStatusSliceClick(slice: { name: string }): void {
    // Map display name back to filter value
    const statusMap: Record<string, string> = {
      [label("chart.active_policies", "Active")]: "Active",
      [label("chart.cancelled_policies", "Cancelled")]: "Cancelled",
    };
    const status = statusMap[slice.name] ?? slice.name;
    navigate("/policies", { state: { status } });
  }

  function handleRiskSliceClick(slice: { name: string }): void {
    const riskMap: Record<string, string> = {
      [label("risk.high", "High")]: "High",
      [label("risk.medium", "Medium")]: "Medium",
      [label("risk.low", "Low")]: "Low",
    };
    const risk = riskMap[slice.name] ?? slice.name;
    navigate("/policies", { state: { risk } });
  }

  function handleBarClick(state: string, risk: string): void {
    navigate("/policies", { state: { state, risk } });
  }

  return (
    <main className="page-content animate-fade-in">
      {/* ── Page heading ──────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-6)" }}>
        <div>
          <h1 style={{ fontSize: "20px", fontWeight: 700 }}>
            {label("title", "Audit Dashboard")}
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}>
            {label("subtitle", "Workers Compensation Premium Audit Overview")}
          </p>
        </div>
        <button
          className="btn btn--secondary btn--sm"
          type="button"
          onClick={() => navigate("/policies")}
          data-testid="btn-view-all-policies"
        >
          {label("btn_view_all_policies", "View All Policies →")}
        </button>
      </div>

      {/* ── 4 KPI cards ───────────────────────────────────────────────────── */}
      <div className="grid-4" style={{ marginBottom: "var(--space-6)" }}>
        <KpiCard
          label={label("kpi.book_premium", "Total Book Premium")}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_book_premium)}
          accentColor="var(--brand)"
          loading={isLoading}
        />
        <KpiCard
          label={label("kpi.est_earned", "Est. Earned Premium")}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_est_earned_premium)}
          loading={isLoading}
        />
        <KpiCard
          label={label("kpi.actual_earned", "Actual Earned Premium")}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_actual_earned_premium)}
          loading={isLoading}
        />
        <KpiCard
          label={label("kpi.variance", "Total Variance")}
          value={isLoading || !data ? "…" : fmtCurrency(data.kpi.total_variance_amount)}
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
          <div className="section-title" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "11px" }}>{label("chart.status_dist", "POLICY STATUS")}</div>
          {isLoading ? (
            <div className="skeleton" style={{ height: "260px" }} />
          ) : (
            <DonutChart
              data={statusDonutData}
              innerLabel={String(totalPolicies)}
              innerSubLabel="Total"
              onSliceClick={handleStatusSliceClick}
            />
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "11px" }}>{label("chart.risk_dist", "RISK DISTRIBUTION")}</div>
          {isLoading ? (
            <div className="skeleton" style={{ height: "260px" }} />
          ) : (
            <DonutChart
              data={riskDonutData}
              innerLabel={String(totalPolicies)}
              innerSubLabel="Policies"
              onSliceClick={handleRiskSliceClick}
            />
          )}
          {/* Risk rule descriptions — mirrors the legend in target design */}
          {!isLoading && (
            <div style={{ marginTop: "8px", fontSize: "12px", lineHeight: "1.7" }}>
              <span style={{ color: "var(--color-red)", fontWeight: 600 }}>
                {label("risk.high", "High")}
              </span>
              {/* <span style={{ color: "var(--text-muted)" }}>
                {" — "}{label("risk.high_desc", ">30% variance AND missing payrolls")}
              </span> */}
              <span style={{ color: "var(--text-muted)" }}>
                {" — "}
                {label(
                  "risk.high_desc",
                  `>${data?.target_variance.threshold_pct ?? 30}% variance AND missing payrolls`
                )}
              </span>
              <br />
              <span style={{ color: "var(--color-amber)", fontWeight: 600 }}>
                {label("risk.medium", "Medium")}
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                {" — "}{label("risk.medium_desc", "Either condition present")}
              </span>
              <br />
              <span style={{ color: "var(--color-green)", fontWeight: 600 }}>
                {label("risk.low", "Low")}
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                {" — "}{label("risk.low_desc", "Neither condition")}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── State & Risk bar chart ─────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <div className="section-title" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "11px" }}>{label("chart.state_risk", "POLICIES BY STATE & RISK")}</div>
        {isLoading ? (
          <div className="skeleton" style={{ height: "240px" }} />
        ) : (data?.state_risk_profiles.length ?? 0) === 0 ? (
          <div className="empty-state">
            <span>No state data available yet.</span>
          </div>
        ) : (
          <StackedBarChart
            data={data?.state_risk_profiles ?? []}
            onBarClick={handleBarClick}
          />
        )}
      </div>

      {/* ── Top 10 Policies snapshot ───────────────────────────────────────── */}
      <div className="card">
        <DashboardPoliciesTable carrierId={carrierId} />
      </div>
    </main>
  );
}