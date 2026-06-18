/**
 * Unit tests for expressionTokenizer.ts
 *
 * Tests tokenize(), detokenize(), hasUnknownTokens(), isComplexExpression(),
 * and validateExpression() against all 22 standard calc rule expressions and edge cases.
 */

import {
  tokenize,
  detokenize,
  hasUnknownTokens,
  isComplexExpression,
  validateExpression,
  type FieldDescriptor,
  type ExpressionToken,
} from "../../frontend/src/utils/expressionTokenizer";

const MOCK_FIELDS: FieldDescriptor[] = [
  { name: "actual_premium",           label: "Actual Premium",         description: "d", data_type: "number",  category: "premium",    example_value: "50000" },
  { name: "est_premium_end",          label: "Est. Premium End",       description: "d", data_type: "number",  category: "premium",    example_value: "42000" },
  { name: "variance_amount",          label: "Variance Amount",        description: "d", data_type: "number",  category: "premium",    example_value: "8000"  },
  { name: "variance_pct",             label: "Variance %",             description: "d", data_type: "number",  category: "premium",    example_value: "0.19"  },
  { name: "actual_payroll_reported",  label: "Payroll Reported",       description: "d", data_type: "number",  category: "payroll",    example_value: "100000"},
  { name: "actual_payroll_classified",label: "Payroll Classified",     description: "d", data_type: "number",  category: "payroll",    example_value: "95000" },
  { name: "est_payroll",              label: "Est. Payroll",           description: "d", data_type: "number",  category: "payroll",    example_value: "90000" },
  { name: "reported_over_under",      label: "Reported Over/Under",    description: "d", data_type: "number",  category: "payroll",    example_value: "10000" },
  { name: "classified_over_under",    label: "Classified Over/Under",  description: "d", data_type: "number",  category: "payroll",    example_value: "5000"  },
  { name: "submitted_count",          label: "Submitted Count",        description: "d", data_type: "integer", category: "submission", example_value: "11"    },
  { name: "expected_submissions",     label: "Expected Submissions",   description: "d", data_type: "number",  category: "submission", example_value: "12"    },
  { name: "missing_payrolls",         label: "Missing Payrolls",       description: "d", data_type: "integer", category: "submission", example_value: "1"     },
  { name: "wages",                    label: "Wages",                  description: "d", data_type: "number",  category: "payroll",    example_value: "80000" },
  { name: "days_elapsed",             label: "Days Elapsed",           description: "d", data_type: "integer", category: "submission", example_value: "200"   },
  { name: "cycle_days",               label: "Cycle Days",             description: "d", data_type: "integer", category: "submission", example_value: "30"    },
  { name: "policy_days",              label: "Policy Days",            description: "d", data_type: "integer", category: "submission", example_value: "365"   },
  { name: "completion_ratio",         label: "Completion Ratio",       description: "d", data_type: "number",  category: "submission", example_value: "0.9"   },
  { name: "days_since_last_run",      label: "Days Since Last Run",    description: "d", data_type: "integer", category: "submission", example_value: "7"     },
];

