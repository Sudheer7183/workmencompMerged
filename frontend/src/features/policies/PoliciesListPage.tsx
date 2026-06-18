/**
 * PoliciesListPage — Phase 7 UX Remediation.
 *
 * Changes:
 *  - Reads initialFilters from React Router location.state (chart click-throughs)
 *  - Dynamic state options derived from current result set
 *  - State filter added to FilterBar
 *  - Uses useLabels() for filter labels
 *  - Audit Status column already present and confirmed working
 */

import React, { useMemo, useState, useEffect } from "react";
import axios from "axios";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/Controls";
import { NaIndicator } from "@/components/ui/NaIndicator";
import { RiskBadge } from "@/components/ui/Badges";
import { StatusBadge } from "@/components/ui/Badges";
import { AuditStatusBadge } from "@/components/ui/Badges";
import { RequestReportButton } from "@/features/reports/RequestReportButton";

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
  page: number;
  page_size: number;
}

/** Shape of filters passed via React Router location.state from chart clicks */
interface InitialFilters {
  status?: string;
  risk?: string;
  state?: string;
}

async function fetchPolicies(
  carrierId: number,
  page: number,
  pageSize: number,
  status: string,
  risk: string,
  state: string
): Promise<PolicyListResponse> {
  const params = new URLSearchParams({
    carrier_id: String(carrierId),
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) params.set("status", status);
  if (risk)   params.set("risk", risk);
  if (state)  params.set("state", state);

  const { data } = await axios.get<PolicyListResponse>(`/api/v1/policies?${params.toString()}`);
  return data;
}

const fmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });
const fmtDate = (d: string | null): string => (d ? fmt.format(new Date(d)) : "—");
const fmtCurrency = (v: number): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact" }).format(v);

