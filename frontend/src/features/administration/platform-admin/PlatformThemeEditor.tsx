/**
 * PlatformThemeEditor — SUPER_ADMIN platform-level theme management.
 *
 * Three levels of interaction:
 *  1. Theme list — shows all platform themes with mode badge, colour swatches,
 *     "Set as Default" and "Edit Tokens" actions per row.
 *  2. Create variant — inline name + mode form that calls POST /platform/themes.
 *  3. Token editor — overlay drawer with colour pickers for all 13 CSS tokens,
 *     calls PUT /platform/themes/{id} on save.
 *
 * Backend endpoints:
 *   GET  /platform/themes           → list all themes
 *   POST /platform/themes           → create a new variant
 *   PUT  /platform/themes/{id}      → update name / tokens
 *   POST /platform/themes/{id}/default → designate as platform default
 *
 * All strings via useLabels(). No style={{}} props except the dynamic swatch
 * background colour (unavoidable for data-driven colours). All layout via BEM.
 */

import React, { useState, useCallback } from "react";
import axios from "axios";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PlatformTheme {
  theme_id: number;
  theme_name: string;
  is_default: boolean;
  base_mode: "dark" | "light";
  tokens: Record<string, string>;
  created_at: string;
}

/** Flat map of CSS variable name → hex value. */
type TokenMap = Record<string, string>;

// ── Token definition ──────────────────────────────────────────────────────────

interface TokenDef {
  key: string;           // e.g. "--brand"
  label: string;         // display name
}

interface TokenGroup {
  title: string;
  tokens: TokenDef[];
}

const TOKEN_GROUPS: TokenGroup[] = [
  {
    title: "Background Tones",
    tokens: [
      { key: "--bg",        label: "Page Background" },
      { key: "--surface",   label: "Surface" },
      { key: "--surface-2", label: "Surface 2" },
    ],
  },
  {
    title: "Text & Borders",
    tokens: [
      { key: "--border",       label: "Border" },
      { key: "--text-primary", label: "Text Primary" },
      { key: "--text-muted",   label: "Text Muted" },
    ],
  },
  {
    title: "Brand Colours",
    tokens: [
      { key: "--brand",      label: "Brand" },
      { key: "--brand-dark", label: "Brand Dark" },
      { key: "--accent",     label: "Accent" },
    ],
  },
  {
    title: "Status Colours",
    tokens: [
      { key: "--color-green", label: "Green" },
      { key: "--color-amber", label: "Amber" },
      { key: "--color-red",   label: "Red" },
      { key: "--color-blue",  label: "Blue" },
    ],
  },
];

const ALL_TOKEN_KEYS = TOKEN_GROUPS.flatMap((g) => g.tokens.map((t) => t.key));

/** Default dark seed values used when a theme has no tokens yet. */
const DEFAULT_DARK_SEED: TokenMap = {
  "--bg":           "#0f1117",
  "--surface":      "#181c27",
  "--surface-2":    "#1e2436",
  "--border":       "#2a2f45",
  "--text-primary": "#e8ecf4",
  "--text-muted":   "#7a84a0",
  "--brand":        "#4ade80",
  "--brand-dark":   "#15803d",
  "--accent":       "#818cf8",
  "--color-green":  "#22c55e",
  "--color-amber":  "#f59e0b",
  "--color-red":    "#ef4444",
  "--color-blue":   "#60a5fa",
};

const DEFAULT_LIGHT_SEED: TokenMap = {
  "--bg":           "#f8fafc",
  "--surface":      "#ffffff",
  "--surface-2":    "#f1f5f9",
  "--border":       "#e2e8f0",
  "--text-primary": "#0f172a",
  "--text-muted":   "#64748b",
  "--brand":        "#16a34a",
  "--brand-dark":   "#15803d",
  "--accent":       "#6366f1",
  "--color-green":  "#22c55e",
  "--color-amber":  "#f59e0b",
  "--color-red":    "#ef4444",
  "--color-blue":   "#3b82f6",
};

function seedForMode(mode: "dark" | "light"): TokenMap {
  return mode === "light" ? DEFAULT_LIGHT_SEED : DEFAULT_DARK_SEED;
}

