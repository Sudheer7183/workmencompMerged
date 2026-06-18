/**
 * expressionTokenizer — Phase 7D
 *
 * Tokenises a calc rule expression string into typed tokens for the
 * ExpressionBuilder drag-and-drop canvas.
 *
 * Tokenisation rules:
 *  - Tokens matching a known FieldDescriptor.name → type: 'field'
 *  - Tokens parseable as a finite number → type: 'number'
 *  - Operator characters/strings → type: 'operator'
 *  - Anything else → type: 'unknown' (complex / unsupported)
 *
 * Round-trip guarantee:
 *  detokenize(tokenize(expression, fields)) === expression
 *  for all standard 22 calc rule expressions.
 *
 * Complex expressions (max/min function calls, nested parens) produce
 * 'unknown' tokens. hasUnknownTokens() lets the caller decide to show
 * the raw text fallback notice.
 */

export interface FieldDescriptor {
  name: string;
  label: string;
  description: string;
  data_type: string;
  category: string;
  example_value: string;
}

// ── Token types ──────────────────────────────────────────────────────────────

export type ExpressionToken =
  | { type: "field";    id: string; name: string; label: string }
  | { type: "number";   id: string; value: number; raw: string }
  | { type: "operator"; id: string; symbol: string }
  | { type: "unknown";  id: string; raw: string };

// ── Known operators ──────────────────────────────────────────────────────────

const OPERATORS = new Set([
  "+", "-", "*", "/", "(", ")", ">", "<", ">=", "<=", "==", "!=",
  "and", "or", "not",
]);

// Split pattern: split on operators while keeping them in the result
const SPLIT_REGEX = /(>=|<=|==|!=|[+\-*/()<>])/;

let _idCounter = 0;
function nextId(): string {
  return `tok_${Date.now()}_${_idCounter++}`;
}

// ── tokenize ─────────────────────────────────────────────────────────────────

/**
 * Converts a raw expression string into an array of typed tokens.
 *
 * @param expression - The raw expression string (e.g. "actual_payroll * rate_multiplier")
 * @param knownFields - The full list of FieldDescriptors from the API
 */
export function tokenize(
  expression: string,
  knownFields: FieldDescriptor[],
): ExpressionToken[] {
  if (!expression.trim()) return [];

  const fieldMap = new Map<string, FieldDescriptor>(
    knownFields.map((f) => [f.name, f])
  );

  // Split on operators, then on whitespace
  const rawParts = expression
    .split(SPLIT_REGEX)
    .flatMap((part) => part.split(/\s+/))
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  return rawParts.map((part): ExpressionToken => {
    // Check known field
    const fieldDesc = fieldMap.get(part);
    if (fieldDesc) {
      return {
        type: "field",
        id: nextId(),
        name: fieldDesc.name,
        label: fieldDesc.label,
      };
    }

    // Check operator
    if (OPERATORS.has(part)) {
      return { type: "operator", id: nextId(), symbol: part };
    }

    // Check number
    const num = parseFloat(part);
    if (!isNaN(num) && isFinite(num)) {
      return { type: "number", id: nextId(), value: num, raw: part };
    }

    // Unknown — complex / unsupported
    return { type: "unknown", id: nextId(), raw: part };
  });
}

// ── detokenize ───────────────────────────────────────────────────────────────

/**
 * Converts a token array back into a raw expression string.
 * Preserves the canonical spacing format.
 */
export function detokenize(tokens: ExpressionToken[]): string {
  const parts: string[] = [];

  tokens.forEach((token, idx) => {
    let str: string;
    switch (token.type) {
      case "field":
        str = token.name;
        break;
      case "number":
        str = token.raw;
        break;
      case "operator":
        str = token.symbol;
        break;
      case "unknown":
        str = token.raw;
        break;
    }

    // Add space before token unless it's a close paren or previous was open paren
    const prev = idx > 0 ? tokens[idx - 1] : null;
    const isOpenParen =
      token.type === "operator" && token.symbol === "(";
    const isCloseParen =
      token.type === "operator" && token.symbol === ")";
    const prevIsOpenParen =
      prev?.type === "operator" && prev.symbol === "(";

    if (idx === 0) {
      parts.push(str);
    } else if (isCloseParen || prevIsOpenParen) {
      parts.push(str);
    } else {
      parts.push(` ${str}`);
    }
  });

  return parts.join("");
}

// ── hasUnknownTokens ─────────────────────────────────────────────────────────

/**
 * Returns true if any token in the array has type 'unknown'.
 * Used to decide whether to show the complexity fallback notice.
 */
export function hasUnknownTokens(tokens: ExpressionToken[]): boolean {
  return tokens.some((t) => t.type === "unknown");
}

// ── isComplexExpression ──────────────────────────────────────────────────────

/**
 * Returns true if the expression contains function calls (e.g. abs(), max()).
 * Complex expressions cannot be fully represented in the visual builder.
 */
