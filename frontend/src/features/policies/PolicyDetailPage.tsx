import React, { useState } from "react";
import axios from "axios";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { Breadcrumb } from "@/components/ui/Controls";
import { NaIndicator } from "@/components/ui/NaIndicator";
import { RiskBadge, AuditStatusBadge, PayrollPill } from "@/components/ui/Badges";

// ---------------------------------------------------------------------------
// API fetch helpers
//
// axios carries Authorization + X-Tenant-Slug headers set by AuthContext.
// Relative URLs are proxied by Vite to the FastAPI backend.
// ---------------------------------------------------------------------------

async function fetchPolicyDetail(policyId: number, carrierId: number) {
  const { data } = await axios.get(`/api/v1/policies/${policyId}?carrier_id=${carrierId}`);
  return data;
}
async function fetchPremiumVariance(policyId: number, carrierId: number) {
  try {
    const { data } = await axios.get(`/api/v1/policies/${policyId}/premium-variance?carrier_id=${carrierId}`);
    return data;
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) return null;
    throw err;
  }
}
async function fetchPayrollVariance(policyId: number, carrierId: number) {
  try {
    const { data } = await axios.get(`/api/v1/policies/${policyId}/payroll-variance?carrier_id=${carrierId}`);
    return data;
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) return null;
    throw err;
  }
}
async function fetchSubmissionMetrics(policyId: number, carrierId: number) {
  const { data } = await axios.get(`/api/v1/policies/${policyId}/submission-metrics?carrier_id=${carrierId}`);
  return data;
}
async function fetchZeroPayroll(policyId: number, carrierId: number) {
  const { data } = await axios.get(`/api/v1/policies/${policyId}/zero-payroll?carrier_id=${carrierId}`);
  return data;
}
async function fetchMissingPayroll(policyId: number, carrierId: number) {
  const { data } = await axios.get(`/api/v1/policies/${policyId}/missing-payroll?carrier_id=${carrierId}`);
  return data;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "10px", fontWeight: 600, textTransform: "uppercase",
                     letterSpacing: "0.5px", color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>{value ?? "—"}</span>
    </div>
  );
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(d));
}
function fmtCurrency(v: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(v);
}

// ── Summary tab ─────────────────────────────────────────────────────────────

