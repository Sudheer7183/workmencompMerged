/**
 * ThemeEditor — Phase 6 Theme Tab component.
 *
 * Addendum S6: 3-column layout for editing all 13 CSS token values.
 *
 * Column 1 (40%): Token Editor — 4 groups of colour pickers
 *   - Background Tones (bg, surface, surface2)
 *   - Text & Borders (border_col, text_primary, text_muted)
 *   - Brand Colours (brand, brand_dark, accent)
 *   - Status Colours (color_green, color_amber, color_red, color_blue)
 *
 * Column 2 (40%): Live ThemePreviewPanel
 *
 * Column 3 (20%): Metadata — theme name, mode badge, based-on,
 *   WCAG contrast indicator (text_primary over surface ratio).
 *
 * The WCAG check is non-blocking (amber warning) per Addendum S6.4.
 */

import React, { useState } from "react";
import { ColorPickerInput } from "./ColorPickerInput";
import { ThemePreviewPanel, type PreviewTokens } from "./ThemePreviewPanel";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ThemeTokenValues {
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

export interface ThemeEditorProps {
  /** Initial token values and metadata. */
  initial: ThemeTokenValues & {
    theme_name: string;
    mode: string;
    based_on_name: string | null;
  };
  /** Called when user clicks Save. */
  onSave: (name: string, tokens: ThemeTokenValues) => void;
  /** Called when user dismisses the editor. */
  onCancel: () => void;
  isSaving?: boolean;
}

// ─── WCAG contrast helpers ────────────────────────────────────────────────────

function hexToLinear(hexComponent: number): number {
  const sRGB = hexComponent / 255;
  return sRGB <= 0.03928
    ? sRGB / 12.92
    : Math.pow((sRGB + 0.055) / 1.055, 2.4);
}

function relativeLuminance(hex: string): number {
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  return (
    0.2126 * hexToLinear(r) +
    0.7152 * hexToLinear(g) +
    0.0722 * hexToLinear(b)
  );
}

function contrastRatio(hex1: string, hex2: string): number {
  const l1 = relativeLuminance(hex1);
  const l2 = relativeLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// ─── Token group definitions ──────────────────────────────────────────────────

const TOKEN_GROUPS: Array<{
  title: string;
  tokens: Array<{ field: keyof ThemeTokenValues; label: string; description: string }>;
}> = [
  {
    title: "Background Tones",
    tokens: [
      { field: "bg",       label: "--bg",       description: "Page background" },
      { field: "surface",  label: "--surface",  description: "Card / panel surface" },
      { field: "surface2", label: "--surface-2", description: "Secondary surface, nav bar" },
    ],
  },
  {
    title: "Text & Borders",
    tokens: [
      { field: "border_col",   label: "--border",       description: "Borders and dividers" },
      { field: "text_primary", label: "--text-primary",  description: "Primary body text" },
      { field: "text_muted",   label: "--text-muted",    description: "Secondary / helper text" },
    ],
  },
  {
    title: "Brand Colours",
    tokens: [
      { field: "brand",      label: "--brand",      description: "Primary brand / interactive" },
      { field: "brand_dark", label: "--brand-dark", description: "Brand hover / dark variant" },
      { field: "accent",     label: "--accent",     description: "Accent / AI highlight" },
    ],
  },
  {
    title: "Status Colours",
    tokens: [
      { field: "color_green", label: "--color-green", description: "Positive / success" },
      { field: "color_amber", label: "--color-amber", description: "Warning / medium risk" },
      { field: "color_red",   label: "--color-red",   description: "Negative / high risk" },
      { field: "color_blue",  label: "--color-blue",  description: "Informational / neutral" },
    ],
  },
];

// ─── Main component ───────────────────────────────────────────────────────────

export function ThemeEditor({
  initial,
  onSave,
  onCancel,
  isSaving = false,
}: ThemeEditorProps): React.JSX.Element {
  const [tokens, setTokens] = useState<ThemeTokenValues>({
    bg:           initial.bg,
    surface:      initial.surface,
    surface2:     initial.surface2,
    border_col:   initial.border_col,
    text_primary: initial.text_primary,
    text_muted:   initial.text_muted,
    brand:        initial.brand,
    brand_dark:   initial.brand_dark,
    accent:       initial.accent,
    color_green:  initial.color_green,
    color_amber:  initial.color_amber,
    color_red:    initial.color_red,
    color_blue:   initial.color_blue,
  });

  const [themeName, setThemeName] = useState(initial.theme_name);

  const updateToken = (field: keyof ThemeTokenValues, hex: string) => {
    setTokens((prev) => ({ ...prev, [field]: hex }));
  };

  // WCAG contrast: text_primary over surface (Addendum S6.4)
  const wcagRatio = contrastRatio(tokens.text_primary, tokens.surface);
  const wcagPass = wcagRatio >= 4.5;

  const previewTokens: PreviewTokens = { ...tokens };

  return (
    <div className="theme-editor" role="dialog" aria-label="Theme editor">
      {/* ── Column 1: Token editor ──────────────────────────────────── */}
      <div>
        <p className="theme-editor__col-title">Token Editor</p>

        {TOKEN_GROUPS.map((group) => (
          <div key={group.title} className="theme-editor__group">
            <p className="theme-editor__group-title">{group.title}</p>

            {group.tokens.map(({ field, label, description }) => (
              <div key={field} className="theme-editor__token-row">
                <span className="theme-editor__token-label">{label}</span>
                <span className="theme-editor__token-desc">{description}</span>
                <ColorPickerInput
                  value={tokens[field]}
                  onChange={(hex) => updateToken(field, hex)}
                  baseValue={initial[field]}
                  label={label}
                />
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* ── Column 2: Live preview ──────────────────────────────────── */}
      <div>
        <p className="theme-editor__col-title">Live Preview</p>
        <ThemePreviewPanel tokens={previewTokens} />
      </div>

      {/* ── Column 3: Metadata ──────────────────────────────────────── */}
      <div className="theme-editor__meta">
        <p className="theme-editor__col-title">Metadata</p>

        <div className="theme-editor__meta-field">
          <label htmlFor="theme-name-input" className="theme-editor__meta-label">
            Theme Name *
          </label>
          <input
            id="theme-name-input"
            type="text"
            className="theme-editor__meta-input"
            value={themeName}
            onChange={(e) => setThemeName(e.target.value)}
            placeholder="My Custom Theme"
            required
          />
        </div>

        <div className="theme-editor__meta-field">
          <span className="theme-editor__meta-label">Mode</span>
          <span className="theme-editor__meta-value">
            <span
              className={`theme-card__badge theme-card__badge--${initial.mode}`}
              style={{ textTransform: "capitalize" }}
            >
              {initial.mode}
            </span>
          </span>
        </div>

        {initial.based_on_name && (
          <div className="theme-editor__meta-field">
            <span className="theme-editor__meta-label">Based On</span>
            <span className="theme-editor__meta-value">{initial.based_on_name}</span>
          </div>
        )}

        {/* WCAG contrast indicator — non-blocking per Addendum S6.4 */}
        <div
          className={`theme-editor__wcag ${wcagPass ? "theme-editor__wcag--pass" : "theme-editor__wcag--warn"}`}
          role="status"
          aria-live="polite"
        >
          <span>{wcagPass ? "✓" : "⚠"}</span>
          <span>
            Contrast {wcagRatio.toFixed(2)}:1
            {!wcagPass && " (below WCAG AA 4.5:1)"}
          </span>
        </div>
      </div>

      {/* ── Footer: actions ─────────────────────────────────────────── */}
      <div className="theme-editor__footer">
        <button type="button" className="theme-tab__btn" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="theme-tab__btn theme-tab__btn--primary"
          onClick={() => onSave(themeName, tokens)}
          disabled={isSaving || !themeName.trim()}
        >
          {isSaving ? "Saving…" : "Save Theme"}
        </button>
      </div>
    </div>
  );
}
