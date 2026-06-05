/**
 * FieldMappingReview — Phase 3.
 *
 * Displays auto-mapped field proposals grouped by confidence tier:
 *   HIGH → MEDIUM → LOW → UNMATCHED
 *
 * Rules per V9 S16.4:
 *   - MEDIUM/LOW/UNMATCHED: proposed_target dropdown is editable
 *   - "Approve Mapping" button: TENANT_ADMIN only (hidden for AUDITOR/REVIEWER)
 *   - "Accept All" button: enabled only when UNMATCHED count = 0
 *   - Reject: returns to AuditRunnerPage
 *
 * Route: /audit-runner/:runId/mapping
 */

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
  const labels = useLabels();
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const location = useLocation();
  const { user } = useAuth();

  const sessionId = (location.state as { sessionId?: number } | null)?.sessionId;
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
    onSuccess: (result) => {
      navigate(`/audit-runner/${runId}/progress`, {
        state: { runId: Number(runId), sessionId },
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
        {labels.mapping_session_missing ?? "No mapping session found. Please re-upload the file."}
        <button className="btn btn--primary" onClick={() => navigate("/audit-runner")}>
          {labels.btn_back_to_upload ?? "Back to Upload"}
        </button>
      </div>
    );
  }

  if (isLoading) {
    return <div className="field-mapping-review__loading">{labels.loading ?? "Loading mapping…"}</div>;
  }

  if (isError || !session) {
    return (
      <div className="field-mapping-review__error">
        {labels.mapping_load_error ?? "Failed to load field mapping."}
      </div>
    );
  }

  return (
    <div className="field-mapping-review">
      {/* Header */}
      <div className="field-mapping-review__header">
        <div>
          <h1 className="field-mapping-review__title">
            {labels.field_mapping_title ?? "Field Mapping Review"}
          </h1>
          <p className="field-mapping-review__subtitle">
            {labels.field_mapping_subtitle ??
              "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields."}
          </p>
        </div>

        {/* Summary counts */}
        <div className="field-mapping-review__summary">
          <div className="field-mapping-review__count">
            <span className="badge badge--green">{labels.confidence_high ?? "HIGH"}</span>
            <span>{session.auto_mapped_count}</span>
          </div>
          <div className="field-mapping-review__count">
            <span className="badge badge--amber">{labels.confidence_medium_low ?? "MED/LOW"}</span>
            <span>{session.flagged_count}</span>
          </div>
          <div className="field-mapping-review__count">
            <span className="badge badge--red">{labels.confidence_unmatched ?? "UNMATCHED"}</span>
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
                {tierProposals.length} {labels.field_mapping_fields ?? "fields"}
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
                    <th>{labels.col_source_field ?? "Source Field"}</th>
                    <th>{labels.col_source_sample ?? "Sample Value"}</th>
                    <th>{labels.col_proposed_target ?? "Target Column"}</th>
                    <th>{labels.col_transform ?? "Transform"}</th>
                    <th>{labels.col_exclude ?? "Exclude"}</th>
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
                                {labels.mapping_unassigned ?? "— Unassigned —"}
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
                            aria-label={`${labels.col_exclude ?? "Exclude"} ${proposal.source_field}`}
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
          {labels.btn_reject_mapping ?? "Reject & Start Over"}
        </button>

        {/* Approve Mapping — TENANT_ADMIN only */}
        {isTenantAdmin && (
          <button
            className="btn btn--primary"
            onClick={() => approveMutation.mutate()}
            disabled={!allResolved || approveMutation.isPending}
            title={
              !allResolved
                ? (labels.mapping_approve_disabled_tooltip ??
                    "Assign or exclude all UNMATCHED fields before approving.")
                : undefined
            }
          >
            {approveMutation.isPending
              ? (labels.btn_approving ?? "Approving…")
              : (labels.btn_approve_mapping ?? "Approve Mapping")}
          </button>
        )}

        {!isTenantAdmin && (
          <p className="field-mapping-review__admin-note">
            {labels.mapping_admin_only ??
              "Mapping approval requires Tenant Administrator access."}
          </p>
        )}
      </div>
    </div>
  );
}
