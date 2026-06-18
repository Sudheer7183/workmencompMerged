/**
 * DashboardPoliciesTable — Top-10 policy snapshot table on the Dashboard page.
 *
 * Fetches the top 10 policies by variance amount (descending).
 * Reuses column rendering patterns from PoliciesListPage.
 * No filter bar, search, or pagination — this is a quick summary.
 */

import React from "react";
import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { RiskBadge } from "@/components/ui/Badges";
import { StatusBadge } from "@/components/ui/Badges";
import { AuditStatusBadge } from "@/components/ui/Badges";
import { NaIndicator } from "@/components/ui/NaIndicator";

interface PolicyListItem {
  policy_id: number;
  policy_number: string;
  insured_name: string;
  state_code: string | null;
  effective_date: string | null;
  policy_status: string;
  est_premium: number | null;
  variance_amount: number | null;
  variance_pct: number | null;
  risk_level: string | null;
  audit_status: string;
}

interface PolicyListResponse {
  items: PolicyListItem[];
  total: number;
}

interface DashboardPoliciesTableProps {
  carrierId: number;
}

const fmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });
const fmtDate = (d: string | null): string => (d ? fmt.format(new Date(d)) : "—");
const fmtCurrency = (v: number): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact" }).format(v);

async function fetchTopPolicies(carrierId: number): Promise<PolicyListResponse> {
  const { data } = await axios.get<PolicyListResponse>(
    `/api/v1/policies?carrier_id=${carrierId}&page=1&page_size=10&sort_by=variance_amount&sort_order=desc`
  );
  return data;
}

export function DashboardPoliciesTable({
  carrierId,
}: DashboardPoliciesTableProps): React.JSX.Element {
  const labelDash = useLabels("dashboard");
  const labelShared = useLabels("shared");
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-policies-top10", carrierId],
    queryFn: () => fetchTopPolicies(carrierId),
    enabled: carrierId > 0,
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const engineOn = items.some((p) => p.variance_pct !== null || (p.est_premium !== null && p.est_premium > 0));

  return (
    <section className="dashboard-policies-table" data-testid="dashboard-policies-table">
      <div className="dashboard-policies-table__header">
        <h2 className="dashboard-policies-table__title">
          {labelDash("section_all_policies", "All Policies")}
        </h2>
      </div>

      {isError && (
        <div className="error-banner">
          {labelShared("error_generic", "Something went wrong. Please try again.")}
        </div>
      )}

      {isLoading ? (
        <div className="skeleton" style={{ height: "200px" }} />
      ) : (
        <div className="dashboard-policies-table__scroll">
          <table className="data-table" data-testid="top-policies-table">
            <thead>
              <tr className="data-table__header-row">
                <th className="data-table__th">Policy #</th>
                <th className="data-table__th">Insured</th>
                <th className="data-table__th">State</th>
                <th className="data-table__th">Effective</th>
                <th className="data-table__th">Status</th>
                <th className="data-table__th">Est. Premium</th>
                <th className="data-table__th">Variance $</th>
                <th className="data-table__th">Variance %</th>
                <th className="data-table__th">Risk</th>
                <th className="data-table__th">
                  {labelDash("table_col_audit_status", "Audit Status")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="data-table__empty">
                    {labelShared("no_data", "No data available.")}
                  </td>
                </tr>
              ) : (
                items.map((p) => (
                  <tr
                    key={p.policy_id}
                    className="data-table__row data-table__row--clickable"
                    onClick={() =>
                      navigate(`/policies/${p.policy_id}?carrier_id=${carrierId}`)
                    }
                  >
                    <td className="data-table__td">
                      <span className="font-mono" style={{ fontSize: "12px", color: "var(--brand)" }}>
                        {p.policy_number}
                      </span>
                    </td>
                    <td className="data-table__td">{p.insured_name}</td>
                    <td className="data-table__td">{p.state_code ?? "—"}</td>
                    <td className="data-table__td">{fmtDate(p.effective_date)}</td>
                    <td className="data-table__td">
                      <StatusBadge status={p.policy_status} />
                    </td>
                    <td className="data-table__td font-mono">
                      {p.est_premium !== null ? fmtCurrency(p.est_premium) : "—"}
                    </td>
                    <td className="data-table__td font-mono">
                      {p.variance_amount !== null ? (
                        <span
                          className={
                            p.variance_amount > 0
                              ? "variance-positive"
                              : p.variance_amount < 0
                              ? "variance-negative"
                              : ""
                          }
                        >
                          {fmtCurrency(p.variance_amount)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="data-table__td">
                      <NaIndicator
                        engineOn={engineOn}
                        value={p.variance_pct}
                        format="pct"
                        className="font-mono"
                      />
                    </td>
                    <td className="data-table__td">
                      <RiskBadge risk={p.risk_level} />
                    </td>
                    <td className="data-table__td">
                      <AuditStatusBadge status={p.audit_status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="dashboard-policies-table__footer">
        <button
          className="btn btn--ghost btn--sm"
          type="button"
          onClick={() => navigate("/policies")}
          data-testid="btn-view-all-policies"
        >
          {labelDash("table_view_all_link", "View all policies →")}
        </button>
      </div>
    </section>
  );
}
