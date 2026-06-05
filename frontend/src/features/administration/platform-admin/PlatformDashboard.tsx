/**
 * PlatformDashboard — SUPER_ADMIN landing page.
 *
 * Displays 4 summary cards (Active Tenants, Carriers, Users, Pairs)
 * and navigation links to Tenants list and Carriers list.
 * V9 S12 — Platform Admin Dashboard.
 */

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface PlatformStats {
  active_tenant_count: number;
  total_carrier_count: number;
  total_user_count: number;
  tenant_carrier_pair_count: number;
}

async function fetchPlatformStats(): Promise<PlatformStats> {
  const [tenantsRes, carriersRes, usersRes] = await Promise.all([
    axios.get<{ items?: unknown[]; length?: number }>("/platform/tenants"),
    axios.get<unknown[]>("/platform/carriers"),
    axios.get<unknown[]>("/platform/users"),
  ]);
  const tenants = Array.isArray(tenantsRes.data) ? tenantsRes.data : [];
  const carriers = Array.isArray(carriersRes.data) ? carriersRes.data : [];
  const users = Array.isArray(usersRes.data) ? usersRes.data : [];
  return {
    active_tenant_count: tenants.length,
    total_carrier_count: carriers.length,
    total_user_count: users.length,
    tenant_carrier_pair_count: 0, // computed server-side in later phase
  };
}

function StatCard({
  label,
  value,
  to,
}: {
  label: string;
  value: number | string;
  to?: string;
}) {
  const inner = (
    <div className="platform-stat-card">
      <div className="platform-stat-card__value">{value}</div>
      <div className="platform-stat-card__label">{label}</div>
    </div>
  );
  return to ? <Link to={to} className="platform-stat-card__link">{inner}</Link> : inner;
}

export function PlatformDashboard(): React.JSX.Element {
  const labels = useLabels();
  const { data: stats, isLoading } = useQuery<PlatformStats>({
    queryKey: ["platform-stats"],
    queryFn: fetchPlatformStats,
    staleTime: 60 * 1000,
  });

  return (
    <div className="platform-dashboard">
      <h1 className="platform-dashboard__title">{labels.platform_dashboard_title}</h1>

      <div className="platform-dashboard__stats">
        <StatCard
          label={labels.platform_stat_active_tenants}
          value={isLoading ? "…" : (stats?.active_tenant_count ?? 0)}
          to="/platform/tenants"
        />
        <StatCard
          label={labels.platform_stat_total_carriers}
          value={isLoading ? "…" : (stats?.total_carrier_count ?? 0)}
          to="/platform/carriers"
        />
        <StatCard
          label={labels.platform_stat_total_users}
          value={isLoading ? "…" : (stats?.total_user_count ?? 0)}
        />
        <StatCard
          label={labels.platform_stat_tenant_carrier_pairs}
          value={isLoading ? "…" : (stats?.tenant_carrier_pair_count ?? 0)}
        />
      </div>

      <div className="platform-dashboard__actions">
        <Link to="/platform/tenants" className="btn btn--primary">
          {labels.platform_tenants_title}
        </Link>
        <Link to="/platform/carriers" className="btn btn--secondary">
          {labels.platform_carriers_title}
        </Link>
      </div>
    </div>
  );
}
