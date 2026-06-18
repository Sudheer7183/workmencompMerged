import React, { useState } from "react";
import axios from "axios";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { NarrativePanel } from "./components/NarrativePanel";
import type { NarrativeData } from "./components/NarrativePanel";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useLabels } from "@/hooks/useLabels";
import { Breadcrumb } from "@/components/ui/Controls";
import { NaIndicator } from "@/components/ui/NaIndicator";
import { RiskBadge, AuditStatusBadge } from "@/components/ui/Badges";
import { RequestReportButton } from "@/features/reports/RequestReportButton";

// ─── API helpers ─────────────────────────────────────────────────────────────

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
async function fetchClassCodeVariance(policyId: number, carrierId: number) {
  try {
    const { data } = await axios.get(`/api/v1/policies/${policyId}/class-code-variance?carrier_id=${carrierId}`);
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

// ─── Formatters ───────────────────────────────────────────────────────────────

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(d));
}
function fmtCurrency(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(v);
}
function fmtNum(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat("en-US").format(v);
}
function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "N/A";
  return `${(v * 100).toFixed(2)}%`;
}
function fmtOverUnder(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v < 0) return `(${fmtNum(Math.abs(v))})`;
  return fmtNum(v);
}
function colorClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "";
  if (v < 0) return "variance-negative";
  if (v > 0) return "variance-positive";
  return "";
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "10px", fontWeight: 600, textTransform: "uppercase",
                     letterSpacing: "0.5px", color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>{value ?? "—"}</span>
    </div>
  );
}

function VarCard({
  label, value, colorValue, format = "currency",
}: {
  label: string;
  value: React.ReactNode;
  colorValue?: number | null;
  format?: "currency" | "pct" | "raw";
}) {
  const cls = colorValue !== undefined ? colorClass(colorValue) : "";
  return (
    <div className="card-sm" style={{ minWidth: "140px" }}>
      <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "6px", lineHeight: "1.4" }}>
        {label}
      </div>
      <div className={`font-mono ${cls}`} style={{ fontSize: "16px", fontWeight: 700 }}>
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "13px", fontWeight: 700, textTransform: "uppercase",
      letterSpacing: "0.6px", color: "var(--text-secondary)",
      marginBottom: "12px", marginTop: "4px",
      paddingBottom: "6px", borderBottom: "1px solid var(--border-subtle)",
    }}>
      {title}
    </div>
  );
}

// ─── Summary tab ──────────────────────────────────────────────────────────────