export function PoliciesListPage(): React.JSX.Element {
  const label_policies = useLabels("policies");
  const label_reports  = useLabels("reports");
  const label_shared   = useLabels("shared");
  const navigate  = useNavigate();
  const location  = useLocation();
  const { carrierId } = useTenantCarrier();

  const [page, setPage]               = useState(1);
  const [search, setSearch]           = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter]     = useState("");
  const [stateFilter, setStateFilter]   = useState("");

  // Re-apply filters whenever React Router navigates to this page —
  // including re-navigations when the component is already mounted.
  useEffect(() => {
    const s = (location.state as InitialFilters | null) ?? {};
    setStatusFilter(s.status ?? "");
    setRiskFilter(s.risk   ?? "");
    setStateFilter(s.state  ?? "");
    setPage(1);
  }, [location.state]);

  const PAGE_SIZE = 25;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["policies-list", carrierId, page, statusFilter, riskFilter, stateFilter],
    queryFn: () => fetchPolicies(carrierId, page, PAGE_SIZE, statusFilter, riskFilter, stateFilter),
  });

  // Client-side text search (policy number / insured name)
  const filtered = search
    ? (data?.items ?? []).filter(
        (p) =>
          p.policy_number.toLowerCase().includes(search.toLowerCase()) ||
          p.insured_name.toLowerCase().includes(search.toLowerCase())
      )
    : (data?.items ?? []);

  // Derive unique state codes from current result set for dynamic filter options
  const dynamicStates = useMemo(
    () => [...new Set((data?.items ?? []).map((r) => r.state_code).filter(Boolean) as string[])].sort(),
    [data?.items]
  );

  const engineOn = filtered.some(
    (p) => p.variance_pct !== null || (p.est_premium !== null && p.est_premium > 0)
  );

  const columns: Column<PolicyListItem>[] = [
    {
      key: "policy_number",
      header: label_policies("col.policy_number", "Policy #"),
      sortable: true,
      render: (r) => (
        <span className="font-mono" style={{ fontSize: "12px", color: "var(--brand)" }}>
          {r.policy_number}
        </span>
      ),
    },
    { key: "insured_name",   header: label_policies("col.insured_name", "Insured"),        sortable: true,  render: (r) => r.insured_name },
    { key: "state_code",     header: label_policies("col.state", "State"),                render: (r) => r.state_code ?? "—" },
    { key: "effective_date", header: label_policies("col.effective_date", "Effective Date"), sortable: true, render: (r) => fmtDate(r.effective_date) },
    { key: "policy_status",  header: label_policies("col.status", "Status"),              render: (r) => <StatusBadge status={r.policy_status} /> },
    {
      key: "est_premium",
      header: label_policies("col.est_premium", "Est. Premium"),
      sortable: true,
      render: (r) => r.est_premium !== null ? <span className="font-mono">{fmtCurrency(r.est_premium)}</span> : "—",
    },
    {
      key: "variance_amount",
      header: label_policies("col.variance_amount", "Variance $"),
      sortable: true,
      render: (r) =>
        r.variance_amount !== null ? (
          <span className={`font-mono ${r.variance_amount > 0 ? "variance-positive" : r.variance_amount < 0 ? "variance-negative" : ""}`}>
            {fmtCurrency(r.variance_amount)}
          </span>
        ) : "—",
    },
    {
      key: "variance_pct",
      header: label_policies("col.variance_pct", "Variance %"),
      sortable: true,
      render: (r) => (
        <NaIndicator engineOn={engineOn} value={r.variance_pct} format="pct" className="font-mono" />
      ),
    },
    { key: "risk_level",   header: label_policies("col.risk_level", "Risk"),                   render: (r) => <RiskBadge risk={r.risk_level} /> },
    {
      key: "audit_status",
      header: label_policies("col_audit_status", label_policies("col.audit_status", "Audit Status")),
      render: (r) => <AuditStatusBadge status={r.audit_status} />,
    },
  ];

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <main className="page-content animate-fade-in">
      {/* ── Heading ──────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 700 }}>
          {label_policies("title", "Policies")}
        </h1>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {data && (
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
              {data.total} {label_policies("pagination.rows", "rows")}
            </span>
          )}
          <RequestReportButton
            carrierId={carrierId}
            reportType="book_summary"
            label={label_reports("btn.book_summary", "report_book_summary") ?? "Policy Book Summary"}
            data-testid="book-summary-btn"
          />
        </div>
      </div>

      {/* ── Engine-off notice ─────────────────────────────────────────────── */}
      {!engineOn && !isLoading && (data?.items.length ?? 0) > 0 && (
        <div
          className="error-banner"
          style={{
            marginBottom: "var(--space-4)",
            color: "var(--color-amber)",
            backgroundColor: "color-mix(in srgb, var(--color-amber) 10%, transparent)",
            borderColor: "color-mix(in srgb, var(--color-amber) 30%, transparent)",
          }}
        >
          {label_shared("engine_off_notice", "Calculation engine is off. Engine-derived fields show N/A.")}
        </div>
      )}

      {/* ── Filters ───────────────────────────────────────────────────────── */}
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by policy # or insured…"
        filters={[
          {
            value: statusFilter,
            onChange: (v) => { setStatusFilter(v); setPage(1); },
            placeholder: label_policies("filter.all_statuses", "All Statuses"),
            options: [
              { value: "Active",    label: label_policies("filter_status_label", "STATUS") === "STATUS" ? "Active"    : "Active"    },
              { value: "Cancelled", label: "Cancelled" },
            ],
          },
          {
            value: riskFilter,
            onChange: (v) => { setRiskFilter(v); setPage(1); },
            placeholder: label_policies("filter.all_risk", "All Risk Levels"),
            options: [
              { value: "High",   label: "High"   },
              { value: "Medium", label: "Medium" },
              { value: "Low",    label: "Low"    },
            ],
          },
          {
            value: stateFilter,
            onChange: (v) => { setStateFilter(v); setPage(1); },
            placeholder: `${label_policies("filter_state_label", "STATE")}: All`,
            options: dynamicStates.map((s) => ({ value: s, label: s })),
          },
        ]}
      />

      {/* ── Error ─────────────────────────────────────────────────────────── */}
      {isError && (
        <div className="error-banner" style={{ marginBottom: "var(--space-4)" }}>
          {label_shared("error_generic", "Something went wrong. Please try again.")}
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────────────── */}
      <DataTable
        columns={columns}
        rows={filtered}
        getRowKey={(r) => r.policy_id}
        loading={isLoading}
        emptyMessage={label_shared("no_data", "No data available.")}
        onRowClick={(r) => navigate(`/policies/${r.policy_id}?carrier_id=${carrierId}`)}
      />

      {/* ── Pagination ────────────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "var(--space-2)",
            marginTop: "var(--space-4)",
          }}
        >
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ‹ Prev
          </button>
          <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            {page} {label_policies("pagination.of", "of")} {totalPages}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next ›
          </button>
        </div>
      )}
    </main>
  );
}