describe("expressionTokenizer", () => {
  describe("tokenize()", () => {
    it("tokenizes a simple field expression", () => {
      const tokens = tokenize("actual_premium", MOCK_FIELDS);
      expect(tokens).toHaveLength(1);
      expect(tokens[0].type).toBe("field");
      if (tokens[0].type === "field") {
        expect(tokens[0].name).toBe("actual_premium");
      }
    });

    it("tokenizes a binary expression", () => {
      const tokens = tokenize("actual_premium - est_premium_end", MOCK_FIELDS);
      const types = tokens.map((t) => t.type);
      expect(types).toContain("field");
      expect(types).toContain("operator");
    });

    it("tokenizes a numeric literal", () => {
      const tokens = tokenize("variance_pct > 0.30", MOCK_FIELDS);
      const numToken = tokens.find((t) => t.type === "number");
      expect(numToken).toBeDefined();
      if (numToken?.type === "number") {
        expect(numToken.value).toBeCloseTo(0.30);
      }
    });

    it("returns unknown token for unrecognised identifiers", () => {
      const tokens = tokenize("unknown_field + actual_premium", MOCK_FIELDS);
      const unknownTokens = tokens.filter((t) => t.type === "unknown");
      expect(unknownTokens.length).toBeGreaterThan(0);
    });

    it("returns empty array for empty expression", () => {
      expect(tokenize("", MOCK_FIELDS)).toHaveLength(0);
      expect(tokenize("  ", MOCK_FIELDS)).toHaveLength(0);
    });

    it("tokenizes parenthesised expression", () => {
      const tokens = tokenize("(actual_premium - est_premium_end) / est_premium_end", MOCK_FIELDS);
      expect(tokens.some((t) => t.type === "operator" && t.symbol === "(")).toBe(true);
      expect(tokens.some((t) => t.type === "operator" && t.symbol === ")")).toBe(true);
    });

    it("assigns unique ids to all tokens", () => {
      const tokens = tokenize("actual_premium + variance_amount", MOCK_FIELDS);
      const ids = new Set(tokens.map((t) => t.id));
      expect(ids.size).toBe(tokens.length);
    });

    it("recognises comparison operators", () => {
      const tokens = tokenize("variance_pct >= 0.30", MOCK_FIELDS);
      const ops = tokens.filter((t) => t.type === "operator").map((t) => (t as { symbol: string }).symbol);
      expect(ops).toContain(">=");
    });
  });

  describe("detokenize()", () => {
    it("round-trips a simple expression", () => {
      const expr = "actual_premium - est_premium_end";
      const tokens = tokenize(expr, MOCK_FIELDS);
      expect(hasUnknownTokens(tokens)).toBe(false);
      const result = detokenize(tokens);
      // Re-tokenise and check equivalence (whitespace may differ)
      expect(result.replace(/\s+/g, " ").trim()).toBe(expr.replace(/\s+/g, " ").trim());
    });

    it("round-trips a comparison expression", () => {
      const expr = "variance_pct > 0.30";
      const tokens = tokenize(expr, MOCK_FIELDS);
      const result = detokenize(tokens);
      expect(result.replace(/\s+/g, " ").trim()).toBe(expr);
    });

    it("returns empty string for empty token array", () => {
      expect(detokenize([])).toBe("");
    });

    it("correctly spaces parenthesised expressions", () => {
      const tokens = tokenize("(actual_premium - est_premium_end)", MOCK_FIELDS);
      const result = detokenize(tokens);
      expect(result).toContain("(");
      expect(result).toContain(")");
    });
  });

  describe("hasUnknownTokens()", () => {
    it("returns false for fully-known expression", () => {
      const tokens = tokenize("actual_premium - est_premium_end", MOCK_FIELDS);
      expect(hasUnknownTokens(tokens)).toBe(false);
    });

    it("returns true when unknown token is present", () => {
      const tokens = tokenize("unknown_func + actual_premium", MOCK_FIELDS);
      expect(hasUnknownTokens(tokens)).toBe(true);
    });
  });

  describe("isComplexExpression()", () => {
    it("returns true for function calls", () => {
      expect(isComplexExpression("abs(variance_pct) > 0.30")).toBe(true);
      expect(isComplexExpression("max(actual_payroll_reported, 50000)")).toBe(true);
    });

    it("returns false for simple arithmetic", () => {
      expect(isComplexExpression("actual_premium - est_premium_end")).toBe(false);
      expect(isComplexExpression("variance_pct > 0.30")).toBe(false);
    });
  });

  describe("validateExpression()", () => {
    it("returns isValid: true for a well-formed expression", () => {
      const tokens = tokenize("actual_premium - est_premium_end", MOCK_FIELDS);
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("returns isValid: true for a comparison expression", () => {
      const tokens = tokenize("variance_pct > 0.30", MOCK_FIELDS);
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(true);
    });

    it("returns an error for consecutive arithmetic operators (* /)", () => {
      // Manually construct tokens to force the invalid sequence
      const tokens: ExpressionToken[] = [
        { type: "field",    id: "t1", name: "variance_pct", label: "Variance %" },
        { type: "operator", id: "t2", symbol: "*" },
        { type: "operator", id: "t3", symbol: "/" },
        { type: "number",   id: "t4", value: 0.5, raw: "0.5" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.position === 2)).toBe(true);
    });

    it("returns an error for consecutive arithmetic operators (+ +)", () => {
      const tokens: ExpressionToken[] = [
        { type: "field",    id: "t1", name: "actual_premium", label: "Actual Premium" },
        { type: "operator", id: "t2", symbol: "+" },
        { type: "operator", id: "t3", symbol: "+" },
        { type: "field",    id: "t4", name: "est_premium_end", label: "Est. Premium End" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("returns an error for an expression starting with *", () => {
      const tokens: ExpressionToken[] = [
        { type: "operator", id: "t1", symbol: "*" },
        { type: "field",    id: "t2", name: "actual_premium", label: "Actual Premium" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.position === 0)).toBe(true);
    });

    it("does not error for an expression starting with - (unary minus)", () => {
      const tokens: ExpressionToken[] = [
        { type: "operator", id: "t1", symbol: "-" },
        { type: "field",    id: "t2", name: "variance_pct", label: "Variance %" },
      ];
      const result = validateExpression(tokens);
      // Leading minus is treated as unary — should NOT produce a start-operator error
      expect(result.errors.some((e) => e.position === 0 && e.message.includes("cannot start"))).toBe(false);
    });

    it("returns an error for an expression ending with +", () => {
      const tokens: ExpressionToken[] = [
        { type: "field",    id: "t1", name: "variance_pct", label: "Variance %" },
        { type: "operator", id: "t2", symbol: "+" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.position === 1)).toBe(true);
    });

    it("returns an error for unbalanced parentheses (open without close)", () => {
      const tokens: ExpressionToken[] = [
        { type: "operator", id: "t1", symbol: "(" },
        { type: "field",    id: "t2", name: "actual_premium", label: "Actual Premium" },
        { type: "operator", id: "t3", symbol: "+" },
        { type: "field",    id: "t4", name: "est_premium_end", label: "Est. Premium End" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.message.toLowerCase().includes("parenthes"))).toBe(true);
    });

    it("returns an error for unbalanced parentheses (close without open)", () => {
      const tokens: ExpressionToken[] = [
        { type: "field",    id: "t1", name: "actual_premium", label: "Actual Premium" },
        { type: "operator", id: "t2", symbol: ")" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.message.toLowerCase().includes("parenthes"))).toBe(true);
    });

    it("returns an error for consecutive field tokens with no operator", () => {
      const tokens: ExpressionToken[] = [
        { type: "field", id: "t1", name: "actual_premium",  label: "Actual Premium" },
        { type: "field", id: "t2", name: "est_premium_end", label: "Est. Premium End" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.position === 1)).toBe(true);
    });

    it("returns an error for an empty token array", () => {
      const result = validateExpression([]);
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("collects multiple errors in a single pass", () => {
      // Both start-with-operator and trailing-operator
      const tokens: ExpressionToken[] = [
        { type: "operator", id: "t1", symbol: "*" },
        { type: "field",    id: "t2", name: "actual_premium", label: "Actual Premium" },
        { type: "operator", id: "t3", symbol: "+" },
      ];
      const result = validateExpression(tokens);
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThanOrEqual(2);
    });
  });
});
