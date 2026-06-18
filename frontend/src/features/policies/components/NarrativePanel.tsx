/**
 * NarrativePanel — Phase 7C
 *
 * Displays the AI-generated audit narrative on the Policy Detail page.
 * Handles five display states:
 *  1. loading   — narrative is being generated
 *  2. fallback  — template narrative (amber notice)
 *  3. engine_not_run — calc engine was off when run was triggered
 *  4. not_attempted — no narrative attempt was made
 *  5. normal    — AI narrative with full text + collapse/expand
 *
 * No style={{}} props. All styling via BEM + CSS custom properties.
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";

export interface NarrativeData {
  text: string;
  is_fallback: boolean;
  provider?: string | null;
  generated_at?: string | null;
  engine_was_off?: boolean;
  not_attempted?: boolean;
}

interface NarrativePanelProps {
  narrative?: NarrativeData | null;
  isLoading?: boolean;
}

export function NarrativePanel({
  narrative,
  isLoading = false,
}: NarrativePanelProps): React.JSX.Element {
  const label = useLabels("narrative_panel");
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!narrative?.text) return;
    try {
      await navigator.clipboard.writeText(narrative.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  // ── State 1: Loading ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="narrative-panel" data-testid="narrative-panel">
        <div className="narrative-panel__header">
          <h4 className="narrative-panel__title">
            {label("title", "AI-Generated Audit Narrative")}
          </h4>
        </div>
        <div className="narrative-panel__loading">
          <span className="spinner" aria-hidden="true" />
          {label("loading", "Generating narrative…")}
        </div>
      </div>
    );
  }

  // ── State 4: Engine was off ───────────────────────────────────────────────
  if (narrative?.engine_was_off) {
    return (
      <div className="narrative-panel" data-testid="narrative-panel">
        <div className="narrative-panel__header">
          <h4 className="narrative-panel__title">
            {label("title", "AI-Generated Audit Narrative")}
          </h4>
        </div>
        <div className="narrative-panel__notice narrative-panel__notice--muted">
          ⚙ {label("engine_not_run_notice", "Enable the Calculation Engine and re-run to generate an AI narrative.")}
        </div>
      </div>
    );
  }

  // ── State 5: Not attempted ────────────────────────────────────────────────
  if (narrative?.not_attempted) {
    return (
      <div className="narrative-panel" data-testid="narrative-panel">
        <div className="narrative-panel__header">
          <h4 className="narrative-panel__title">
            {label("title", "AI-Generated Audit Narrative")}
          </h4>
        </div>
        <div className="narrative-panel__notice narrative-panel__notice--muted">
          {label("not_attempted", "Narrative generation was not attempted for this run.")}
        </div>
      </div>
    );
  }

  // ── State 0: No narrative at all ─────────────────────────────────────────
  if (!narrative?.text) {
    return (
      <div className="narrative-panel" data-testid="narrative-panel">
        <div className="narrative-panel__header">
          <h4 className="narrative-panel__title">
            {label("title", "AI-Generated Audit Narrative")}
          </h4>
        </div>
        <div className="narrative-panel__notice narrative-panel__notice--muted">
          {label("no_narrative", "No narrative available for this policy.")}
        </div>
      </div>
    );
  }

  const formattedDate = narrative.generated_at
    ? new Date(narrative.generated_at).toLocaleString()
    : null;

  // ── State 2: Fallback (amber notice) + text ──────────────────────────────
  // ── State 3: Normal (full AI text) ──────────────────────────────────────
  return (
    <div className="narrative-panel" data-testid="narrative-panel">
      <div className="narrative-panel__header">
        <h4 className="narrative-panel__title">
          {label("title", "AI-Generated Audit Narrative")}
        </h4>
        <div className="narrative-panel__meta">
          {formattedDate && (
            <span>
              {label("generated_at_prefix", "Generated:")} {formattedDate}
            </span>
          )}
          {narrative.provider && (
            <span className="narrative-panel__provider-badge">
              {label("provider_badge_prefix", "via")} {narrative.provider}
            </span>
          )}
        </div>
      </div>

      {/* Fallback amber notice */}
      {narrative.is_fallback && (
        <div className="narrative-panel__notice narrative-panel__notice--amber">
          ⚠ {label(
            "fallback_notice",
            "This narrative was generated using a template because the AI service was unavailable."
          )}
        </div>
      )}

      {/* Narrative body */}
      <div
        className={`narrative-panel__body${isCollapsed ? " narrative-panel__body--collapsed" : ""}`}
        data-testid="narrative-body"
      >
        {narrative.text}
      </div>

      {/* Actions */}
      <div className="narrative-panel__actions">
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => setIsCollapsed((c) => !c)}
          type="button"
          data-testid="btn-toggle-narrative"
        >
          {isCollapsed
            ? label("btn_show_full", "Show Full Narrative ▼")
            : label("btn_collapse", "Collapse ▲")}
        </button>
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => void handleCopy()}
          type="button"
          data-testid="btn-copy-narrative"
        >
          {copied
            ? label("btn_copied", "Copied!")
            : label("btn_copy", "Copy to Clipboard")}
        </button>
      </div>
    </div>
  );
}