export function isComplexExpression(expression: string): boolean {
  // Function call pattern: word followed immediately by '('
  return /\b[a-z_]+\s*\(/.test(expression);
}

// ── validateExpression ───────────────────────────────────────────────────────

export interface ValidationError {
  /** 0-based index of the offending token in the token array */
  position: number;
  /** Human-readable display label for the token */
  tokenDisplay: string;
  /** Specific error message describing the problem */
  message: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
}

/** Arithmetic operators that cannot be consecutive or at expression boundaries */
const ARITHMETIC_OPERATORS = new Set(["+", "-", "*", "/"]);
/** All operators including comparison (cannot be the last token) */
const ALL_OPERATORS = new Set(["+", "-", "*", "/", ">", "<", ">=", "<=", "==", "!="]);

function tokenDisplay(token: ExpressionToken): string {
  switch (token.type) {
    case "field":    return token.label;
    case "number":   return token.raw;
    case "operator": return token.symbol;
    case "unknown":  return token.raw;
  }
}

/**
 * Validates an expression token array for syntactic correctness.
 *
 * Performs a single pass and collects ALL errors rather than stopping at the first.
 * Returns isValid: true only when the errors array is empty.
 *
 * Rules checked:
 *  1. Empty expression
 *  2. Expression starts with an arithmetic operator (leading - is a warning converted to error
 *     for *, /, + — leading - is excluded per spec as it may be unary minus)
 *  3. Expression ends with any arithmetic or comparison operator
 *  4. Consecutive arithmetic operators
 *  5. Consecutive field/number tokens with no operator between them
 *  6. Unbalanced parentheses
 */
export function validateExpression(tokens: ExpressionToken[]): ValidationResult {
  const errors: ValidationError[] = [];

  // Rule 1 — Empty expression
  const meaningfulTokens = tokens.filter(
    (t) => !(t.type === "unknown" && t.raw.trim() === "")
  );
  if (meaningfulTokens.length === 0) {
    errors.push({
      position: 0,
      tokenDisplay: "",
      message: "Expression is empty",
    });
    return { isValid: false, errors };
  }

  // Rule 2 — Expression starts with arithmetic operator (excluding unary minus)
  const firstToken = meaningfulTokens[0];
  if (
    firstToken.type === "operator" &&
    ARITHMETIC_OPERATORS.has(firstToken.symbol) &&
    firstToken.symbol !== "-"
  ) {
    errors.push({
      position: tokens.indexOf(firstToken),
      tokenDisplay: tokenDisplay(firstToken),
      message: `Expression cannot start with operator "${firstToken.symbol}"`,
    });
  }

  // Rule 3 — Expression ends with an operator
  const lastToken = meaningfulTokens[meaningfulTokens.length - 1];
  if (
    lastToken.type === "operator" &&
    ALL_OPERATORS.has(lastToken.symbol)
  ) {
    errors.push({
      position: tokens.indexOf(lastToken),
      tokenDisplay: tokenDisplay(lastToken),
      message: `Expression cannot end with operator "${lastToken.symbol}"`,
    });
  }

  // Rules 4 & 5 — Consecutive token checks
  let openParenCount = 0;
  let closeParenCount = 0;

  for (let i = 0; i < tokens.length; i++) {
    const current = tokens[i];
    const prev = i > 0 ? tokens[i - 1] : null;

    // Track parentheses for Rule 6
    if (current.type === "operator") {
      if (current.symbol === "(") openParenCount++;
      if (current.symbol === ")") closeParenCount++;
    }

    if (!prev) continue;

    // Rule 4 — Consecutive arithmetic operators
    if (
      current.type === "operator" &&
      ARITHMETIC_OPERATORS.has(current.symbol) &&
      prev.type === "operator" &&
      ARITHMETIC_OPERATORS.has(prev.symbol)
    ) {
      errors.push({
        position: i,
        tokenDisplay: tokenDisplay(current),
        message: `Consecutive operators "${tokenDisplay(prev)}" and "${tokenDisplay(current)}" — missing operand between them`,
      });
    }

    // Rule 5 — Consecutive field/number tokens
    const currentIsValue = current.type === "field" || current.type === "number";
    const prevIsValue = prev.type === "field" || prev.type === "number";
    if (currentIsValue && prevIsValue) {
      errors.push({
        position: i,
        tokenDisplay: tokenDisplay(current),
        message: `"${tokenDisplay(prev)}" and "${tokenDisplay(current)}" are adjacent — missing operator between them`,
      });
    }
  }

  // Rule 6 — Unbalanced parentheses
  if (openParenCount !== closeParenCount) {
    errors.push({
      position: tokens.length - 1,
      tokenDisplay: openParenCount > closeParenCount ? "(" : ")",
      message: `Unbalanced parentheses — ${openParenCount} opening and ${closeParenCount} closing`,
    });
  }

  return { isValid: errors.length === 0, errors };
}
