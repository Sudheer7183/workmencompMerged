/**
 * ThemeTab — CarrierConfigHub Tab 6.
 *
 * Full theme management UI per Addendum S5–S7 and S13.
 *
 * Features:
 *   - Lists system themes (4, padlock read-only) and custom themes
 *   - Theme cards with colour swatches, current-default highlight
 *   - "Set as Default" / "Edit" / "Delete" per custom theme
 *   - "Create New Theme" → base theme selector → ThemeEditor
 *   - "Allow User Override" toggle → carrier_theme_config
 *   - Import/Export (ThemeImportExport)
 *
 * Phase 6. TENANT_ADMIN only.
 *
 * Fix applied:
 *   The base theme picker rendered ThemeCard components with empty
 *   onSetDefault/onEdit/onDelete handlers (all `() => {}`), and relied
 *   on a transparent overlay div with `zIndex: -1` to catch clicks via
 *   bubbling. Because the overlay was behind the cards (z-index -1) it
 *   never received pointer events, so clicking a theme card had no effect.
 *
 *   Fixed by introducing a separate BaseSelectorCard component used only
 *   in the picker view. Each card calls onSelect() directly via its own
 *   onClick handler — no overlay hack needed.
 */

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ThemeEditor, type ThemeTokenValues } from "./ThemeEditor";
import { ThemeImportExport } from "./ThemeImportExport";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ThemeRow {
  theme_id: number;
  theme_name: string;
  mode: "dark" | "light";
  is_system: boolean;
  based_on_name: string | null;
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

interface CarrierThemeConfig {
  carrier_id: number;
  theme_source: "SYSTEM" | "CUSTOM";
  default_theme_id: number;
  allow_user_override: boolean;
}

// ─── API helpers ──────────────────────────────────────────────────────────────

async function fetchThemes(carrierId: number): Promise<ThemeRow[]> {
  const { data } = await axios.get<ThemeRow[]>(
    `/api/v1/admin/themes?carrier_id=${carrierId}`
  );
  return data;
}

async function fetchCarrierThemeConfig(carrierId: number): Promise<CarrierThemeConfig> {
  const { data } = await axios.get<CarrierThemeConfig>(
    `/api/v1/admin/carrier-theme-config/${carrierId}`
  );
  return data;
}

async function updateCarrierThemeConfig(
  carrierId: number,
  payload: Omit<CarrierThemeConfig, "carrier_id">
): Promise<CarrierThemeConfig> {
  const { data } = await axios.put<CarrierThemeConfig>(
    `/api/v1/admin/carrier-theme-config/${carrierId}`,
    payload
  );
  return data;
}

async function createTheme(
  payload: ThemeTokenValues & {
    theme_name: string;
    mode: string;
    based_on_name: string | null;
  }
): Promise<ThemeRow> {
  const { data } = await axios.post<ThemeRow>("/api/v1/admin/themes", payload);
  return data;
}

async function updateTheme(
  themeId: number,
  payload: ThemeTokenValues & { theme_name: string }
): Promise<ThemeRow> {
  const { data } = await axios.put<ThemeRow>(
    `/api/v1/admin/themes/${themeId}`,
    payload
  );
  return data;
}

async function deleteTheme(themeId: number): Promise<void> {
  await axios.delete(`/api/v1/admin/themes/${themeId}`);
}

async function exportTheme(themeId: number): Promise<void> {
  const response = await axios.get(`/api/v1/admin/themes/${themeId}/export`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(new Blob([response.data as BlobPart]));
  const a = document.createElement("a");
  a.href = url;
  a.download = `theme_${themeId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Shared colour swatches ───────────────────────────────────────────────────

const SWATCH_FIELDS: Array<keyof ThemeRow & string> = [
  "bg", "surface", "brand", "accent", "text_primary",
];

function ThemeSwatches({ theme }: { theme: ThemeRow }): React.JSX.Element {
  return (
    <div className="theme-card__swatches" aria-label="Theme colour swatches">
      {SWATCH_FIELDS.map((field) => (
        <div
          key={field}
          className="theme-card__swatch"
          style={{ backgroundColor: `#${theme[field]}` }}
          title={`--${field}: #${theme[field]}`}
        />
      ))}
    </div>
  );
}

// ─── BaseSelectorCard — used only in the base picker view ─────────────────────
//
// FIX: The original code reused ThemeCard with empty () => {} handlers and
// relied on an invisible overlay div to detect clicks. The overlay had
// zIndex: -1 so it sat behind the cards and never received pointer events.
// This dedicated component solves it cleanly: the entire card is clickable
// and calls onSelect() directly.

interface BaseSelectorCardProps {
  theme: ThemeRow;
  onSelect: (theme: ThemeRow) => void;
}