/** Fill any missing token keys with seed values. */
function hydrateTokens(tokens: TokenMap, mode: "dark" | "light"): TokenMap {
  const seed = seedForMode(mode);
  const result: TokenMap = { ...seed };
  for (const key of ALL_TOKEN_KEYS) {
    if (tokens[key]) result[key] = tokens[key];
  }
  return result;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchPlatformThemes(): Promise<PlatformTheme[]> {
  try {
    const { data } = await axios.get<PlatformTheme[]>("/platform/themes");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

const SWATCH_PREVIEW_KEYS = ["--brand", "--bg", "--surface", "--accent"];

function SwatchRow({ tokens }: { tokens: TokenMap }): React.JSX.Element {
  return (
    <div className="platform-theme-card__swatch-row">
      {SWATCH_PREVIEW_KEYS.map((key) =>
        tokens[key] ? (
          <span
            key={key}
            className="platform-theme-card__swatch"
            style={{ backgroundColor: tokens[key] }}
            title={`${key}: ${tokens[key]}`}
          />
        ) : null
      )}
    </div>
  );
}

// ── Token editor overlay ──────────────────────────────────────────────────────

interface TokenEditorProps {
  theme: PlatformTheme;
  onClose: () => void;
  onSaved: () => void;
}

function TokenEditor({ theme, onClose, onSaved }: TokenEditorProps): React.JSX.Element {
  const label = useLabels("platform_admin");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();

  const [themeName, setThemeName] = useState(theme.theme_name);
  const [tokens, setTokens] = useState<TokenMap>(() =>
    hydrateTokens(theme.tokens, theme.base_mode)
  );
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async (): Promise<void> => {
      await axios.put(`/platform/themes/${theme.theme_id}`, {
        theme_name: themeName.trim() || theme.theme_name,
        tokens,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform-themes"] });
      onSaved();
    },
    onError: (err: unknown) => {
      setError(
        axios.isAxiosError(err)
          ? ((err.response?.data as { detail?: string })?.detail ??
              labelShared("error_generic", "Something went wrong. Please try again."))
          : labelShared("error_generic", "Something went wrong. Please try again.")
      );
    },
  });

  const setToken = useCallback((key: string, value: string): void => {
    setTokens((prev) => ({ ...prev, [key]: value }));
  }, []);

  return (
    <div className="theme-edit-overlay" role="dialog" aria-modal="true">
      <div className="theme-edit-drawer">
        {/* Header */}
        <div className="theme-edit-drawer__header">
          <h2 className="theme-edit-drawer__title">
            {label("themes.edit_title", "Edit Theme Tokens")}
          </h2>
          <button
            type="button"
            className="theme-edit-drawer__close"
            onClick={onClose}
            aria-label={labelShared("btn.close", "Close")}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="theme-edit-drawer__body">
          {error && (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          )}

          {/* Theme name */}
          <div className="form-field" style={{ marginBottom: "var(--space-5)" }}>
            <label className="form-field__label" htmlFor="te-name">
              {label("themes.name_label", "Theme Name")}
            </label>
            <input
              id="te-name"
              className="form-field__input"
              type="text"
              value={themeName}
              onChange={(e) => setThemeName(e.target.value)}
              maxLength={200}
            />
          </div>

          {/* Token groups */}
          {TOKEN_GROUPS.map((group) => (
            <div key={group.title} className="theme-token-group">
              <p className="theme-token-group__title">{group.title}</p>
              <div className="theme-token-grid">
                {group.tokens.map(({ key, label: tokenLabel }) => {
                  const value = tokens[key] ?? "";
                  const inputId = `te-${key.replace(/[^a-z0-9]/g, "-")}`;
                  return (
                    <div key={key} className="theme-token-row">
                      <label className="theme-token-row__label" htmlFor={inputId}>
                        {tokenLabel}
                      </label>
                      <div className="theme-token-row__input-group">
                        {/* Native color picker layered under the swatch display */}
                        <div className="theme-token-row__swatch-wrap">
                          <div
                            className="theme-token-row__swatch-display"
                            style={{ backgroundColor: value }}
                          />
                          <input
                            type="color"
                            value={value || "#000000"}
                            onChange={(e) => setToken(key, e.target.value)}
                            style={{
                              position: "absolute",
                              inset: 0,
                              opacity: 0,
                              cursor: "pointer",
                              width: "100%",
                              height: "100%",
                              border: "none",
                              padding: 0,
                            }}
                            aria-label={`${tokenLabel} colour picker`}
                          />
                        </div>
                        <input
                          id={inputId}
                          type="text"
                          className="theme-token-row__text-input"
                          value={value}
                          onChange={(e) => setToken(key, e.target.value)}
                          placeholder="#000000"
                          maxLength={20}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="theme-edit-drawer__footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            {labelShared("btn.close", "Cancel")}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending
              ? labelShared("loading", "Loading…")
              : label("themes.btn_save_tokens", "Save Tokens")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function PlatformThemeEditor(): React.JSX.Element {
  const label = useLabels("platform_admin");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();

  const [editingTheme, setEditingTheme] = useState<PlatformTheme | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newThemeName, setNewThemeName] = useState("");
  const [newThemeMode, setNewThemeMode] = useState<"dark" | "light">("dark");
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: themes = [], isLoading } = useQuery<PlatformTheme[]>({
    queryKey: ["platform-themes"],
    queryFn: fetchPlatformThemes,
    staleTime: 30 * 1000,
  });

  const setDefaultMutation = useMutation({
    mutationFn: async (themeId: number): Promise<void> => {
      await axios.post(`/platform/themes/${themeId}/default`);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["platform-themes"] }),
  });

  const createMutation = useMutation({
    mutationFn: async (params: { name: string; mode: "dark" | "light" }): Promise<void> => {
      await axios.post("/platform/themes", {
        theme_name: params.name,
        base_mode:  params.mode,
        tokens:     seedForMode(params.mode),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform-themes"] });
      setShowCreateForm(false);
      setNewThemeName("");
      setNewThemeMode("dark");
      setCreateError(null);
    },
    onError: (err: unknown) => {
      setCreateError(
        axios.isAxiosError(err)
          ? ((err.response?.data as { detail?: string })?.detail ??
              label("theme.create_error", "Failed to create theme."))
          : label("theme.create_error", "Failed to create theme.")
      );
    },
  });

  function handleCreate(): void {
    if (!newThemeName.trim()) return;
    createMutation.mutate({ name: newThemeName.trim(), mode: newThemeMode });
  }

  return (
    <div className="platform-theme-editor">
      {/* Header toolbar */}
      <div className="platform-theme-editor__toolbar">
        <div>
          <h1 className="platform-theme-editor__title">
            {label("themes.title", "Platform Themes")}
          </h1>
          <p className="platform-theme-editor__subtitle">
            {label(
              "themes.subtitle",
              "Manage base and variant themes. The default theme is used when no tenant theme override exists."
            )}
          </p>
        </div>

        <div className="platform-theme-editor__actions">
          {showCreateForm ? (
            <>
              <input
                className="form-field__input"
                type="text"
                value={newThemeName}
                onChange={(e) => setNewThemeName(e.target.value)}
                placeholder={label("themes.new_name_placeholder", "Theme name…")}
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                style={{ width: 200 }}
              />
              <select
                className="form-field__select"
                value={newThemeMode}
                onChange={(e) => setNewThemeMode(e.target.value as "dark" | "light")}
                style={{ width: 100 }}
              >
                <option value="dark">{label("themes.mode_dark", "Dark")}</option>
                <option value="light">{label("themes.mode_light", "Light")}</option>
              </select>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={handleCreate}
                disabled={!newThemeName.trim() || createMutation.isPending}
              >
                {createMutation.isPending
                  ? labelShared("loading", "Loading…")
                  : label("themes.btn_create", "Create")}
              </button>
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewThemeName("");
                  setCreateError(null);
                }}
              >
                {label("btn.cancel_short", "Cancel")}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setShowCreateForm(true)}
            >
              {label("themes.btn_new", "New Theme Variant")}
            </button>
          )}
        </div>
      </div>

      {createError && (
        <div className="alert alert--error" role="alert">
          {createError}
        </div>
      )}

      {/* Theme list */}
      {isLoading ? (
        <p className="text-muted">{labelShared("loading", "Loading…")}</p>
      ) : themes.length === 0 ? (
        <div className="empty-state">
          <span>{label("themes.empty", "No platform themes found.")}</span>
        </div>
      ) : (
        <div className="platform-theme-editor__theme-list">
          {themes.map((theme) => (
            <div
              key={theme.theme_id}
              className={`platform-theme-card ${theme.is_default ? "platform-theme-card--default" : ""}`}
            >
              <div className="platform-theme-card__info">
                <p className="platform-theme-card__name">
                  {theme.theme_name}
                  {theme.is_default && (
                    <span className="badge badge-green" style={{ marginLeft: "var(--space-2)" }}>
                      {label("themes.default_badge", "Platform Default")}
                    </span>
                  )}
                  <span className="badge badge-muted" style={{ marginLeft: "var(--space-2)" }}>
                    {theme.base_mode === "dark"
                      ? label("themes.mode_dark", "Dark")
                      : label("themes.mode_light", "Light")}
                  </span>
                </p>
                <p className="platform-theme-card__meta">
                  {label("themes.created_prefix", "Created")}{" "}
                  {new Date(theme.created_at).toLocaleDateString()}
                  {" · "}
                  {label("themes.id_prefix", "ID:")} {theme.theme_id}
                </p>
                <SwatchRow tokens={theme.tokens} />
              </div>

              <div className="platform-theme-card__actions">
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  onClick={() => setEditingTheme(theme)}
                >
                  {label("themes.btn_edit_tokens", "Edit Tokens")}
                </button>
                {!theme.is_default && (
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => setDefaultMutation.mutate(theme.theme_id)}
                    disabled={setDefaultMutation.isPending}
                  >
                    {label("themes.btn_set_default", "Set as Default")}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Token editor overlay */}
      {editingTheme && (
        <TokenEditor
          theme={editingTheme}
          onClose={() => setEditingTheme(null)}
          onSaved={() => setEditingTheme(null)}
        />
      )}
    </div>
  );
}
