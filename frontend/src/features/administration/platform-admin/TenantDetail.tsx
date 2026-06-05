/**
 * TenantDetail — SUPER_ADMIN per-tenant view.
 * V9 S12.3 — identity card, assigned carriers, tenant users, danger zone.
 */

import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface TenantDetailResponse {
  slug: string;
  display_name: string;
  schema_name: string;
  tenant_type: string;
  status: string;
  created_at: string;
}

async function fetchTenant(slug: string): Promise<TenantDetailResponse> {
  const { data } = await axios.get<TenantDetailResponse>(`/platform/tenants/${slug}`);
  return data;
}

export function TenantDetail(): React.JSX.Element {
  const { slug } = useParams<{ slug: string }>();
  const labels = useLabels();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: tenant, isLoading } = useQuery<TenantDetailResponse>({
    queryKey: ["platform-tenant", slug],
    queryFn: () => fetchTenant(slug!),
    enabled: !!slug,
  });

  const activateMutation = useMutation({
    mutationFn: () => axios.post(`/platform/tenants/${slug}/activate`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform-tenant", slug] });
      void qc.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => axios.delete(`/platform/tenants/${slug}`),
    onSuccess: () => {
      navigate("/platform/tenants");
    },
  });
  const suspendMutation = useMutation({
    mutationFn: () => axios.post(`/platform/tenants/${slug}/suspend`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform-tenant", slug] });
      void qc.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
  });
  if (isLoading) return <p>{labels.loading}</p>;
  if (!tenant) return <p>{labels.error_generic}</p>;

  return (
    <div className="tenant-detail">
      <div className="tenant-detail__header">
        <h1 className="tenant-detail__title">{tenant.display_name}</h1>
        <span className="tenant-detail__slug">{tenant.slug}</span>
      </div>

      <section className="tenant-detail__section">
        <dl className="tenant-detail__meta">
          <dt>{labels.platform_col_type}</dt>
          <dd>{tenant.tenant_type}</dd>
          <dt>{labels.platform_col_status}</dt>
          <dd>{tenant.status}</dd>
          <dt>Schema</dt>
          <dd><code>{tenant.schema_name}</code></dd>
          <dt>Created</dt>
          <dd>{new Date(tenant.created_at).toLocaleDateString()}</dd>
        </dl>
      </section>

      <div className="tenant-detail__actions">
        {(tenant.status === "DRAFT" || tenant.status === "SUSPENDED" || tenant.status === "PROVISIONING") && (
          <button
            className="btn btn--primary"
            onClick={() => activateMutation.mutate()}
            disabled={activateMutation.isPending}
          >
            {labels.platform_btn_activate}
          </button>
        )}
        {tenant.status === "ACTIVE" && (
          <button
            className="btn btn--secondary"
            onClick={() => {
              if (window.confirm(`Suspend tenant ${tenant.slug}?`)) {
                suspendMutation.mutate();
              }
            }}
            disabled={suspendMutation.isPending}
          >
            Suspend Tenant
          </button>
        )}
      </div>

      <section className="tenant-detail__danger-zone">
        <h2 className="tenant-detail__danger-title">Danger Zone</h2>
        <button
          className="btn btn--danger"
          onClick={() => {
            if (window.confirm(`Delete tenant ${tenant.slug}?`)) {
              deleteMutation.mutate();
            }
          }}
          disabled={deleteMutation.isPending}
        >
          Delete Tenant
        </button>
      </section>
    </div>
  );
}