function SummaryTab({ policyId, carrierId, engineOn }: { policyId: number; carrierId: number; engineOn: boolean }) {
  const labels = useLabels();
  const { data: pv } = useQuery({ queryKey: ["pv", policyId, carrierId], queryFn: () => fetchPremiumVariance(policyId, carrierId) });
  const { data: pvp } = useQuery({ queryKey: ["pvp", policyId, carrierId], queryFn: () => fetchPayrollVariance(policyId, carrierId) });
  const { data: pm } = useQuery({ queryKey: ["pm", policyId, carrierId], queryFn: () => fetchSubmissionMetrics(policyId, carrierId) });

  const varAmt = pv?.variance_amount ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Payroll metrics pills */}
      {pm && (
        <div>
          <div className="section-title">Payroll Submissions</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
            <PayrollPill label={labels.pm_actual_received}    value={pm.actual_received}    engineOn={engineOn} alwaysAvailable />
            <PayrollPill label={labels.pm_zero_payrolls}      value={pm.zero_payroll_count} engineOn={engineOn} alwaysAvailable />
            <PayrollPill label={labels.pm_expected_submissions} value={pm.expected_submissions} engineOn={engineOn} />
            <PayrollPill label={labels.pm_missing_payrolls}   value={pm.missing_payroll_count} engineOn={engineOn} />
            <PayrollPill label={labels.pm_submission_rate}    value={pm.submission_rate !== null ? `${(pm.submission_rate * 100).toFixed(1)}%` : null} engineOn={engineOn} />
          </div>
        </div>
      )}

      {/* Premium variance */}
      {pv && (
        <div>
          <div className="section-title">{labels.pv_section_title}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-3)" }}>
            <div className="card-sm">
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>{labels.pv_est_premium}</div>
              <div className="font-mono" style={{ fontWeight: 600 }}>{fmtCurrency(pv.est_premium_end)}</div>
            </div>
            <div className="card-sm">
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>{labels.pv_actual_premium}</div>
              <div className="font-mono" style={{ fontWeight: 600 }}>{fmtCurrency(pv.actual_premium)}</div>
            </div>
            <div className="card-sm">
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>{labels.pv_variance_amount}</div>
              <div className={`font-mono ${(varAmt ?? 0) > 0 ? "variance-positive" : "variance-negative"}`} style={{ fontWeight: 600 }}>
                {varAmt !== null ? fmtCurrency(varAmt) : "—"}
              </div>
            </div>
            <div className="card-sm">
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>{labels.pv_variance_pct}</div>
              <NaIndicator engineOn={engineOn} value={pv.variance_pct} format="pct" className="font-mono" />
            </div>
          </div>
        </div>
      )}

      {/* Payroll variance */}
      {pvp && (
        <div>
          <div className="section-title">{labels.pvp_section_title}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-3)" }}>
            {[
              { label: labels.pvp_est_payroll,           value: fmtCurrency(pvp.est_payroll),              alwaysOn: true },
              { label: labels.pvp_actual_reported,       value: fmtCurrency(pvp.actual_payroll_reported),  alwaysOn: true },
              { label: labels.pvp_reported_over_under,   value: fmtCurrency(pvp.reported_over_under),      alwaysOn: true },
              { label: labels.pvp_actual_classified,     value: fmtCurrency(pvp.actual_payroll_classified), alwaysOn: true },
              { label: labels.pvp_classified_over_under, value: fmtCurrency(pvp.classified_over_under),    alwaysOn: true },
              { label: labels.pvp_reported_pct,          value: pvp.reported_pct,                          alwaysOn: false },
              { label: labels.pvp_classified_pct,        value: pvp.classified_pct,                        alwaysOn: false },
            ].map((item) => (
              <div key={item.label} className="card-sm">
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>{item.label}</div>
                {item.alwaysOn ? (
                  <div className="font-mono" style={{ fontWeight: 600 }}>{item.value}</div>
                ) : (
                  <NaIndicator engineOn={engineOn} value={item.value} format="pct" className="font-mono" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Missing payrolls tab ─────────────────────────────────────────────────────

function MissingPayrollsTab({ policyId, carrierId }: { policyId: number; carrierId: number }) {
  const labels = useLabels();
  const { data, isLoading } = useQuery({ queryKey: ["mp", policyId, carrierId], queryFn: () => fetchMissingPayroll(policyId, carrierId) });

  if (isLoading) return <div className="spinner" />;
  if (!data?.rows.length) return <div className="empty-state"><span>{labels.no_data}</span></div>;

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {[labels.zp_policyholder, labels.zp_policy_number, labels.zp_state,
              labels.mp_period_start, labels.mp_period_end, labels.zp_frequency, labels.mp_days_since].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r: any) => (
            <tr key={r.mp_id}>
              <td>{r.policyholder_name ?? "—"}</td>
              <td className="font-mono">{r.policy_number ?? "—"}</td>
              <td>{r.state_code ?? "—"}</td>
              <td>{fmtDate(r.period_start)}</td>
              <td>{fmtDate(r.period_end)}</td>
              <td>{r.payroll_frequency ?? "—"}</td>
              <td>{r.days_since_last_run ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Zero payrolls tab ────────────────────────────────────────────────────────

function ZeroPayrollsTab({ policyId, carrierId }: { policyId: number; carrierId: number }) {
  const labels = useLabels();
  const { data, isLoading } = useQuery({ queryKey: ["zp", policyId, carrierId], queryFn: () => fetchZeroPayroll(policyId, carrierId) });

  if (isLoading) return <div className="spinner" />;
  if (!data?.rows.length) return <div className="empty-state"><span>{labels.no_data}</span></div>;

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {[labels.zp_policyholder, labels.zp_policy_number, labels.zp_state,
              labels.zp_report_date, labels.zp_frequency].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r: any) => (
            <tr key={r.zp_id}>
              <td>{r.policyholder_name ?? "—"}</td>
              <td className="font-mono">{r.policy_number ?? "—"}</td>
              <td>{r.state_code ?? "—"}</td>
              <td>{fmtDate(r.report_date)}</td>
              <td>{r.payroll_frequency ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── AI Narrative tab ─────────────────────────────────────────────────────────

function AINarrativeTab({ engineOn }: { engineOn: boolean }) {
  return (
    <div
      className="card"
      style={{ fontStyle: "italic", color: "var(--text-muted)", textAlign: "center" }}
    >
      {engineOn
        ? "AI narrative will appear here after the calculation engine runs."
        : "Enable the calculation engine and re-run to generate an AI narrative."}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main PolicyDetailPage
// ---------------------------------------------------------------------------

export function PolicyDetailPage(): React.JSX.Element {
  const { policyId } = useParams<{ policyId: string }>();
  const [searchParams] = useSearchParams();
  const labels = useLabels();
  const { carrierId } = useTenantCarrier();

  const pid = Number(policyId);
  const cid = Number(searchParams.get("carrier_id") ?? carrierId);

  const [activeTab, setActiveTab] = useState(0);

  const { data: detail, isLoading, isError } = useQuery({
    queryKey: ["policy-detail", pid, cid],
    queryFn: () => fetchPolicyDetail(pid, cid),
  });

  if (isLoading) {
    return (
      <div className="page-content">
        <div className="skeleton" style={{ height: "200px", borderRadius: "var(--radius-lg)" }} />
      </div>
    );
  }

  if (isError || !detail) {
    return <div className="page-content"><div className="error-banner">{labels.error_generic}</div></div>;
  }

  const meta = detail.meta;
  const engineOn: boolean = detail.engine_on;

  const tabs = [
    { label: labels.tab_summary,         component: <SummaryTab policyId={pid} carrierId={cid} engineOn={engineOn} /> },
    { label: labels.tab_missing_payrolls, component: <MissingPayrollsTab policyId={pid} carrierId={cid} /> },
    { label: labels.tab_zero_payrolls,    component: <ZeroPayrollsTab policyId={pid} carrierId={cid} /> },
    { label: labels.tab_ai_narrative,     component: <AINarrativeTab engineOn={engineOn} /> },
  ];

  return (
    <main className="page-content animate-fade-in">
      <Breadcrumb items={[{ label: "Policies", href: "/policies" }, { label: meta.policy_number }]} />

      {/* ── Meta card ────────────────────────────────────────────────────── */}
      <div
        className="card"
        style={{ marginBottom: "var(--space-6)" }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: "var(--space-5)",
          }}
        >
          <div>
            <div style={{ fontSize: "20px", fontWeight: 700, fontFamily: "'DM Mono', monospace" }}>
              {meta.policy_number}
            </div>
            <div style={{ fontSize: "15px", color: "var(--text-muted)", marginTop: "2px" }}>
              {meta.insured_name}
            </div>
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            <RiskBadge risk={meta.risk_level} />
            <AuditStatusBadge status={meta.audit_status} />
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-4)" }}>
          <MetaRow label={labels.meta_fein}         value={meta.fein} />
          <MetaRow label={labels.meta_state}        value={meta.state_code} />
          <MetaRow label={labels.meta_effective}    value={fmtDate(meta.effective_date)} />
          <MetaRow label={labels.meta_expiration}   value={fmtDate(meta.expiration_date)} />
          <MetaRow label={labels.meta_cancellation} value={fmtDate(meta.cancellation_date)} />
          <MetaRow label={labels.meta_payment_freq} value={meta.payment_frequency} />
          <MetaRow label={labels.meta_owner_status} value={meta.owner_status} />
          <MetaRow
            label={labels.meta_total_est_payroll}
            value={
              <NaIndicator
                engineOn={engineOn}
                value={meta.total_est_payroll}
                format="currency"
                className="font-mono"
              />
            }
          />
        </div>

        {!engineOn && (
          <div
            className="error-banner"
            style={{
              marginTop: "var(--space-4)",
              color: "var(--color-amber)",
              backgroundColor: "color-mix(in srgb, var(--color-amber) 10%, transparent)",
              borderColor: "color-mix(in srgb, var(--color-amber) 30%, transparent)",
            }}
          >
            {labels.engine_off_notice}
          </div>
        )}
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="tab-bar">
        {tabs.map((tab, i) => (
          <button
            key={i}
            className={`tab${activeTab === i ? " active" : ""}`}
            onClick={() => setActiveTab(i)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="animate-fade-in">
        {tabs[activeTab]?.component}
      </div>
    </main>
  );
}
