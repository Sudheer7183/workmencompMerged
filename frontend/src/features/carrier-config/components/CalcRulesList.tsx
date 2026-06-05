/**
 * CalcRulesList — Phase 3.
 *
 * Displays all 22 carrier calc rules in a table with:
 *  - Status badges (DRAFT | PENDING_REVIEW | ACTIVE | DEACTIVATED)
 *  - LOCKED rules: padlock icon, no edit/transition buttons
 *  - EDITABLE rules: edit button, inline expression editor, history drawer
 *  - Two-step approval: Submit → Approve & Activate
 *  - Expression tester panel
 *  - AI-suggest integration
 *  - Rule history drawer
 *
 * V9 S19.
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";
import type { CalcRule, RuleHistoryEntry } from "../services/carrierConfigApi";
import {
  fetchCalcRules,
  updateRuleExpression,
  submitRuleForReview,
  approveRule,
  revertRule,
  deactivateRule,
  fetchRuleHistory,
  testExpression,
  suggestExpression,
} from "../services/carrierConfigApi";

const STATUS_BADGE_CLASS: Record<string, string> = {
  ACTIVE:         "badge badge--green",
  DRAFT:          "badge badge--amber",
  PENDING_REVIEW: "badge badge--blue",
  DEACTIVATED:    "badge badge--muted",
};

interface CalcRulesListProps {
  carrierId: number;
}

export function CalcRulesList({ carrierId }: CalcRulesListProps): React.JSX.Element {
  const labels = useLabels();
  const qc = useQueryClient();
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [editExpression, setEditExpression] = useState<string>("");
  const [historyRuleId, setHistoryRuleId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [descriptionInput, setDescriptionInput] = useState<string>("");

  const { data: rules = [], isLoading, isError } = useQuery<CalcRule[]>({
    queryKey: ["calc-rules", carrierId],
    queryFn: () => fetchCalcRules(carrierId),
    staleTime: 30_000,
  });

  const { data: history = [] } = useQuery<RuleHistoryEntry[]>({
    queryKey: ["rule-history", historyRuleId],
    queryFn: () => fetchRuleHistory(historyRuleId!),
    enabled: historyRuleId !== null,
  });

  const updateMutation = useMutation({
    mutationFn: ({ ruleId, expression }: { ruleId: number; expression: string }) =>
      updateRuleExpression(ruleId, expression),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calc-rules", carrierId] }),
  });

  const submitMutation = useMutation({
    mutationFn: (ruleId: number) => submitRuleForReview(ruleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calc-rules", carrierId] }),
  });

  const approveMutation = useMutation({
    mutationFn: (ruleId: number) => approveRule(ruleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calc-rules", carrierId] }),
  });

  const revertMutation = useMutation({
    mutationFn: (ruleId: number) => revertRule(ruleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calc-rules", carrierId] }),
  });

  const deactivateMutation = useMutation({
    mutationFn: (ruleId: number) => deactivateRule(ruleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calc-rules", carrierId] }),
  });

  function startEdit(rule: CalcRule): void {
    setEditingRuleId(rule.rule_id);
    setEditExpression(rule.expression);
    setTestResult(null);
    setDescriptionInput(rule.rule_description ?? "");
  }

  function cancelEdit(): void {
    setEditingRuleId(null);
    setEditExpression("");
    setTestResult(null);
  }

  async function saveEdit(ruleId: number): Promise<void> {
    await updateMutation.mutateAsync({ ruleId, expression: editExpression });
    setEditingRuleId(null);
    setEditExpression("");
  }

  async function handleTestExpression(): Promise<void> {
    setIsTesting(true);
    try {
      const result = await testExpression(editExpression, carrierId, {
        variance_pct: 0.35,
        missing_payrolls: 1,
        actual_premium: 50000,
        est_premium_end: 42000,
      });
      setTestResult(
        result.error
          ? `Error: ${result.error}`
          : `Result: ${JSON.stringify(result.result)}`
      );
    } catch {
      setTestResult("Expression test failed.");
    } finally {
      setIsTesting(false);
    }
  }

  async function handleAISuggest(): Promise<void> {
    setIsSuggesting(true);
    try {
      const result = await suggestExpression(descriptionInput || "variance threshold check", carrierId);
      setEditExpression(result.suggested_expression);
      setTestResult(`AI suggestion: ${result.explanation}`);
    } catch {
      setTestResult("AI suggestion failed.");
    } finally {
      setIsSuggesting(false);
    }
  }

  if (isLoading) {
    return <div className="calc-rules-list__loading">{labels.loading ?? "Loading rules…"}</div>;
  }

  if (isError) {
    return (
      <div className="calc-rules-list__error">
        {labels.calc_rules_load_error ?? "Failed to load calculation rules."}
      </div>
    );
  }

  return (
    <div className="calc-rules-list">
      <div className="calc-rules-list__header">
        <h3 className="calc-rules-list__title">
          {labels.calc_rules_title ?? "Calculation Rules"}
        </h3>
        <p className="calc-rules-list__subtitle">
          {labels.calc_rules_subtitle ??
            "22 rules govern how the audit engine computes variance, risk, and payroll metrics. LOCKED rules use built-in Python logic. EDITABLE rules can be customised using safe expressions."}
        </p>
      </div>

      <div className="calc-rules-list__table-wrap">
        <table className="calc-rules-list__table">
          <thead>
            <tr>
              <th>{labels.col_rule_key ?? "Rule Key"}</th>
              <th>{labels.col_rule_label ?? "Label"}</th>
              <th>{labels.col_rule_expression ?? "Expression"}</th>
              <th>{labels.col_rule_status ?? "Status"}</th>
              <th>{labels.col_rule_type ?? "Type"}</th>
              <th>{labels.col_rule_actions ?? "Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <React.Fragment key={rule.rule_id}>
                <tr
                  className={[
                    "calc-rules-list__row",
                    editingRuleId === rule.rule_id ? "calc-rules-list__row--editing" : "",
                  ].join(" ")}
                >
                  <td className="calc-rules-list__cell--key">
                    <code className="calc-rules-list__rule-key">{rule.rule_key}</code>
                  </td>
                  <td className="calc-rules-list__cell--label">
                    <span>{rule.rule_label}</span>
                    {rule.rule_description && (
                      <p className="calc-rules-list__description">{rule.rule_description}</p>
                    )}
                  </td>
                  <td className="calc-rules-list__cell--expression">
                    <code className="calc-rules-list__expression">{rule.expression}</code>
                  </td>
                  <td>
                    <span className={STATUS_BADGE_CLASS[rule.rule_status] ?? "badge"}>
                      {rule.rule_status}
                    </span>
                  </td>
                  <td>
                    {rule.is_editable ? (
                      <span className="badge badge--muted">
                        {labels.rule_type_editable ?? "EDITABLE"}
                      </span>
                    ) : (
                      <span className="calc-rules-list__locked" title={labels.rule_locked_tooltip ?? "This rule uses a built-in Python implementation and cannot be modified."}>
                        🔒 {labels.rule_type_locked ?? "LOCKED"}
                      </span>
                    )}
                  </td>
                  <td className="calc-rules-list__actions">
                    {rule.is_editable && (
                      <>
                        {/* Edit button — only when not DEACTIVATED */}
                        {rule.rule_status !== "DEACTIVATED" && editingRuleId !== rule.rule_id && (
                          <button
                            className="btn btn--secondary btn--sm"
                            onClick={() => startEdit(rule)}
                          >
                            {labels.btn_edit ?? "Edit"}
                          </button>
                        )}
                        {/* Submit for review — DRAFT only */}
                        {rule.rule_status === "DRAFT" && (
                          <button
                            className="btn btn--primary btn--sm"
                            onClick={() => submitMutation.mutate(rule.rule_id)}
                            disabled={submitMutation.isPending}
                          >
                            {labels.btn_submit_review ?? "Submit"}
                          </button>
                        )}
                        {/* Approve — PENDING_REVIEW only */}
                        {rule.rule_status === "PENDING_REVIEW" && (
                          <>
                            <button
                              className="btn btn--primary btn--sm"
                              onClick={() => approveMutation.mutate(rule.rule_id)}
                              disabled={approveMutation.isPending}
                            >
                              {labels.btn_approve_activate ?? "Approve & Activate"}
                            </button>
                            <button
                              className="btn btn--secondary btn--sm"
                              onClick={() => revertMutation.mutate(rule.rule_id)}
                              disabled={revertMutation.isPending}
                            >
                              {labels.btn_revert ?? "Revert"}
                            </button>
                          </>
                        )}
                        {/* Deactivate — ACTIVE editable only */}
                        {rule.rule_status === "ACTIVE" && (
                          <button
                            className="btn btn--danger btn--sm"
                            onClick={() => {
                              if (window.confirm(labels.confirm_deactivate ?? "Deactivate this rule?")) {
                                deactivateMutation.mutate(rule.rule_id);
                              }
                            }}
                            disabled={deactivateMutation.isPending}
                          >
                            {labels.btn_deactivate ?? "Deactivate"}
                          </button>
                        )}
                      </>
                    )}
                    {/* History — all rules */}
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() =>
                        setHistoryRuleId((prev) =>
                          prev === rule.rule_id ? null : rule.rule_id
                        )
                      }
                    >
                      {labels.btn_history ?? "History"}
                    </button>
                  </td>
                </tr>

                {/* Inline edit row */}
                {editingRuleId === rule.rule_id && (
                  <tr className="calc-rules-list__edit-row">
                    <td colSpan={6}>
                      <div className="calc-rules-list__edit-panel">
                        <div className="calc-rules-list__edit-label">
                          {labels.edit_expression_label ?? "Expression"}
                        </div>
                        <textarea
                          className="calc-rules-list__edit-textarea"
                          value={editExpression}
                          onChange={(e) => setEditExpression(e.target.value)}
                          rows={2}
                          spellCheck={false}
                          aria-label={labels.edit_expression_aria ?? "Edit rule expression"}
                        />

                        {/* AI suggest */}
                        <div className="calc-rules-list__ai-row">
                          <input
                            type="text"
                            className="calc-rules-list__ai-input"
                            placeholder={
                              labels.ai_suggest_placeholder ??
                              "Describe the rule in plain English…"
                            }
                            value={descriptionInput}
                            onChange={(e) => setDescriptionInput(e.target.value)}
                          />
                          <button
                            className="btn btn--secondary btn--sm"
                            onClick={handleAISuggest}
                            disabled={isSuggesting}
                          >
                            {isSuggesting
                              ? (labels.btn_suggesting ?? "Suggesting…")
                              : (labels.btn_ai_suggest ?? "AI Suggest")}
                          </button>
                        </div>

                        {/* Expression tester */}
                        <div className="calc-rules-list__tester-row">
                          <button
                            className="btn btn--secondary btn--sm"
                            onClick={handleTestExpression}
                            disabled={isTesting || !editExpression}
                          >
                            {isTesting
                              ? (labels.btn_testing ?? "Testing…")
                              : (labels.btn_test_expression ?? "Test Expression")}
                          </button>
                          {testResult && (
                            <span className="calc-rules-list__test-result">{testResult}</span>
                          )}
                        </div>

                        {/* Save / Cancel */}
                        <div className="calc-rules-list__edit-actions">
                          <button
                            className="btn btn--primary btn--sm"
                            onClick={() => saveEdit(rule.rule_id)}
                            disabled={updateMutation.isPending || !editExpression}
                          >
                            {updateMutation.isPending
                              ? (labels.btn_saving ?? "Saving…")
                              : (labels.btn_save_draft ?? "Save as Draft")}
                          </button>
                          <button className="btn btn--secondary btn--sm" onClick={cancelEdit}>
                            {labels.btn_cancel ?? "Cancel"}
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}

                {/* History drawer */}
                {historyRuleId === rule.rule_id && (
                  <tr className="calc-rules-list__history-row">
                    <td colSpan={6}>
                      <div className="calc-rules-list__history-panel">
                        <h4 className="calc-rules-list__history-title">
                          {labels.rule_history_title ?? "Rule History"}
                        </h4>
                        {history.length === 0 ? (
                          <p className="calc-rules-list__history-empty">
                            {labels.rule_history_empty ?? "No history entries yet."}
                          </p>
                        ) : (
                          <table className="calc-rules-list__history-table">
                            <thead>
                              <tr>
                                <th>{labels.col_changed_at ?? "Date"}</th>
                                <th>{labels.col_changed_by ?? "Changed By"}</th>
                                <th>{labels.col_status_change ?? "Transition"}</th>
                                <th>{labels.col_expression_snapshot ?? "Expression"}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {history.map((entry) => (
                                <tr key={entry.id}>
                                  <td>{new Date(entry.changed_at).toLocaleString()}</td>
                                  <td>{entry.changed_by}</td>
                                  <td>
                                    <span className={STATUS_BADGE_CLASS[entry.previous_status] ?? "badge"}>
                                      {entry.previous_status}
                                    </span>
                                    {" → "}
                                    <span className={STATUS_BADGE_CLASS[entry.new_status] ?? "badge"}>
                                      {entry.new_status}
                                    </span>
                                  </td>
                                  <td>
                                    {entry.expression_snapshot ? (
                                      <code>{entry.expression_snapshot}</code>
                                    ) : (
                                      "—"
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                        <button
                          className="btn btn--ghost btn--sm"
                          onClick={() => setHistoryRuleId(null)}
                        >
                          {labels.btn_close_history ?? "Close"}
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
