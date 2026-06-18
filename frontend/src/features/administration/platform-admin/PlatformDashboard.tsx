/**
 * PlatformDashboard — SUPER_ADMIN landing page.
 * Phase 7B redesign: stat cards + searchable/filterable tenant table.
 */

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { KpiCard } from "@/components/ui/KpiCard";

interface TenantRow {
  slug: string;
  name: string;
  tenant_type: string;
  status: string;
  carrier_count?: number;
}

interface PlatformStats {
  active_tenant_count: number;
  total_carrier_count: number;
  total_user_count: number;
  tenant_carrier_pair_count: number;
}

async function fetchTenants(): Promise<TenantRow[]> {
  const res = await axios.get<TenantRow[]>("/platform/tenants");
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchPlatformStats(): Promise<PlatformStats> {
  const [tenantsRes, carriersRes, usersRes] = await Promise.all([
    axios.get<TenantRow[]>("/platform/tenants"),
    axios.get<unknown[]>("/platform/carriers"),
    axios.get<unknown[]>("/platform/users"),
  ]);
  const tenants = Array.isArray(tenantsRes.data) ? tenantsRes.data : [];
  const carriers = Array.isArray(carriersRes.data) ? carriersRes.data : [];
  const users = Array.isArray(usersRes.data) ? usersRes.data : [];
  return {
    active_tenant_count: tenants.filter((t) => t.status === "ACTIVE").length,
    total_carrier_count: carriers.length,
    total_user_count: users.length,
    tenant_carrier_pair_count: 0,
  };
}

export function PlatformDashboard(): React.JSX.Element {
  const label = useLabels("platform_admin");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data: stats, isLoading: statsLoading } = useQuery<PlatformStats>({
    queryKey: ["platform-stats"],
    queryFn: fetchPlatformStats,
    staleTime: 60 * 1000,
  });

  const { data: tenants = [], isLoading: tenantsLoading } = useQuery<TenantRow[]>({
    queryKey: ["platform-tenants"],
    queryFn: fetchTenants,
    staleTime: 60 * 1000,
  });

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return tenants.filter((t) => {
      const matchesSearch =
        !q ||
        t.name.toLowerCase().includes(q) ||
        t.slug.toLowerCase().includes(q) ||
        (t.tenant_type || "").toLowerCase().includes(q);
      const matchesStatus =
        statusFilter === "ALL" || t.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [tenants, search, statusFilter]);

  const loading = statsLoading || tenantsLoading;

  return (
    <div className="platform-admin">
      {/* Header */}
      <div className="platform-admin__header">
        <h1 className="platform-admin__title">
          {label("title", "Platform Administration")}
        </h1>
        <Link to="/platform/tenants/new" className="btn btn--primary btn--sm">
          {label("btn_new_tenant", "+ New Tenant")}
        </Link>
      </div>

      {/* Stat cards */}
      <div className="platform-admin__stat-grid">
        <KpiCard
          label={label("stat_tenants", "Tenants")}
          value={loading ? "…" : String(stats?.active_tenant_count ?? 0)}
          subtext={label("stat_tenants_sub", "Active")}
        />
        <KpiCard
          label={label("stat_carriers", "Carriers")}
          value={loading ? "…" : String(stats?.total_carrier_count ?? 0)}
          subtext={label("stat_carriers_sub", "Platform")}
        />
        <KpiCard
          label={label("stat_users", "Total Users")}
          value={loading ? "…" : String(stats?.total_user_count ?? 0)}
          subtext={label("stat_users_sub", "Across all tenants")}
        />
        <KpiCard
          label={label("stat_tc_pairs", "Active TC Pairs")}
          value={loading ? "…" : String(stats?.tenant_carrier_pair_count ?? 0)}
          subtext={label("stat_tc_pairs_sub", "Tenant-Carrier")}
        />
      </div>

      {/* Tenant table */}
      <div>
        <p className="platform-admin__section-title">
          {label("tenants.title", "Tenants")}
        </p>

        {/* Search + filter toolbar */}
        <div className="platform-admin__table-toolbar" style={{ marginBottom: "var(--space-3)" }}>
          <input
            className="input platform-admin__search"
            type="search"
            placeholder={label("search_placeholder", "Search tenants…")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="tenant-search"
          />
          <select
            className="select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            data-testid="status-filter"
          >
            <option value="ALL">{label("filter_status_all", "All Statuses")}</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="PROVISIONING">PROVISIONING</option>
            <option value="INACTIVE">INACTIVE</option>
          </select>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th className="data-table__th">{label("table_col_name", "Name")}</th>
              <th className="data-table__th">{label("table_col_type", "Type")}</th>
              <th className="data-table__th">{label("table_col_status", "Status")}</th>
              <th className="data-table__th">{label("table_col_carriers", "Carriers")}</th>
              <th className="data-table__th">{label("table_col_actions", "Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {tenantsLoading ? (
              <tr>
                <td className="data-table__cell" colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                  Loading…
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td className="data-table__cell" colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                  No tenants found.
                </td>
              </tr>
            ) : (
              filtered.map((tenant) => (
                <tr className="data-table__row" key={tenant.slug}>
                  <td className="data-table__cell">
                    <span style={{ fontWeight: 600 }}>{tenant.name}</span>
                    <br />
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                      {tenant.slug}
                    </span>
                  </td>
                  <td className="data-table__cell">{tenant.tenant_type}</td>
                  <td className="data-table__cell">
                    <span
                      className={`status-badge status-badge--${
                        tenant.status === "ACTIVE" ? "active" : "inactive"
                      }`}
                    >
                      {tenant.status}
                    </span>
                  </td>
                  <td className="data-table__cell">
                    {tenant.carrier_count ?? "—"}
                  </td>
                  <td className="data-table__cell">
                    <Link
                      to={`/platform/tenants/${tenant.slug}`}
                      className="btn btn--ghost btn--sm"
                    >
                      {label("action_view", "View")}
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