function SummaryTab({
  policyId, carrierId, engineOn, onTabChange,
}: {
  policyId: number;
  carrierId: number;
  engineOn: boolean;
  onTabChange: (tab: number) => void;
}) {
  const { data: pv }  = useQuery({ queryKey: ["pv",  policyId, carrierId], queryFn: () => fetchPremiumVariance(policyId, carrierId) });
  const { data: pvp } = useQuery({ queryKey: ["pvp", policyId, carrierId], queryFn: () => fetchPayrollVariance(policyId, carrierId) });
  const { data: pvc } = useQuery({ queryKey: ["pvc", policyId, carrierId], queryFn: () => fetchClassCodeVariance(policyId, carrierId) });
  const { data: pm }  = useQuery({ queryKey: ["pm",  policyId, carrierId], queryFn: () => fetchSubmissionMetrics(policyId, carrierId) });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>

      {/* ── 1. Premium Variance ─────────────────────────────────────────── */}
      {pv && (
        <div>
          <SectionTitle title="Premium Variance" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
            <VarCard
              label="Actual Premium to Date"
              value={fmtCurrency(pv.actual_premium)}
              colorValue={pv.actual_premium}
            />
            <VarCard
              label="Est Premium to End Date"
              value={fmtCurrency(pv.est_premium_end)}
            />
            <VarCard
              label="Variance $"
              value={fmtCurrency(pv.variance_amount)}
              colorValue={pv.variance_amount}
            />
            <VarCard
              label="Actual Premium as % of Est Premium End Date"
              value={<NaIndicator engineOn={engineOn} value={pv.variance_pct} format="pct" className="font-mono" />}
            />
          </div>
        </div>
      )}

      {/* ── 2. Payroll Variance ──────────────────────────────────────────── */}
      {pvp && (
        <div>
          <SectionTitle title="Payroll Variance" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
            <VarCard label="Estimated Payroll"                  value={fmtCurrency(pvp.est_payroll)} />
            <VarCard label="Actual Payroll As Reported"         value={fmtCurrency(pvp.actual_payroll_reported)}  colorValue={pvp.actual_payroll_reported} />
            <VarCard label="Actual Reported Over (Under) Est"   value={fmtOverUnder(pvp.reported_over_under)}     colorValue={pvp.reported_over_under} />
            <VarCard
              label="Actual Reported % of Est"
              value={<NaIndicator engineOn={engineOn} value={pvp.reported_pct} format="pct" className="font-mono" />}
            />
            <VarCard label="Actual Payroll as Classified"        value={fmtCurrency(pvp.actual_payroll_classified)} colorValue={pvp.actual_payroll_classified} />
            <VarCard label="Actual Classified Over (Under) Est"  value={fmtOverUnder(pvp.classified_over_under)}    colorValue={pvp.classified_over_under} />
            <VarCard
              label="Actual Classified % of Est"
              value={<NaIndicator engineOn={engineOn} value={pvp.classified_pct} format="pct" className="font-mono" />}
            />
          </div>
        </div>
      )}

      {/* ── 3. Class Code Variance Table ─────────────────────────────────── */}
      <div>
        <SectionTitle title="Class Code Variance — Payroll" />
        {pvc && pvc.rows && pvc.rows.length > 0 ? (
          <div className="data-table-wrapper" style={{ marginBottom: "var(--space-5)" }}>
            <table className="data-table" style={{ fontSize: "12px" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>State</th>
                  <th style={{ textAlign: "left" }}>Class Code</th>
                  <th style={{ textAlign: "right" }}>Est. Payroll (YTD)</th>
                  <th style={{ textAlign: "right" }}>Actual As Reported</th>
                  <th style={{ textAlign: "right" }}>Reported Over (Under) Est</th>
                  <th style={{ textAlign: "right" }}>Reported % of Est</th>
                  <th style={{ textAlign: "right" }}>Actual As Classified</th>
                  <th style={{ textAlign: "right" }}>Classified Over (Under) Est</th>
                  <th style={{ textAlign: "right" }}>Classified % of Est</th>
                </tr>
              </thead>
              <tbody>
                {pvc.rows.map((r: any, i: number) => {
                  const repOU   = (r.actual_reported ?? 0) - (r.est_payroll ?? 0);
                  const clsOU   = (r.actual_classified ?? 0) - (r.est_payroll ?? 0);
                  const repPct  = r.reported_pct;
                  const clsPct  = r.classified_pct;
                  const estZero = !r.est_payroll || r.est_payroll === 0;
                  return (
                    <tr key={i}>
                      <td style={{ textAlign: "left" }}>{r.state_code ?? "—"}</td>
                      <td style={{ textAlign: "left", fontFamily: "var(--font-mono)" }}>{r.class_code ?? "—"}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{fmtNum(r.est_payroll)}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{fmtNum(r.actual_reported)}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        <span className={colorClass(repOU)}>{fmtOverUnder(repOU)}</span>
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {estZero
                          ? <span style={{ color: "var(--text-muted)" }}>N/A</span>
                          : <span className={colorClass(repOU)}>{fmtPct(repPct)}</span>
                        }
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{fmtNum(r.actual_classified)}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        <span className={colorClass(clsOU)}>{fmtOverUnder(clsOU)}</span>
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {estZero
                          ? <span style={{ color: "var(--text-muted)" }}>N/A</span>
                          : <span className={colorClass(clsOU)}>{fmtPct(clsPct)}</span>
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state" style={{ marginBottom: "var(--space-5)" }}>
            <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>No class code data available</span>
          </div>
        )}

        {/* ── 4. Payroll Submission Pills ─────────────────────────────── */}
        {pm && (
          <>
            <SectionTitle title="Payroll" />
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
              {/* Total Expected */}
              <div className="card-sm" style={{ textAlign: "center", minWidth: "120px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Total Payroll Expected
                </div>
                <div className="font-mono" style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-brand)" }}>
                  {pm.expected_submissions ?? "N/A"}
                </div>
              </div>
              {/* Actual Received */}
              <div className="card-sm" style={{ textAlign: "center", minWidth: "120px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Actual Payrolls Received
                </div>
                <div className="font-mono" style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-brand)" }}>
                  {pm.actual_received ?? 0}
                </div>
              </div>
              {/* Missing */}
              <div className="card-sm" style={{ textAlign: "center", minWidth: "120px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Missing Payrolls
                </div>
                <div className="font-mono" style={{
                  fontSize: "20px", fontWeight: 700,
                  color: (pm.missing_payroll_count ?? 0) > 0 ? "var(--color-amber)" : "var(--color-brand)",
                }}>
                  {pm.missing_payroll_count ?? 0}
                </div>
                <button
                  onClick={() => onTabChange(1)}
                  style={{ fontSize: "11px", color: "var(--color-blue, #60a5fa)", background: "none", border: "none",
                           cursor: "pointer", marginTop: "4px", textDecoration: "underline", padding: 0 }}
                >
                  Details
                </button>
              </div>
              {/* Zero Payrolls */}
              <div className="card-sm" style={{ textAlign: "center", minWidth: "120px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Zero Payrolls
                </div>
                <div className="font-mono" style={{
                  fontSize: "20px", fontWeight: 700,
                  color: (pm.zero_payroll_count ?? 0) > 0 ? "var(--color-amber)" : "var(--color-brand)",
                }}>
                  {pm.zero_payroll_count ?? 0}
                </div>
                <button
                  onClick={() => onTabChange(2)}
                  style={{ fontSize: "11px", color: "var(--color-blue, #60a5fa)", background: "none", border: "none",
                           cursor: "pointer", marginTop: "4px", textDecoration: "underline", padding: 0 }}
                >
                  Details
                </button>
              </div>
              {/* Submission Rate */}
              <div className="card-sm" style={{ textAlign: "center", minWidth: "120px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Submission Rate
                </div>
                <div className="font-mono" style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-amber)" }}>
                  {pm.submission_rate !== null && pm.submission_rate !== undefined
                    ? `${(pm.submission_rate * 100).toFixed(0)}%`
                    : "N/A"}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Missing payrolls tab ─────────────────────────────────────────────────────

function MissingPayrollsTab({ policyId, carrierId }: { policyId: number; carrierId: number }) {
  const label_reports = useLabels("reports");
  const label_shared = useLabels("shared");
  const { data, isLoading } = useQuery({ queryKey: ["mp", policyId, carrierId], queryFn: () => fetchMissingPayroll(policyId, carrierId) });

  if (isLoading) return <div className="spinner" />;
  if (!data?.rows.length) return (
    <div className="empty-state">
      <span style={{ color: "var(--text-muted)" }}>No missing payrolls</span>
    </div>
  );

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {["Policyholder", "Policy Number", "State", "Period Start", "Period End", "Frequency", "Days Since"].map((h) => (
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

// ─── Zero payrolls tab ────────────────────────────────────────────────────────

function ZeroPayrollsTab({ policyId, carrierId }: { policyId: number; carrierId: number }) {
  const { data, isLoading } = useQuery({ queryKey: ["zp", policyId, carrierId], queryFn: () => fetchZeroPayroll(policyId, carrierId) });

  if (isLoading) return <div className="spinner" />;
  if (!data?.rows.length) return (
    <div className="empty-state">
      <span style={{ color: "var(--text-muted)" }}>No zero payrolls</span>
    </div>
  );

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {["Policyholder", "Policy Number", "State", "Report Date", "Frequency"].map((h) => (
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

// ─── AI Narrative tab ─────────────────────────────────────────────────────────

function AINarrativeTab({
  engineOn,
  narrative,
}: {
  engineOn: boolean;
  narrative?: NarrativeData | null;
}) {
  if (!engineOn) {
    return (
      <NarrativePanel
        narrative={{ text: "", is_fallback: false, engine_was_off: true }}
      />
    );
  }
  return <NarrativePanel narrative={narrative ?? null} />;
}

// ─── Main PolicyDetailPage ────────────────────────────────────────────────────

export function PolicyDetailPage(): React.JSX.Element {
  const { policyId } = useParams<{ policyId: string }>();
  const [searchParams] = useSearchParams();
  const label_reports = useLabels("reports");
  const label_shared = useLabels("shared");
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
    return <div className="page-content"><div className="error-banner">{label_shared("error_generic", "Something went wrong. Please try again.")}</div></div>;
  }

  const meta     = detail.meta;
  const engineOn = detail.engine_on as boolean;

  const TABS = [
    {
      label: "Policy Summary",
      component: (
        <SummaryTab
          policyId={pid}
          carrierId={cid}
          engineOn={engineOn}
          onTabChange={setActiveTab}
        />
      ),
    },
    { label: "Missing Payrolls", component: <MissingPayrollsTab policyId={pid} carrierId={cid} /> },
    { label: "Zero Payrolls",    component: <ZeroPayrollsTab    policyId={pid} carrierId={cid} /> },
    { label: "AI Narrative",     component: <AINarrativeTab     engineOn={engineOn} narrative={detail?.narrative ?? null} /> },
  ];

  return (
    <main className="page-content animate-fade-in">
      <Breadcrumb items={[{ label: "Policies", href: "/policies" }, { label: meta.policy_number }]} />

      {/* ── Meta card ──────────────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        {/* Header row: policy number + badges */}
        <div style={{
          display: "flex", alignItems: "flex-start",
          justifyContent: "space-between", marginBottom: "var(--space-5)",
        }}>
          <div>
            <div style={{ fontSize: "22px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {meta.policy_number}
            </div>
            <div style={{ fontSize: "14px", color: "var(--text-muted)", marginTop: "2px" }}>
              {meta.insured_name}
            </div>
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            <RiskBadge risk={meta.risk_level} />
            <AuditStatusBadge status={meta.audit_status} />
            <div className="policy-detail__report-actions">
              <RequestReportButton
                carrierId={carrierId}
                reportType="policy_audit"
                policyId={pid}
                policyNumber={meta.policy_number}
                label={label_reports("btn.generate_audit", "report_generate_audit") ?? "Generate Audit Report"}
              />
            </div>
          </div>
        </div>

        {/* Meta grid — matches portal layout */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "var(--space-4) var(--space-6)",
        }}>
          <MetaRow label="FEIN"              value={meta.fein} />
          <MetaRow label="State"             value={meta.state_code} />
          <MetaRow label="Effective Date"    value={fmtDate(meta.effective_date)} />
          <MetaRow label="Expiration Date"   value={fmtDate(meta.expiration_date)} />
          <MetaRow label="Cancellation Date" value={fmtDate(meta.cancellation_date)} />
          <MetaRow label="Payment Frequency" value={meta.payment_frequency} />
          <MetaRow label="Owner Status"      value={meta.owner_status} />
          <MetaRow
            label="Total Est. Payroll"
            value={
              meta.total_est_payroll
                ? <span className="font-mono" style={{ fontWeight: 600 }}>{fmtCurrency(meta.total_est_payroll)}</span>
                : <span style={{ color: "var(--text-muted)" }}>N/A</span>
            }
          />
          {/* Policy Premium as Written — matches portal "Policy Premium as Written" */}
          {meta.premium_written != null && (
            <MetaRow
              label="Policy Premium as Written"
              value={
                <span className="font-mono" style={{ fontWeight: 700, fontSize: "15px", color: "var(--color-brand)" }}>
                  {fmtCurrency(meta.premium_written)}
                </span>
              }
            />
          )}
        </div>

        {/* Engine-off notice */}
        {!engineOn && (
          <div className="error-banner" style={{
            marginTop: "var(--space-4)",
            color: "var(--color-amber)",
            backgroundColor: "color-mix(in srgb, var(--color-amber) 10%, transparent)",
            borderColor: "color-mix(in srgb, var(--color-amber) 30%, transparent)",
          }}>
            {label_shared("engine_off_notice", "Calculation engine is off. Engine-derived fields show N/A.")}
          </div>
        )}
      </div>

      {/* ── Tab bar ────────────────────────────────────────────────────── */}
      <div className="tab-bar">
        {TABS.map((tab, i) => (
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
        {TABS[activeTab]?.component}
      </div>
    </main>
  );
}