/**
 * ExpressionBuilder — Phase 7D (Bug-fix revision)
 *
 * Visual drag-and-drop builder for calc rule expressions.
 * Uses @dnd-kit/core and @dnd-kit/sortable.
 *
 * Architecture:
 *  - Left panel: field pills (useDraggable — palette sources, not sortable peers)
 *  - Canvas: SortableContext wrapping canvas tokens ONLY (canvasIds only)
 *  - Operator buttons: click to append
 *  - Raw expression display (read-only, kept in sync)
 *  - Toggle to switch between builder and raw textarea
 *  - Inline validation errors below the canvas
 *
 * No style={{}} props for visual styling. All via BEM classes and CSS vars.
 */

import React, { useState, useMemo, useCallback } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useLabels } from "@/hooks/useLabels";
import {
  ExpressionToken,
  FieldDescriptor,
  tokenize,
  detokenize,
  hasUnknownTokens,
  isComplexExpression,
  validateExpression,
} from "@/utils/expressionTokenizer";

const OPERATORS = ["+", "-", "*", "/", "(", ")", ">", "<", ">=", "<=", "=="];

// ── DraggableFieldPill ────────────────────────────────────────────────────────
// Uses useDraggable (not useSortable) — field pills are drag sources from the
// palette, they are not sortable peers within the canvas SortableContext.

function DraggableFieldPill({
  field,
}: {
  field: FieldDescriptor;
}): React.JSX.Element {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `source-${field.name}`,
    data: { type: "source-field", field },
  });

  return (
    <div
      ref={setNodeRef}
      className={`expression-builder__field-pill${isDragging ? " expression-builder__field-pill--dragging" : ""}`}
      title={`${field.description}\nExample: ${field.example_value}`}
      {...attributes}
      {...listeners}
    >
      <span>{field.label}</span>
    </div>
  );
}

// ── SortableToken ─────────────────────────────────────────────────────────────

function SortableToken({
  token,
  onRemove,
  isInvalid,
}: {
  token: ExpressionToken;
  onRemove: (id: string) => void;
  isInvalid: boolean;
}): React.JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: token.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const typeClass = `expression-builder__token--${token.type}`;
  const invalidClass = isInvalid ? " expression-builder__token--invalid" : "";
  const display =
    token.type === "field"
      ? token.label
      : token.type === "number"
      ? token.raw
      : token.type === "operator"
      ? token.symbol
      : token.raw;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`expression-builder__token ${typeClass}${invalidClass}`}
      {...attributes}
      {...listeners}
    >
      <span>{display}</span>
      <button
        className="expression-builder__token-remove"
        onClick={() => onRemove(token.id)}
        type="button"
        aria-label={`Remove ${display}`}
        onPointerDown={(e) => e.stopPropagation()}
      >
        ✕
      </button>
    </div>
  );
}

// ── Canvas droppable wrapper ──────────────────────────────────────────────────

function CanvasDropZone({
  children,
  isEmpty,
  hintText,
}: {
  children: React.ReactNode;
  isEmpty: boolean;
  hintText: string;
}): React.JSX.Element {
  const { isOver, setNodeRef } = useDroppable({ id: "canvas-drop-zone" });

  return (
    <div
      ref={setNodeRef}
      className={`expression-builder__canvas-tokens${
        isOver ? " expression-builder__canvas-tokens--active-drop" : ""
      }`}
      data-testid="expression-canvas"
    >
      {isEmpty ? (
        <span className="expression-builder__canvas-hint">{hintText}</span>
      ) : (
        children
      )}
    </div>
  );
}

// ── ExpressionBuilder ─────────────────────────────────────────────────────────

interface ExpressionBuilderProps {
  /** Current raw expression string */
  expressionRaw: string;
  /** Called with the new raw expression on every token change */
  onExpressionChange: (raw: string) => void;
  /** Full list of available fields from the API */
  fields: FieldDescriptor[];
  /** If true, shows the raw textarea instead of the visual builder */
  isRawMode: boolean;
  /** Called to switch between modes */
  onToggleMode: () => void;
  /** If true, available-fields are still loading — show a skeleton in the field panel */
  isFieldsLoading?: boolean;
}

