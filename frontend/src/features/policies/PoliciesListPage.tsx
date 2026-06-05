import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/Controls";
import { NaIndicator } from "@/components/ui/NaIndicator";
import { RiskBadge } from "@/components/ui/Badges";
import { StatusBadge } from "@/components/ui/Badges";
import { AuditStatusBadge } from "@/components/ui/Badges";

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

async function fetchPolicies(
  carrierId: number,
  page: number,
  pageSize: number,
  status: string,
  risk: string
): Promise<PolicyListResponse> {
  const params = new URLSearchParams({
    carrier_id: String(carrierId),
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) params.set("status", status);
  if (risk) params.set("risk", risk);

  // axios carries Authorization + X-Tenant-Slug headers set by AuthContext.
  const { data } = await axios.get<PolicyListResponse>(
    `/api/v1/policies?${params.toString()}`
  );
  return data;
}

const fmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });
const fmtDate = (d: string | null) => (d ? fmt.format(new Date(d)) : "—");
const fmtCurrency = (v: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact" }).format(v);

export function PoliciesListPage(): React.JSX.Element {
  const labels = useLabels();
  const navigate = useNavigate();
  const { carrierId } = useTenantCarrier();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");

  const PAGE_SIZE = 25;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["policies-list", carrierId, page, statusFilter, riskFilter],
    queryFn: () => fetchPolicies(carrierId, page, PAGE_SIZE, statusFilter, riskFilter),
  });

  // Client-side search filter (policy number / insured name)
  const filtered = search
    ? (data?.items ?? []).filter(
        (p) =>
          p.policy_number.toLowerCase().includes(search.toLowerCase()) ||
          p.insured_name.toLowerCase().includes(search.toLowerCase())
      )
    : (data?.items ?? []);

  // Engine on = variance_pct is non-null for at least one row
  // Show engine-derived fields whenever we have premium data (est_premium > 0)
  // or variance data. Don't hide data just because variance_pct hasn't been
  // written by the calc engine yet — it's now computed on the fly by the API.
  const engineOn = filtered.some(
    (p) => p.variance_pct !== null || (p.est_premium !== null && p.est_premium > 0)
  );

  const columns: Column<PolicyListItem>[] = [
    {
      key: "policy_number",
      header: labels.col_policy_number,
      sortable: true,
      render: (r) => (
        <span className="font-mono" style={{ fontSize: "12px", color: "var(--brand)" }}>
          {r.policy_number}
        </span>
      ),
    },
    { key: "insured_name",   header: labels.col_insured_name,   sortable: true,  render: (r) => r.insured_name },
    { key: "state_code",     header: labels.col_state,          render: (r) => r.state_code ?? "—" },
    { key: "effective_date", header: labels.col_effective_date, sortable: true,  render: (r) => fmtDate(r.effective_date) },
    { key: "policy_status",  header: labels.col_policy_status,  render: (r) => <StatusBadge status={r.policy_status} /> },
    {
      key: "est_premium",
      header: labels.col_est_premium,
      sortable: true,
      render: (r) =>
        r.est_premium !== null ? (
          <span className="font-mono">{fmtCurrency(r.est_premium)}</span>
        ) : (
          "—"
        ),
    },
    {
      key: "variance_amount",
      header: labels.col_variance_amount,
      sortable: true,
      render: (r) =>
        r.variance_amount !== null ? (
          <span
            className={`font-mono ${r.variance_amount > 0 ? "variance-positive" : r.variance_amount < 0 ? "variance-negative" : ""}`}
          >
            {fmtCurrency(r.variance_amount)}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "variance_pct",
      header: labels.col_variance_pct,
      sortable: true,
      render: (r) => (
        <NaIndicator
          engineOn={engineOn}
          value={r.variance_pct}
          format="pct"
          className="font-mono"
        />
      ),
    },
    { key: "risk_level",   header: labels.col_risk_level,   render: (r) => <RiskBadge risk={r.risk_level} /> },
    { key: "audit_status", header: labels.col_audit_status, render: (r) => <AuditStatusBadge status={r.audit_status} /> },
  ];

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <main className="page-content animate-fade-in">
      {/* ── Heading ──────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 700 }}>{labels.policies_title}</h1>
        {data && (
          <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            {data.total} {labels.pagination_rows}
          </span>
        )}
      </div>

      {/* ── Engine-off notice ─────────────────────────────────────────────── */}
      {!engineOn && !isLoading && (data?.items.length ?? 0) > 0 && (
        <div className="error-banner" style={{ marginBottom: "var(--space-4)", color: "var(--color-amber)",
              backgroundColor: "color-mix(in srgb, var(--color-amber) 10%, transparent)",
              borderColor: "color-mix(in srgb, var(--color-amber) 30%, transparent)" }}>
          {labels.engine_off_notice}
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
            onChange: setStatusFilter,
            placeholder: labels.filter_all_statuses,
            options: [
              { value: "Active",    label: "Active"    },
              { value: "Cancelled", label: "Cancelled" },
            ],
          },
          {
            value: riskFilter,
            onChange: setRiskFilter,
            placeholder: labels.filter_all_risk,
            options: [
              { value: "High",   label: "High"   },
              { value: "Medium", label: "Medium" },
              { value: "Low",    label: "Low"    },
            ],
          },
        ]}
      />

      {/* ── Error ─────────────────────────────────────────────────────────── */}
      {isError && (
        <div className="error-banner" style={{ marginBottom: "var(--space-4)" }}>
          {labels.error_generic}
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────────────── */}
      <DataTable
        columns={columns}
        rows={filtered}
        getRowKey={(r) => r.policy_id}
        loading={isLoading}
        emptyMessage={labels.no_data}
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
            {page} {labels.pagination_of} {totalPages}
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