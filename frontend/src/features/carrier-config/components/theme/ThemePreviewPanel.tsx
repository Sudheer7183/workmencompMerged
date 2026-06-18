/**
 * ThemePreviewPanel — Phase 6 Theme Editor component.
 *
 * Addendum S6.3: Miniaturised live preview of the platform UI using the
 * theme tokens currently being edited. All colours are applied via inline
 * style referencing the token values directly — the preview reflects the
 * draft tokens before they are saved.
 *
 * Sections:
 *   - Nav bar sample
 *   - KPI stat card
 *   - Data row with positive/negative variance values
 *   - Risk badges (High / Medium / Low)
 *   - Status badges (Active / Cancelled)
 *   - AI Narrative card snippet
 */

import React from "react";

export interface PreviewTokens {
  bg: string;
  surface: string;
  surface2: string;
  border_col: string;
  text_primary: string;
  text_muted: string;
  brand: string;
  brand_dark: string;
  accent: string;
  color_green: string;
  color_amber: string;
  color_red: string;
  color_blue: string;
}

interface ThemePreviewPanelProps {
  tokens: PreviewTokens;
}

export function ThemePreviewPanel({ tokens }: ThemePreviewPanelProps): React.JSX.Element {
  const hex = (t: string) => `#${t}`;

  return (
    <div
      className="theme-preview-panel"
      style={{
        backgroundColor: hex(tokens.bg),
        borderColor: hex(tokens.border_col),
      }}
      aria-label="Live theme preview"
    >
      {/* Nav bar */}
      <div
        className="theme-preview-panel__nav"
        style={{
          backgroundColor: hex(tokens.surface2),
          color: hex(tokens.text_primary),
          borderBottom: `1px solid ${hex(tokens.border_col)}`,
        }}
      >
        <span style={{ color: hex(tokens.brand), fontWeight: 600, fontSize: "0.75rem" }}>
          ◆ Portal
        </span>
        <span style={{ color: hex(tokens.text_muted), fontSize: "0.65rem" }}>Dashboard</span>
        <span style={{ color: hex(tokens.text_muted), fontSize: "0.65rem" }}>Policies</span>
        <span style={{ marginLeft: "auto", color: hex(tokens.brand_dark), fontSize: "0.65rem" }}>
          Admin
        </span>
      </div>

      {/* KPI card */}
      <div
        className="theme-preview-panel__kpi"
        style={{
          backgroundColor: hex(tokens.surface),
          borderColor: hex(tokens.border_col),
          color: hex(tokens.text_primary),
        }}
      >
        <div className="theme-preview-panel__kpi-label" style={{ color: hex(tokens.text_muted) }}>
          Total Book Premium
        </div>
        <div className="theme-preview-panel__kpi-value" style={{ color: hex(tokens.brand) }}>
          $4,821,440
        </div>
      </div>

      {/* Data row */}
      <div
        style={{
          padding: "var(--space-2) var(--space-3)",
          backgroundColor: hex(tokens.surface),
          borderRadius: "4px",
          borderLeft: `3px solid ${hex(tokens.border_col)}`,
          fontSize: "0.7rem",
          display: "flex",
          gap: "var(--space-3)",
          alignItems: "center",
        }}
      >
        <span style={{ color: hex(tokens.text_primary) }}>POL-0042</span>
        <span style={{ color: hex(tokens.text_muted) }}>Acme Corp</span>
        <span style={{ color: hex(tokens.color_green), marginLeft: "auto" }}>+12.4%</span>
        <span style={{ color: hex(tokens.color_red) }}>-8.1%</span>
      </div>

      {/* Risk + status badges */}
      <div className="theme-preview-panel__badges">
        <span
          className="theme-preview-panel__badge"
          style={{
            backgroundColor: `${hex(tokens.color_red)}22`,
            color: hex(tokens.color_red),
          }}
        >
          High
        </span>
        <span
          className="theme-preview-panel__badge"
          style={{
            backgroundColor: `${hex(tokens.color_amber)}22`,
            color: hex(tokens.color_amber),
          }}
        >
          Medium
        </span>
        <span
          className="theme-preview-panel__badge"
          style={{
            backgroundColor: `${hex(tokens.color_green)}22`,
            color: hex(tokens.color_green),
          }}
        >
          Low
        </span>
        <span
          className="theme-preview-panel__badge"
          style={{
            backgroundColor: `${hex(tokens.color_green)}22`,
            color: hex(tokens.color_green),
          }}
        >
          Active
        </span>
        <span
          className="theme-preview-panel__badge"
          style={{
            backgroundColor: `${hex(tokens.color_red)}22`,
            color: hex(tokens.color_red),
          }}
        >
          Cancelled
        </span>
      </div>

      {/* AI Narrative card */}
      <div
        style={{
          padding: "var(--space-2) var(--space-3)",
          backgroundColor: hex(tokens.surface2),
          borderRadius: "4px",
          borderLeft: `3px solid ${hex(tokens.accent)}`,
        }}
      >
        <div style={{ fontSize: "0.65rem", color: hex(tokens.accent), marginBottom: "3px" }}>
          AI Narrative
        </div>
        <div style={{ fontSize: "0.65rem", color: hex(tokens.text_muted), lineHeight: 1.4 }}>
          Policy shows a 12.4% variance above threshold. Recommend audit review.
        </div>
      </div>
    </div>
  );
}