export function ExpressionBuilder({
  expressionRaw,
  onExpressionChange,
  fields,
  isRawMode,
  onToggleMode,
  isFieldsLoading = false,
}: ExpressionBuilderProps): React.JSX.Element {
  const label = useLabels("calc_rule_builder");
  const [fieldSearch, setFieldSearch] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  // Tokenise the current expression
  const tokens: ExpressionToken[] = useMemo(
    () => tokenize(expressionRaw, fields),
    [expressionRaw, fields]
  );

  const isComplex = isComplexExpression(expressionRaw);
  const hasUnknown = hasUnknownTokens(tokens);

  // Derived validation — pure computation, no useState
  const validationResult = validateExpression(tokens);
  const invalidPositions = new Set(validationResult.errors.map((e) => e.position));

  // Group fields by category for the left panel
  const groupedFields = useMemo(() => {
    const q = fieldSearch.toLowerCase();
    const filtered = fields.filter(
      (f) =>
        !q ||
        f.label.toLowerCase().includes(q) ||
        f.name.toLowerCase().includes(q)
    );
    const groups: Record<string, FieldDescriptor[]> = {};
    for (const f of filtered) {
      if (!groups[f.category]) groups[f.category] = [];
      groups[f.category].push(f);
    }
    return groups;
  }, [fields, fieldSearch]);

  const categoryLabel: Record<string, string> = {
    payroll: label("category_payroll", "Payroll"),
    premium: label("category_premium", "Premium"),
    class_code: label("category_class_code", "Class Code"),
    officer: label("category_officer", "Officer"),
    submission: label("category_submission", "Submission"),
  };

  const removeToken = useCallback(
    (id: string) => {
      const next = tokens.filter((t) => t.id !== id);
      onExpressionChange(detokenize(next));
    },
    [tokens, onExpressionChange]
  );

  const appendOperator = useCallback(
    (symbol: string) => {
      const opToken: ExpressionToken = {
        type: "operator",
        id: `tok_${Date.now()}`,
        symbol,
      };
      const next = [...tokens, opToken];
      onExpressionChange(detokenize(next));
    },
    [tokens, onExpressionChange]
  );

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;

    const activeData = event.active.data.current as { type?: string; field?: FieldDescriptor };

    // Dropping from field panel onto canvas
    if (activeData?.type === "source-field" && activeData.field) {
      const fieldDesc = activeData.field;
      const newToken: ExpressionToken = {
        type: "field",
        id: `tok_${Date.now()}`,
        name: fieldDesc.name,
        label: fieldDesc.label,
      };

      // Insert at the position of the 'over' token, or append if dropped on canvas zone
      if (String(over.id) === "canvas-drop-zone") {
        const next = [...tokens, newToken];
        onExpressionChange(detokenize(next));
      } else {
        // Insert before the over token
        const overIdx = tokens.findIndex((t) => t.id === String(over.id));
        if (overIdx !== -1) {
          const next = [...tokens];
          next.splice(overIdx, 0, newToken);
          onExpressionChange(detokenize(next));
        } else {
          onExpressionChange(detokenize([...tokens, newToken]));
        }
      }
      return;
    }

    // Reordering within the canvas
    if (String(active.id) !== String(over.id)) {
      const oldIdx = tokens.findIndex((t) => t.id === String(active.id));
      const newIdx = tokens.findIndex((t) => t.id === String(over.id));
      if (oldIdx !== -1 && newIdx !== -1) {
        const reordered = arrayMove(tokens, oldIdx, newIdx);
        onExpressionChange(detokenize(reordered));
      }
    }
  }

  // The toggle row is always shown so the user can switch modes
  const toggleRow = (
    <div className="expression-builder__toggle-row">
      <button
        className="btn btn--ghost btn--sm"
        onClick={onToggleMode}
        type="button"
        data-testid="btn-switch-mode"
      >
        {isRawMode
          ? label("btn_switch_to_builder", "↔ Switch to Builder")
          : label("btn_switch_to_raw", "↔ Switch to Raw Text")}
      </button>
    </div>
  );

  if (isRawMode) {
    return <div className="expression-builder">{toggleRow}</div>;
  }

  // Show complex notice if the expression can't be fully rendered
  const complexNotice =
    isComplex || hasUnknown ? (
      <div className="expression-builder__complex-notice" data-testid="complex-notice">
        ⚠ {label(
          "complex_expression_notice",
          "This expression is too complex for the visual builder. Edit it in raw text mode."
        )}
      </div>
    ) : null;

  // Canvas-only sortable ids — field pills are NOT included here
  const canvasIds = tokens.map((t) => t.id);

  return (
    <div className="expression-builder" data-testid="expression-builder">
      {toggleRow}

      {complexNotice}

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="expression-builder__layout">
          {/* Left panel: available fields — pills use useDraggable, not inside SortableContext */}
          <div className="expression-builder__fields">
            <h4 className="expression-builder__fields-title">
              {label("section_fields", "Available Fields")}
            </h4>
            <input
              className="input expression-builder__fields-search"
              type="search"
              placeholder={label("search_placeholder", "Search fields…")}
              value={fieldSearch}
              onChange={(e) => setFieldSearch(e.target.value)}
              data-testid="field-search"
            />
            {isFieldsLoading ? (
              <div className="expression-builder__fields-loading" data-testid="fields-loading-state">
                <div className="skeleton expression-builder__fields-skeleton" />
                <div className="skeleton expression-builder__fields-skeleton" />
                <div className="skeleton expression-builder__fields-skeleton" />
              </div>
            ) : Object.keys(groupedFields).length === 0 ? (
              <div className="expression-builder__fields-empty" data-testid="fields-empty-state">
                {label("no_fields_available", "No fields available")}
              </div>
            ) : (
              Object.entries(groupedFields).map(([cat, catFields]) => (
                <div key={cat}>
                  <div className="expression-builder__category">
                    {categoryLabel[cat] ?? cat}
                  </div>
                  {catFields.map((field) => (
                    <DraggableFieldPill key={field.name} field={field} />
                  ))}
                </div>
              ))
            )}
          </div>

          {/* Right: canvas + operators — SortableContext wraps canvas tokens ONLY */}
          <div className="expression-builder__canvas">
            <h4 className="expression-builder__canvas-title">
              {label("section_canvas", "Expression Canvas")}
            </h4>

            <SortableContext items={canvasIds} strategy={horizontalListSortingStrategy}>
              <CanvasDropZone
                isEmpty={tokens.length === 0}
                hintText={label("drop_hint", "Drag fields here to build your expression")}
              >
                {tokens.map((token, idx) => (
                  <SortableToken
                    key={token.id}
                    token={token}
                    onRemove={removeToken}
                    isInvalid={invalidPositions.has(idx)}
                  />
                ))}
              </CanvasDropZone>
            </SortableContext>

            {/* Inline validation errors */}
            {validationResult.errors.length > 0 && (
              <div
                className="expression-builder__validation-errors"
                data-testid="validation-errors"
                role="alert"
                aria-label={label("validation_errors_heading", "Expression errors must be resolved before saving")}
              >
                {validationResult.errors.map((err, i) => (
                  <div
                    key={i}
                    className="expression-builder__validation-error"
                    data-testid={`validation-error-${i}`}
                  >
                    {err.message}
                  </div>
                ))}
              </div>
            )}

            {/* Operator buttons */}
            <div>
              <h4 className="expression-builder__canvas-title">
                {label("section_operators", "Operators")}
              </h4>
              <div className="expression-builder__operators">
                {OPERATORS.map((op) => (
                  <button
                    key={op}
                    className="expression-builder__operator-btn"
                    onClick={() => appendOperator(op)}
                    type="button"
                    data-testid={`op-btn-${op}`}
                  >
                    {op}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Drag overlay */}
        <DragOverlay>
          {activeId ? (
            <div className="expression-builder__token expression-builder__token--field">
              {activeId.startsWith("source-")
                ? fields.find((f) => `source-${f.name}` === activeId)?.label ?? activeId
                : tokens.find((t) => t.id === activeId)?.type === "field"
                ? (tokens.find((t) => t.id === activeId) as { label: string })?.label
                : activeId}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Raw expression display */}
      <div className="expression-builder__raw">
        <p className="expression-builder__raw-label">
          {label("section_expression", "Expression (raw)")}
        </p>
        <code className="expression-builder__raw-display" data-testid="raw-expression-display">
          {expressionRaw || "—"}
        </code>
      </div>
    </div>
  );
}