function BaseSelectorCard({ theme, onSelect }: BaseSelectorCardProps): React.JSX.Element {
  return (
    <button
      type="button"
      className={`theme-card theme-card--selectable${theme.is_system ? " theme-card--system" : ""}`}
      onClick={() => onSelect(theme)}
      aria-label={`Use ${theme.theme_name} as base theme`}
      data-testid={`theme-card-${theme.theme_name}`}
    >
      <div className="theme-card__header">
        <h4 className="theme-card__name">{theme.theme_name}</h4>
        <div className="theme-card__badges">
          <span className={`theme-card__badge theme-card__badge--${theme.mode}`}>
            {theme.mode.toUpperCase()}
          </span>
          {theme.is_system && (
            <span className="theme-card__badge theme-card__badge--system">
              SYSTEM 🔒
            </span>
          )}
        </div>
      </div>
      <ThemeSwatches theme={theme} />
      <div className="theme-card__footer">
        <button
          type="button"
          className="theme-card__action-btn"
          onClick={(e) => {
            e.stopPropagation(); // prevent double-firing from card onClick
            void exportTheme(theme.theme_id);
          }}
          title="Export theme as JSON"
        >
          Export
        </button>
      </div>
    </button>
  );
}

// ─── ThemeCard — used in the main theme list ──────────────────────────────────

interface ThemeCardProps {
  theme: ThemeRow;
  isCurrentDefault: boolean;
  onSetDefault: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onExport: () => void;
}

