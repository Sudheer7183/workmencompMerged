/**
 * TenantsList — SUPER_ADMIN tenant management table.
 * V9 S12 — lists all tenants with status badge and actions.
 *
 * The backend GET /platform/tenants returns a plain array (list[TenantListItem]).
 * Fields: slug, name, tenant_type, status, schema_name.
 */

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

// ---------------------------------------------------------------------------
// Types — must exactly match the backend TenantListItem Pydantic schema.
// GET /platform/tenants → list[TenantListItem]
// ---------------------------------------------------------------------------
interface TenantListItem {
  slug: string;
  name: string;         // backend field name is "name", not "display_name"
  tenant_type: string;
  status: string;
  schema_name: string;
}

/**
 * Fetches the tenant list from the SUPER_ADMIN-only platform endpoint.
 * Returns a plain array — not a paginated object.
 * axios carries the Authorization header set by AuthContext.
 */
async function fetchTenants(statusFilter?: string): Promise<TenantListItem[]> {
  const params = statusFilter ? { status: statusFilter } : {};
  const { data } = await axios.get<TenantListItem[]>("/platform/tenants", { params });
  // Guard: if the backend ever wraps in a paginated object, extract items safely.
  // This makes the component resilient to future shape changes.
  if (Array.isArray(data)) return data;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const paginated = data as any;
  if (Array.isArray(paginated?.items)) return paginated.items as TenantListItem[];
  return [];
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "ACTIVE"
      ? "badge badge--active"
      : status === "PROVISIONING"
      ? "badge badge--provisioning"
      : "badge badge--draft";
  return <span className={cls}>{status}</span>;
}

export function TenantsList(): React.JSX.Element {
  const label_platform_admin = useLabels("platform_admin");
  const label_shared = useLabels("shared");
  const navigate = useNavigate();

const [showDeleted, setShowDeleted] = React.useState(false);

  const { data: tenants = [], isLoading, isError } = useQuery<TenantListItem[]>({
    queryKey: ["platform-tenants", showDeleted],
    queryFn: () => fetchTenants(showDeleted ? "DELETED" : undefined),
    staleTime: 30 * 1000,
  });
  return (
    <div className="tenants-list">
      <div className="tenants-list__header">
        <h1 className="tenants-list__title">{label_platform_admin("tenants.title", "Tenants")}</h1>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <button
            className={`btn ${showDeleted ? "btn--secondary" : "btn--ghost"}`}
            onClick={() => setShowDeleted((prev) => !prev)}
          >
            {showDeleted ? "Show Active" : "Show Deleted"}
          </button>
          <button
            className="btn btn--primary"
            onClick={() => navigate("/platform/tenants/new")}
          >
            {label_platform_admin("btn.new_tenant", "New Tenant")}
          </button>
        </div>
      </div>

      {isError && (
        <div className="error-banner" style={{ marginBottom: "var(--space-4)" }}>
          {label_shared("error_generic", "Something went wrong. Please try again.")}
        </div>
      )}

      {isLoading ? (
        <p className="tenants-list__loading">{label_shared("loading", "Loading…")}</p>
      ) : tenants.length === 0 ? (
        <div className="empty-state">
          <span>No tenants yet. Create one to get started.</span>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>{label_platform_admin("col.slug", "Slug")}</th>
              <th>{label_platform_admin("col.name", "Name")}</th>
              <th>{label_platform_admin("col.type", "Type")}</th>
              <th>{label_platform_admin("col.status", "Status")}</th>
              <th>{label_platform_admin("col.actions", "Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.slug} className="data-table__row">
                <td className="data-table__cell">
                  <code className="tenants-list__slug">{t.slug}</code>
                </td>
                <td className="data-table__cell">{t.name}</td>
                <td className="data-table__cell">{t.tenant_type}</td>
                <td className="data-table__cell">
                  <StatusBadge status={t.status} />
                </td>
                <td className="data-table__cell">
                  <Link
                    to={`/platform/tenants/${t.slug}`}
                    className="btn btn--sm btn--secondary"
                  >
                    {label_platform_admin("col.actions", "Actions")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
