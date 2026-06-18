/**
 * StateMultiSelect — Multi-select state filter dropdown.
 *
 * Replaces the single <select> in the state/risk bar chart. Allows multiple
 * state codes to be selected simultaneously.
 *
 * Constraints:
 *  - At least one state must always be selected (deselecting all is blocked)
 *  - Click-outside-to-close via mousedown listener on document
 *  - No style={{}} for visual properties — all via BEM + CSS variables
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLabels } from "@/hooks/useLabels";

interface StateMultiSelectProps {
  /** All available state codes to show as options */
  options: string[];
  /** Currently selected state codes */
  selected: Set<string>;
  /** Called on every toggle with the new full selection set */
  onChange: (next: Set<string>) => void;
}

export function StateMultiSelect({
  options,
  selected,
  onChange,
}: StateMultiSelectProps): React.JSX.Element {
  const labelFn = useLabels("dashboard");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    function handleMouseDown(e: MouseEvent): void {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [open]);

  const allSelected = options.every((s) => selected.has(s));

  const triggerLabel: string = (() => {
    if (selected.size === 0 || allSelected) {
      return labelFn("state_filter_all_label", "All States");
    }
    if (selected.size === 1) {
      return [...selected][0];
    }
    return `${selected.size} states`;
  })();

  const toggleState = useCallback(
    (code: string): void => {
      // Block removing the last selected state
      if (selected.has(code) && selected.size === 1) return;
      const next = new Set(selected);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      onChange(next);
    },
    [selected, onChange]
  );

  const toggleAll = useCallback((): void => {
    if (allSelected) {
      // Keep at least the first one selected
      onChange(new Set(options.slice(0, 1)));
    } else {
      onChange(new Set(options));
    }
  }, [allSelected, options, onChange]);

  return (
    <div
      ref={containerRef}
      className={`state-multi-select${open ? " state-multi-select--open" : ""}`}
      data-testid="state-multi-select"
    >
      <button
        className="state-multi-select__trigger"
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="state-multi-select__trigger-label">{triggerLabel}</span>
        <span className="state-multi-select__chevron" aria-hidden="true">▾</span>
      </button>

      {open && (
        <div className="state-multi-select__dropdown" role="listbox" aria-multiselectable="true">
          {/* Select All / Deselect All row */}
          <label className="state-multi-select__row state-multi-select__row--select-all">
            <input
              type="checkbox"
              className="state-multi-select__checkbox"
              checked={allSelected}
              onChange={toggleAll}
            />
            <span>{labelFn("state_filter_select_all", "Select All")}</span>
          </label>

          <div className="state-multi-select__divider" role="separator" />

          {options.length === 0 ? (
            <div className="state-multi-select__empty">
              {labelFn("state_filter_placeholder", "Filter states…")}
            </div>
          ) : (
            options.map((code) => (
              <label
                key={code}
                className="state-multi-select__row"
                role="option"
                aria-selected={selected.has(code)}
              >
                <input
                  type="checkbox"
                  className="state-multi-select__checkbox"
                  checked={selected.has(code)}
                  onChange={() => toggleState(code)}
                />
                <span>{code}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
}