function ThemeCard({
  theme,
  isCurrentDefault,
  onSetDefault,
  onEdit,
  onDelete,
  onExport,
}: ThemeCardProps): React.JSX.Element {
  return (
    <div
      className={[
        "theme-card",
        isCurrentDefault ? "theme-card--current" : "",
        theme.is_system ? "theme-card--system" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid={`theme-card-${theme.theme_name}`}
    >
      {theme.is_system && (
        <span
          className="theme-card__lock"
          title="System theme — read-only"
          aria-label="System theme"
        >
          🔒
        </span>
      )}

      <div className="theme-card__header">
        <h4 className="theme-card__name">{theme.theme_name}</h4>
        <div className="theme-card__badges">
          <span className={`theme-card__badge theme-card__badge--${theme.mode}`}>
            {theme.mode.toUpperCase()}
          </span>
          {theme.is_system && (
            <span className="theme-card__badge theme-card__badge--system">SYSTEM</span>
          )}
          {isCurrentDefault && (
            <span className="theme-card__badge theme-card__badge--current">Default</span>
          )}
        </div>
      </div>

      <ThemeSwatches theme={theme} />

      <div className="theme-card__footer">
        {!isCurrentDefault && (
          <button
            type="button"
            className="theme-card__action-btn"
            onClick={onSetDefault}
            title="Set as default theme for this carrier"
          >
            Set Default
          </button>
        )}
        {!theme.is_system && (
          <button
            type="button"
            className="theme-card__action-btn"
            onClick={onEdit}
            title="Edit this theme"
          >
            Edit
          </button>
        )}
        <button
          type="button"
          className="theme-card__action-btn"
          onClick={onExport}
          title="Export theme as JSON"
        >
          Export
        </button>
        {!theme.is_system && (
          <button
            type="button"
            className="theme-card__action-btn theme-card__action-btn--danger"
            onClick={onDelete}
            title="Delete this theme"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface ThemeTabProps {
  carrierId: number;
}

type EditorMode =
  | { type: "closed" }
  | { type: "create"; baseTheme: ThemeRow }
  | { type: "edit"; theme: ThemeRow };

export function ThemeTab({ carrierId }: ThemeTabProps): React.JSX.Element {
  const queryClient = useQueryClient();
  const [editorMode, setEditorMode] = useState<EditorMode>({ type: "closed" });
  const [basePickerOpen, setBasePickerOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: themes = [], isLoading: themesLoading } = useQuery({
    queryKey: ["admin-themes", carrierId],
    queryFn: () => fetchThemes(carrierId),
    staleTime: 60_000,
  });

  const { data: carrierConfig } = useQuery({
    queryKey: ["carrier-theme-config", carrierId],
    queryFn: () => fetchCarrierThemeConfig(carrierId),
    staleTime: 60_000,
  });

  const invalidateAll = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["admin-themes", carrierId] });
    void queryClient.invalidateQueries({ queryKey: ["carrier-theme-config", carrierId] });
    void queryClient.invalidateQueries({ queryKey: ["theme", carrierId] });
  };

  const setDefaultMutation = useMutation({
    mutationFn: (theme: ThemeRow) =>
      updateCarrierThemeConfig(carrierId, {
        default_theme_id: theme.theme_id,
        theme_source: theme.is_system ? "SYSTEM" : "CUSTOM",
        allow_user_override: carrierConfig?.allow_user_override ?? true,
      }),
    onSuccess: invalidateAll,
  });

  const overrideMutation = useMutation({
    mutationFn: (allow: boolean) =>
      updateCarrierThemeConfig(carrierId, {
        default_theme_id: carrierConfig?.default_theme_id ?? 1,
        theme_source: carrierConfig?.theme_source ?? "SYSTEM",
        allow_user_override: allow,
      }),
    onSuccess: invalidateAll,
  });

  const createMutation = useMutation({
    mutationFn: (payload: Parameters<typeof createTheme>[0]) => createTheme(payload),
    onSuccess: () => {
      invalidateAll();
      setEditorMode({ type: "closed" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: ThemeTokenValues & { theme_name: string };
    }) => updateTheme(id, payload),
    onSuccess: () => {
      invalidateAll();
      setEditorMode({ type: "closed" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (themeId: number) => deleteTheme(themeId),
    onSuccess: invalidateAll,
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setDeleteError(
          (err.response.data as { detail?: { message?: string } })?.detail?.message ??
            "This theme is in use. Reassign dependent carriers first."
        );
      }
    },
  });

  const handleSave = (name: string, tokens: ThemeTokenValues): void => {
    if (editorMode.type === "create") {
      createMutation.mutate({
        theme_name: name,
        mode: editorMode.baseTheme.mode,
        based_on_name: editorMode.baseTheme.theme_name,
        ...tokens,
      });
    } else if (editorMode.type === "edit") {
      updateMutation.mutate({
        id: editorMode.theme.theme_id,
        payload: { theme_name: name, ...tokens },
      });
    }
  };

  // FIX: handler called by BaseSelectorCard — no overlay hack needed
  const handleBaseSelected = (theme: ThemeRow): void => {
    setBasePickerOpen(false);
    setEditorMode({ type: "create", baseTheme: theme });
  };

  if (themesLoading) {
    return (
      <p style={{ color: "var(--text-muted)", padding: "var(--space-4)" }}>
        Loading themes…
      </p>
    );
  }

  // ── Theme editor ──────────────────────────────────────────────────────────

  if (editorMode.type === "edit" || editorMode.type === "create") {
    const sourceTheme =
      editorMode.type === "edit" ? editorMode.theme : editorMode.baseTheme;

    return (
      <div style={{ padding: "var(--space-4) 0" }}>
        <ThemeEditor
          initial={{
            ...sourceTheme,
            theme_name:
              editorMode.type === "create"
                ? `${sourceTheme.theme_name} Copy`
                : sourceTheme.theme_name,
          }}
          onSave={handleSave}
          onCancel={() => setEditorMode({ type: "closed" })}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      </div>
    );
  }

  // ── Base theme picker ─────────────────────────────────────────────────────
  //
  // FIX: each BaseSelectorCard has a direct onClick → handleBaseSelected().
  // The invisible overlay div with zIndex:-1 has been removed entirely.

  if (basePickerOpen) {
    return (
      <div style={{ padding: "var(--space-4) 0" }}>
        <h3 style={{ color: "var(--text-primary)", margin: "0 0 var(--space-2)" }}>
          Choose a Base Theme
        </h3>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", margin: "0 0 var(--space-4)" }}>
          Click a theme card to use it as the starting point for your new theme.
        </p>

        <div className="theme-tab__grid">
          {themes.map((t) => (
            <BaseSelectorCard
              key={t.theme_id}
              theme={t}
              onSelect={handleBaseSelected}
            />
          ))}
        </div>

        <div style={{ marginTop: "var(--space-4)" }}>
          <button
            type="button"
            className="theme-tab__btn"
            onClick={() => setBasePickerOpen(false)}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // ── Main theme list ───────────────────────────────────────────────────────

  const currentDefaultId = carrierConfig?.default_theme_id ?? 1;

  return (
    <div className="theme-tab">
      {/* Header */}
      <div className="theme-tab__header">
        <h3 className="theme-tab__title">Themes</h3>
        <div className="theme-tab__actions">
          <ThemeImportExport carrierId={carrierId} onImported={invalidateAll} />
          <button
            type="button"
            className="theme-tab__btn theme-tab__btn--primary"
            onClick={() => setBasePickerOpen(true)}
          >
            + Create Theme
          </button>
        </div>
      </div>

      {/* Allow user override toggle */}
      <div className="theme-tab__override-row">
        <div>
          <p className="theme-tab__override-label">Allow User Theme Override</p>
          <p className="theme-tab__override-hint">
            When enabled, each user can choose their own theme from the avatar menu.
          </p>
        </div>
        <input
          type="checkbox"
          className="theme-tab__toggle"
          checked={carrierConfig?.allow_user_override ?? true}
          onChange={(e) => overrideMutation.mutate(e.target.checked)}
          aria-label="Allow user theme override"
        />
      </div>

      {/* Delete error */}
      {deleteError && (
        <p style={{ color: "var(--color-red)", fontSize: "var(--text-sm)" }}>
          {deleteError}
          <button
            type="button"
            style={{
              marginLeft: "var(--space-2)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
            }}
            onClick={() => setDeleteError(null)}
          >
            ✕
          </button>
        </p>
      )}

      {/* Theme grid */}
      <div className="theme-tab__grid">
        {themes.map((theme) => (
          <ThemeCard
            key={theme.theme_id}
            theme={theme}
            isCurrentDefault={theme.theme_id === currentDefaultId}
            onSetDefault={() => setDefaultMutation.mutate(theme)}
            onEdit={() => setEditorMode({ type: "edit", theme })}
            onDelete={() => {
              setDeleteError(null);
              deleteMutation.mutate(theme.theme_id);
            }}
            onExport={() => void exportTheme(theme.theme_id)}
          />
        ))}
      </div>
    </div>
  );
}