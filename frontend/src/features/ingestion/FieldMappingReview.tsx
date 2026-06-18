

import React, { useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";
import {
  fetchMappingSession,
  fetchCanonicalColumns,
  updateMappingProposal,
  approveMapping,
  rejectMapping,
  uploadFile,
  runAuditEngine,
  type MappingProposal,
} from "./services/ingestionApi";
 
const CONFIDENCE_ORDER = ["HIGH", "MEDIUM", "LOW", "UNMATCHED"] as const;
 
const CONFIDENCE_CLASS: Record<string, string> = {
  HIGH:      "badge badge--green",
  MEDIUM:    "badge badge--amber",
  LOW:       "badge badge--amber",
  UNMATCHED: "badge badge--red",
};
 
const TRANSFORM_FNS = ["none", "to_date", "to_decimal", "to_integer", "to_boolean", "strip", "upper"];
 
export function FieldMappingReview(): React.JSX.Element {
  const label_field_mapping = useLabels("field_mapping");
  const label_shared = useLabels("shared");
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const location = useLocation();
  const { user } = useAuth();
 
  const locationState = location.state as {
    sessionId?: number;
    runId?: number;
    ingestionMode?: string;
    bulkQueue?: Array<{
      policyKey: string;
      files: Array<{ slotType: string; name: string }>;
    }>;
    hasBulkQueue?: boolean;
    // Accumulated run_ids from all files already processed in this bulk session.
    // Passed through each navigation hop so the last file can send them all to
    // run_audit, enabling one LLM call per policy with complete data.
    completedRunIds?: number[];
  } | null;
 
  const sessionId       = locationState?.sessionId;
  const bulkQueue       = locationState?.bulkQueue ?? [];
  const hasBulkQueue    = locationState?.hasBulkQueue ?? false;
  // All run_ids completed so far in this bulk session (accumulated across hops).
  const completedRunIds = locationState?.completedRunIds ?? [];
 
  // State for bulk queue processing progress
  const [bulkStatus, setBulkStatus] = React.useState<string | null>(null);
  const isTenantAdmin = user?.role === "TENANT_ADMIN";
 
  const [collapsedTiers, setCollapsedTiers] = useState<Set<string>>(new Set(["HIGH"]));
  const [pendingUpdates, setPendingUpdates] = useState<Map<number, Partial<MappingProposal>>>(new Map());
 
  const { data: session, isLoading, isError, refetch } = useQuery({
    queryKey: ["mapping-session", sessionId],
    queryFn: () => fetchMappingSession(sessionId!),
    enabled: sessionId != null,
  });
 
  const { data: canonicalColumns = [] } = useQuery({
    queryKey: ["canonical-columns"],
    queryFn: fetchCanonicalColumns,
    staleTime: Infinity,
  });
 
  const approveMutation = useMutation({
    mutationFn: () => approveMapping(sessionId!),
    onSuccess: async () => {
      // ── Bulk upload queue continuation ────────────────────────────────────
      // If this mapping approval is part of a bulk upload session and there
      // are more policies waiting, upload the next group automatically without
      // requiring the user to navigate back to the bulk upload page.
      if (hasBulkQueue && bulkQueue.length > 0) {
        const nextGroup   = bulkQueue[0];
        const remaining   = bulkQueue.slice(1);
        const fileStore   = (window as Window & { __bulkFileStore?: Record<string, File> }).__bulkFileStore ?? {};
        const modeRaw     = (window as Window & { __bulkIngestionMode?: string }).__bulkIngestionMode;
        const ingestionMode = (modeRaw === "display_only" ? "display_only" : "calc_engine") as "calc_engine" | "display_only";
        const carrierId   = (window as Window & { __bulkCarrierId?: number }).__bulkCarrierId ?? 1;
        const currentRunId = Number(runId);
 
        // ── calc_engine only: run engine per file as each is approved. ────────
        // For display_only we do NOT run audit here — we wait until the last
        // file so we have ALL data from ALL five sheets before calling the LLM.
        if (ingestionMode === "calc_engine" && currentRunId > 0) {
          setBulkStatus("Running calculation engine for current policy…");
          try {
            await runAuditEngine(carrierId, currentRunId);
          } catch {
            // Non-fatal — bulk queue continues even if one policy fails.
          }
        }
 
        // Accumulate this run_id so the last file can pass the full list.
        const nowCompletedRunIds = [...completedRunIds, ...(currentRunId > 0 ? [currentRunId] : [])];
 
        const slotOrder = ingestionMode === "display_only"
          ? ["display", "csv"]
          : ["xml", "payroll", "audit"];
 
        const orderedFiles = [...nextGroup.files].sort((a, b) => {
          const ai = slotOrder.indexOf(a.slotType);
          const bi = slotOrder.indexOf(b.slotType);
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        });
 
        setBulkStatus(`Uploading next policy: ${nextGroup.policyKey}…`);
 
        try {
          let nextRunId     = 0;
          let nextSessionId = 0;
 
          for (let fi = 0; fi < orderedFiles.length; fi++) {
            const entry = orderedFiles[fi];
            const file  = fileStore[entry.name];
            if (!file) {
              setBulkStatus(`File not found: ${entry.name}. Please return to bulk upload.`);
              return;
            }
 
            const isLastFile = fi === orderedFiles.length - 1;
            const resp = await uploadFile(carrierId, 1, file, ingestionMode);
            nextRunId     = resp.run_id;
            nextSessionId = resp.session_id;
 
            if (!isLastFile) {
              // Auto-approve non-audit files (XML, payroll)
              await approveMapping(resp.session_id);
              await new Promise((r) => setTimeout(r, 600));
            }
          }
 
          // Navigate to the next policy's mapping review, carrying
          // the accumulated run_ids so the last file can use them all.
          navigate(`/audit-runner/${nextRunId}/mapping`, {
            state: {
              sessionId:       nextSessionId,
              runId:           nextRunId,
              bulkQueue:       remaining,
              hasBulkQueue:    remaining.length > 0,
              completedRunIds: nowCompletedRunIds,
            },
          });
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "Upload failed";
          setBulkStatus(`Failed to upload ${nextGroup.policyKey}: ${msg}. Return to bulk upload to retry.`);
        }
        return;
      }
 
      // ── Normal (single-policy) flow ───────────────────────────────────────
      // Also run calc engine automatically for single-policy bulk uploads
      // (hasBulkQueue=true but bulkQueue is empty = last policy in the queue)
      const currentRunId = Number(runId);
      const carrierIdFinal = (window as Window & { __bulkCarrierId?: number }).__bulkCarrierId;
      // isBulkLast: this is the last file in a display_only bulk session.
      // Conditions: we're NOT in the mid-queue branch (bulkQueue is empty),
      // AND we have accumulated run_ids from prior files (completedRunIds non-empty),
      // OR hasBulkQueue was explicitly true (calc_engine / original path).
      // Using completedRunIds.length > 0 as the reliable indicator because
      // BulkUploadPage sets hasBulkQueue:false when there's only 1 remaining file.
      const modeRawForLast = (window as Window & { __bulkIngestionMode?: string }).__bulkIngestionMode;
      const isBulkLast = (
        (locationState?.hasBulkQueue === true && bulkQueue.length === 0) ||
        (modeRawForLast === "display_only" && completedRunIds.length > 0 && bulkQueue.length === 0)
      );
 
      if (isBulkLast && currentRunId > 0 && carrierIdFinal) {
        const modeRaw = (window as Window & { __bulkIngestionMode?: string }).__bulkIngestionMode;
        setBulkStatus(
          modeRaw === "display_only"
            ? "Generating AI narratives for all policies…"
            : "Running calculation engine for final policy…"
        );
        try {
          if (modeRaw === "display_only") {
            // Pass ALL run_ids from the session so the backend can aggregate
            // complete data for every policy before calling the LLM.
            // This is the ONLY runAuditEngine call for display_only — all
            // five files are already ingested at this point.
            const allSessionRunIds = [...completedRunIds, currentRunId];
            await runAuditEngine(carrierIdFinal, currentRunId, undefined, allSessionRunIds);
          } else {
            await runAuditEngine(carrierIdFinal, currentRunId);
          }
        } catch { /* non-fatal */ }
      }
 
      // Pass ingestionMode so IngestionProgress can auto-trigger narrative for display_only
      const modeForProgress = (window as Window & { __bulkIngestionMode?: string }).__bulkIngestionMode
        ?? (locationState as { ingestionMode?: string } | null)?.ingestionMode
        ?? null;
      // Pass bulkRunIds so IngestionProgress skips its own auto-trigger
      // (FieldMappingReview already called runAuditEngine with full session data).
      const bulkRunIdsForProgress = isBulkLast
        ? [...completedRunIds, Number(runId)]  // already fired above — signal to skip
        : [];
      navigate(`/audit-runner/${runId}/progress`, {
        state: {
          runId:       Number(runId),
          sessionId,
          ingestionMode: modeForProgress,
          bulkRunIds:    bulkRunIdsForProgress,
        },
      });
    },
  });
 
  const rejectMutation = useMutation({
    mutationFn: () => rejectMapping(sessionId!),
    onSuccess: () => {
      navigate("/audit-runner");
    },
  });
 
  function toggleTier(tier: string): void {
    setCollapsedTiers((prev) => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
  }
 
  function handleProposalChange(
    proposal: MappingProposal,
    field: "proposed_target" | "transform_fn" | "is_excluded",
    value: string | boolean | null
  ): void {
    setPendingUpdates((prev) => {
      const next = new Map(prev);
      const existing = next.get(proposal.proposal_id) ?? {};
      next.set(proposal.proposal_id, { ...existing, [field]: value });
      return next;
    });
    // Persist immediately
    updateMappingProposal(proposal.session_id, proposal.proposal_id, {
      [field]: value,
    }).then(() => refetch());
  }
 
  const proposals = session?.proposals ?? [];
  const unmatchedCount = proposals.filter(
    (p) => p.confidence === "UNMATCHED" && !p.is_excluded
  ).length;
  const allResolved = unmatchedCount === 0;
 
  if (!sessionId) {
    return (
      <div className="field-mapping-review__error">
        {label_field_mapping("mapping.session_missing", "No mapping session found. Please re-upload the file.") ?? "No mapping session found. Please re-upload the file."}
        <button className="btn btn--primary" onClick={() => navigate("/audit-runner")}>
          {label_field_mapping("btn.back_to_upload", "Back to Upload") ?? "Back to Upload"}
        </button>
      </div>
    );
  }
 
  if (isLoading) {
    return <div className="field-mapping-review__loading">{label_shared("loading", "Loading…") ?? "Loading mapping…"}</div>;
  }
 
  if (isError || !session) {
    return (
      <div className="field-mapping-review__error">
        {label_field_mapping("mapping.load_error", "Failed to load field mapping.") ?? "Failed to load field mapping."}
      </div>
    );
  }
 
  return (
    <div className="field-mapping-review">
      {/* Header */}
      <div className="field-mapping-review__header">
        <div>
          <h1 className="field-mapping-review__title">
            {label_field_mapping("title", "User Management") ?? "Field Mapping Review"}
          </h1>
          {hasBulkQueue && (
            <div
              style={{
                marginTop: "8px",
                padding: "8px 14px",
                background: "rgba(99,102,241,0.10)",
                border: "1px solid rgba(99,102,241,0.30)",
                borderRadius: "6px",
                fontSize: "12px",
                color: "var(--text-muted)",
              }}
            >
              <strong style={{ color: "var(--accent)" }}>
                📦 Bulk Upload in progress
              </strong>
              {" — "}
              {bulkQueue.length} more {bulkQueue.length === 1 ? "policy" : "policies"} will
              upload automatically after you approve this mapping.
            </div>
          )}
          {bulkStatus && (
            <div
              style={{
                marginTop: "8px",
                padding: "10px 14px",
                background: "rgba(245,158,11,0.10)",
                border: "1px solid var(--color-amber)",
                borderRadius: "6px",
                fontSize: "13px",
                color: "var(--color-amber)",
              }}
            >
              ⟳ {bulkStatus}
            </div>
          )}
          <p className="field-mapping-review__subtitle">
            {label_field_mapping("subtitle", "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields.") ??
              "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields."}
          </p>
        </div>
 
        {/* Summary counts */}
        <div className="field-mapping-review__summary">
          <div className="field-mapping-review__count">
            <span className="badge badge--green">{label_field_mapping("confidence.high", "HIGH") ?? "HIGH"}</span>
            <span>{session.auto_mapped_count}</span>
          </div>
          <div className="field-mapping-review__count">
            <span className="badge badge--amber">{label_field_mapping("confidence.medium_low", "MED/LOW") ?? "MED/LOW"}</span>
            <span>{session.flagged_count}</span>
          </div>
          <div className="field-mapping-review__count">
            <span className="badge badge--red">{label_field_mapping("confidence.unmatched", "UNMATCHED") ?? "UNMATCHED"}</span>
            <span>{session.unmatched_count}</span>
          </div>
        </div>
      </div>
 
      {/* Confidence-tiered sections */}
      {CONFIDENCE_ORDER.map((tier) => {
        const tierProposals = proposals.filter((p) => p.confidence === tier);
        if (tierProposals.length === 0) return null;
 
        const isCollapsed = collapsedTiers.has(tier);
 
        return (
          <div key={tier} className={`field-mapping-review__tier field-mapping-review__tier--${tier.toLowerCase()}`}>
            {/* Section header */}
            <button
              className="field-mapping-review__tier-header"
              onClick={() => toggleTier(tier)}
              aria-expanded={!isCollapsed}
            >
              <span className={CONFIDENCE_CLASS[tier]}>{tier}</span>
              <span className="field-mapping-review__tier-count">
                {tierProposals.length} {label_field_mapping("fields", "fields") ?? "fields"}
              </span>
              <span className="field-mapping-review__tier-chevron">
                {isCollapsed ? "▶" : "▼"}
              </span>
            </button>
 
            {/* Proposals table */}
            {!isCollapsed && (
              <table className="field-mapping-review__table">
                <thead>
                  <tr>
                    <th>{label_field_mapping("col.source_field", "Source Field") ?? "Source Field"}</th>
                    <th>{label_field_mapping("col.source_sample", "Sample Value") ?? "Sample Value"}</th>
                    <th>{label_field_mapping("col.proposed_target", "Target Column") ?? "Target Column"}</th>
                    <th>{label_field_mapping("col.transform", "Transform") ?? "Transform"}</th>
                    <th>{label_field_mapping("col.exclude", "Exclude") ?? "Exclude"}</th>
                  </tr>
                </thead>
                <tbody>
                  {tierProposals.map((proposal) => {
                    const isEditable = tier !== "HIGH";
                    return (
                      <tr
                        key={proposal.proposal_id}
                        className={[
                          "field-mapping-review__row",
                          proposal.is_excluded ? "field-mapping-review__row--excluded" : "",
                        ].join(" ")}
                      >
                        <td className="field-mapping-review__cell--source">
                          <span className="field-mapping-review__source-field">
                            {proposal.source_field}
                          </span>
                          <span className="field-mapping-review__inferred-type">
                            {proposal.inferred_type}
                          </span>
                        </td>
                        <td className="field-mapping-review__cell--sample">
                          <code>{proposal.source_sample ?? "—"}</code>
                        </td>
                        <td className="field-mapping-review__cell--target">
                          {isEditable ? (
                            <select
                              className="field-mapping-review__target-select"
                              value={proposal.proposed_target ?? ""}
                              onChange={(e) =>
                                handleProposalChange(
                                  proposal,
                                  "proposed_target",
                                  e.target.value || null
                                )
                              }
                              disabled={proposal.is_excluded}
                            >
                              <option value="">
                                {label_field_mapping("mapping.unassigned", "— Unassigned —") ?? "— Unassigned —"}
                              </option>
                              {canonicalColumns.map((col) => (
                                <option key={col.column_name} value={col.column_name}>
                                  {col.column_name} ({col.data_type})
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="field-mapping-review__target-fixed">
                              {proposal.proposed_target ?? "—"}
                            </span>
                          )}
                        </td>
                        <td className="field-mapping-review__cell--transform">
                          {isEditable ? (
                            <select
                              className="field-mapping-review__transform-select"
                              value={proposal.transform_fn}
                              onChange={(e) =>
                                handleProposalChange(proposal, "transform_fn", e.target.value)
                              }
                              disabled={proposal.is_excluded}
                            >
                              {TRANSFORM_FNS.map((fn) => (
                                <option key={fn} value={fn}>{fn}</option>
                              ))}
                            </select>
                          ) : (
                            <span>{proposal.transform_fn}</span>
                          )}
                        </td>
                        <td className="field-mapping-review__cell--exclude">
                          <input
                            type="checkbox"
                            checked={proposal.is_excluded}
                            onChange={(e) =>
                              handleProposalChange(proposal, "is_excluded", e.target.checked)
                            }
                            aria-label={`${label_field_mapping("col.exclude", "Exclude") ?? "Exclude"} ${proposal.source_field}`}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
 
      {/* Action bar */}
      <div className="field-mapping-review__actions">
        <button
          className="btn btn--secondary"
          onClick={() => rejectMutation.mutate()}
          disabled={rejectMutation.isPending}
        >
          {label_field_mapping("btn.reject_mapping", "Reject & Start Over") ?? "Reject & Start Over"}
        </button>
 
        {/* Approve Mapping — TENANT_ADMIN only */}
        {isTenantAdmin && (
          <button
            className="btn btn--primary"
            onClick={() => approveMutation.mutate()}
            disabled={!allResolved || approveMutation.isPending}
            title={
              !allResolved
                ? (label_field_mapping("mapping.approve_disabled_tooltip", "Assign or exclude all UNMATCHED fields before approving.") ??
                    "Assign or exclude all UNMATCHED fields before approving.")
                : undefined
            }
          >
            {approveMutation.isPending
              ? (label_field_mapping("btn.approving", "Approving…") ?? "Approving…")
              : (label_field_mapping("btn.approve_mapping", "Approve Mapping") ?? "Approve Mapping")}
          </button>
        )}
 
        {!isTenantAdmin && (
          <p className="field-mapping-review__admin-note">
            {label_field_mapping("mapping.admin_only", "Mapping approval requires Tenant Administrator access.") ??
              "Mapping approval requires Tenant Administrator access."}
          </p>
        )}
      </div>
    </div>
  );
}