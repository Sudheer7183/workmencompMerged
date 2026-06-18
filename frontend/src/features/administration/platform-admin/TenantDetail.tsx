/**
 * TenantDetail — SUPER_ADMIN per-tenant view.
 * Phase 7B redesign: two-column Identity/Carriers grid, read-only carrier list,
 * danger-zone BEM block. No add/remove carrier buttons (managed by Tenant Admin).
 */

import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface CarrierAssignment {
  carrier_id: number;
  carrier_name: string;
  use_calculation_engine: boolean;
}

interface TenantDetailResponse {
  slug: string;
  name: string;
  display_name?: string;
  schema_name: string;
  tenant_type: string;
  status: string;
  platform_url?: string;
  created_at: string;
  carriers?: CarrierAssignment[];
}

interface UserRow {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
}

async function fetchTenant(slug: string): Promise<TenantDetailResponse> {
  const { data } = await axios.get<TenantDetailResponse>(`/platform/tenants/${slug}`);
  return data;
}

async function fetchTenantUsers(slug: string): Promise<UserRow[]> {
  try {
    const { data } = await axios.get<UserRow[]>(`/platform/tenants/${slug}/users`);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export function TenantDetail(): React.JSX.Element {
  const { slug } = useParams<{ slug: string }>();
  const label = useLabels("tenant_detail");
  const labelShared = useLabels("shared");

  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: tenant, isLoading } = useQuery<TenantDetailResponse>({
    queryKey: ["platform-tenant", slug],
    queryFn: () => fetchTenant(slug!),
    enabled: !!slug,
  });

  const { data: users = [] } = useQuery<UserRow[]>({
    queryKey: ["platform-tenant-users", slug],
    queryFn: () => fetchTenantUsers(slug!),
    enabled: !!slug,
  });

  const deactivateMutation = useMutation({
    mutationFn: () => axios.post(`/platform/tenants/${slug}/deactivate`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform-tenant", slug] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => axios.delete(`/platform/tenants/${slug}`),
    onSuccess: () => {
      navigate("/platform/tenants");
    },
  });

  if (isLoading) {
    return (
      <div className="detail-panel" >
        <p className="text-muted">{labelShared("loading", "Loading…")}</p>
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="detail-panel" >
        <p className="text-muted">Tenant not found.</p>
      </div>
    );
  }

  const displayName = tenant.display_name || tenant.name;
  const carriers: CarrierAssignment[] = tenant.carriers || [];

  return (
    <div className="detail-panel" data-testid="tenant-detail">
      {/* Back navigation */}
      <button
        className="detail-panel__back-link"
        onClick={() => navigate("/platform/tenants")}
        type="button"
      >
        {label("back_to_admin", "← Platform Admin")}
      </button>

      {/* Header */}
      <div className="detail-panel__header">
        <h1 className="detail-panel__title">
          {displayName}
          <span
            className={`status-badge status-badge--${
              tenant.status === "ACTIVE" ? "active" : "inactive"
            }`}
            className="detail-panel__header-badge"
          >
            {tenant.status}
          </span>
        </h1>
      </div>

      {/* Two-column: Identity + Carriers */}
      <div className="detail-panel__top-grid">
        {/* Identity */}
        <div className="detail-panel__section">
          <h3 className="detail-panel__section-title">
            {label("section_identity", "Identity")}
          </h3>
          <dl className="detail-panel__dl">
            <dt>{label("label_slug", "Slug")}</dt>
            <dd>{tenant.slug}</dd>
            <dt>{label("label_schema", "Schema")}</dt>
            <dd>{tenant.schema_name}</dd>
            <dt>{label("label_type", "Type")}</dt>
            <dd>{tenant.tenant_type}</dd>
            {tenant.platform_url && (
              <>
                <dt>{label("label_url", "URL")}</dt>
                <dd>
                  <a
                    href={tenant.platform_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="detail-panel__external-link"
                  >
                    {tenant.platform_url} ↗
                  </a>
                </dd>
              </>
            )}
          </dl>
        </div>

        {/* Carriers — read-only */}
        <div className="detail-panel__section">
          <h3 className="detail-panel__section-title">
            {label("section_carriers", "Assigned Carriers")}
          </h3>
          <p className="carrier-read-only-list__notice">
            {label(
              "carriers_managed_by_admin",
              "Carrier assignments are managed by the Tenant Administrator."
            )}
          </p>
          {carriers.length === 0 ? (
            <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
              No carriers assigned.
            </p>
          ) : (
            <ul className="carrier-read-only-list">
              {carriers.map((c) => (
                <li className="carrier-read-only-list__item" key={c.carrier_id}>
                  <span>{c.carrier_name}</span>
                  <span
                    className={`carrier-engine-badge carrier-engine-badge--${
                      c.use_calculation_engine ? "on" : "off"
                    }`}
                  >
                    {c.use_calculation_engine
                      ? label("carrier_engine_on", "Engine ON")
                      : label("carrier_engine_off", "Engine OFF")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Users table */}
      {users.length > 0 && (
        <div className="detail-panel__section">
          <h3 className="detail-panel__section-title">
            {label("section_users", "Users")} ({users.length})
          </h3>
          <table className="data-table">
            <thead>
              <tr>
                <th className="data-table__th">Name</th>
                <th className="data-table__th">Email</th>
                <th className="data-table__th">Role</th>
                <th className="data-table__th">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr className="data-table__row" key={u.id}>
                  <td className="data-table__cell">
                    {u.first_name} {u.last_name}
                  </td>
                  <td className="data-table__cell">{u.email}</td>
                  <td className="data-table__cell">{u.role}</td>
                  <td className="data-table__cell">
                    <span
                      className={`status-badge status-badge--${
                        u.is_active ? "active" : "inactive"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Danger Zone */}
      <div className="danger-zone">
        <h3 className="danger-zone__title">
          ⚠ {label("section_danger_zone", "Danger Zone")}
        </h3>
        <p className="danger-zone__description">
          These actions are irreversible. Proceed with caution.
        </p>
        <div className="danger-zone__actions">
          <button
            className="btn btn--danger btn--sm"
            onClick={() => {
              if (confirm("Deactivate this tenant?")) {
                deactivateMutation.mutate();
              }
            }}
            disabled={deactivateMutation.isPending || tenant.status !== "ACTIVE"}
            type="button"
          >
            {label("btn_deactivate_tenant", "Deactivate Tenant")}
          </button>
          <button
            className="btn btn--danger btn--sm"
            onClick={() => {
              if (confirm(`Permanently delete tenant "${displayName}"? This cannot be undone.`)) {
                deleteMutation.mutate();
              }
            }}
            disabled={deleteMutation.isPending}
            type="button"
          >
            {label("btn_delete_tenant", "Delete Tenant")}
          </button>
        </div>
      </div>
    </div>
  );
}
