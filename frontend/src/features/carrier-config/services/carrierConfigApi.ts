/**
 * carrier-config/services/carrierConfigApi.ts
 *
 * All API calls for the Carrier Configuration Hub (Phase 3).
 * Covers: calc engine config, calc rules CRUD + workflow.
 */

import axios from "axios";

// ── Types ────────────────────────────────────────────────────────────────────

export interface CalcRule {
  rule_id: number;
  carrier_id: number;
  rule_key: string;
  rule_label: string;
  rule_description: string | null;
  expression: string;
  is_editable: boolean;
  rule_status: "DRAFT" | "PENDING_REVIEW" | "ACTIVE" | "DEACTIVATED";
  submitted_by: string | null;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  effective_from: string;
}

export interface RuleHistoryEntry {
  id: number;
  rule_id: number;
  carrier_id: number;
  previous_status: string;
  new_status: string;
  changed_by: string;
  expression_snapshot: string | null;
  changed_at: string;
}

export interface ExpressionTestResult {
  result: unknown;
  error: string | null;
  evaluated_expression: string;
}

export interface AISuggestResult {
  suggested_expression: string;
  explanation: string;
}

// ── Calc Rules API ───────────────────────────────────────────────────────────

export async function fetchCalcRules(carrierId: number): Promise<CalcRule[]> {
  const { data } = await axios.get<CalcRule[]>(
    `/api/v1/admin/calc-rules?carrier_id=${carrierId}`
  );
  return data;
}

export async function updateRuleExpression(
  ruleId: number,
  expression: string
): Promise<CalcRule> {
  const { data } = await axios.put<CalcRule>(`/api/v1/admin/calc-rules/${ruleId}`, {
    expression,
  });
  return data;
}

export async function submitRuleForReview(ruleId: number): Promise<CalcRule> {
  const { data } = await axios.post<CalcRule>(
    `/api/v1/admin/calc-rules/${ruleId}/submit`
  );
  return data;
}

export async function approveRule(ruleId: number): Promise<CalcRule> {
  const { data } = await axios.post<CalcRule>(
    `/api/v1/admin/calc-rules/${ruleId}/approve`
  );
  return data;
}

export async function revertRule(ruleId: number): Promise<CalcRule> {
  const { data } = await axios.post<CalcRule>(
    `/api/v1/admin/calc-rules/${ruleId}/revert`
  );
  return data;
}

export async function deactivateRule(ruleId: number): Promise<CalcRule> {
  const { data } = await axios.post<CalcRule>(
    `/api/v1/admin/calc-rules/${ruleId}/deactivate`
  );
  return data;
}

export async function fetchRuleHistory(ruleId: number): Promise<RuleHistoryEntry[]> {
  const { data } = await axios.get<RuleHistoryEntry[]>(
    `/api/v1/admin/calc-rules/${ruleId}/history`
  );
  return data;
}

export async function testExpression(
  expression: string,
  carrierId: number,
  sampleValues: Record<string, unknown>
): Promise<ExpressionTestResult> {
  const { data } = await axios.post<ExpressionTestResult>(
    `/api/v1/admin/calc-rules/test-expression`,
    { expression, carrier_id: carrierId, sample_values: sampleValues }
  );
  return data;
}

export async function suggestExpression(
  description: string,
  carrierId: number
): Promise<AISuggestResult> {
  const { data } = await axios.post<AISuggestResult>(
    `/api/v1/admin/calc-rules/ai-suggest`,
    { description, carrier_id: carrierId }
  );
  return data;
}
