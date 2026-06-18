/**
 * UserThemePicker — Phase 6.
 *
 * Addendum S8: Compact theme picker opened from the user avatar dropdown.
 *
 * Features:
 *   - "Use Carrier Default" option at top: DELETE /api/v1/user/theme-preference
 *   - System themes (4) + custom themes, grouped by mode
 *   - Each row: 5 mini swatches + name + mode badge
 *   - Current selection indicated with checkmark
 *   - Selecting a theme: PUT /api/v1/user/theme-preference →
 *     invalidates ["theme"] query → useTheme() re-applies CSS vars immediately
 */

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useAuth } from "@/context/AuthContext";

interface ThemeOption {
  theme_id: number;
  theme_name: string;
  mode: "dark" | "light";
  is_system: boolean;
  bg: string;
  surface: string;
  brand: string;
  accent: string;
  text_primary: string;
}

interface UserThemePref {
  theme_id: number;
  theme_source: "SYSTEM" | "CUSTOM";
}



const SWATCH_FIELDS: Array<keyof ThemeOption & string> = [
  "bg", "surface", "brand", "accent", "text_primary",
];

async function fetchThemes(carrierId: number): Promise<ThemeOption[]> {
  const { data } = await axios.get<ThemeOption[]>(
    `/api/v1/admin/themes?carrier_id=${carrierId}`
  );
  return data;
}

async function fetchUserPref(): Promise<UserThemePref | null> {
  const { data } = await axios.get<UserThemePref | null>(
    "/api/v1/user/theme-preference"
  );
  return data;
}

async function setUserPref(
  carrierId: number,
  themeId: number,
  themeSource: "SYSTEM" | "CUSTOM"
): Promise<void> {
  await axios.put(
    `/api/v1/user/theme-preference?carrier_id=${carrierId}`,
    { theme_id: themeId, theme_source: themeSource }
  );
}

async function clearUserPref(carrierId: number): Promise<void> {
  await axios.delete(
    `/api/v1/user/theme-preference?carrier_id=${carrierId}`
  );
}

export function UserThemePicker(): React.JSX.Element {
  const { carrierId } = useTenantCarrier();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  // SUPER_ADMIN has no tenant — skip theme queries to prevent 400 errors.
  const isTenantUser = user !== null && user.role !== "SUPER_ADMIN";

  const { data: themes = [] } = useQuery({
    queryKey: ["admin-themes", carrierId],
    queryFn: () => fetchThemes(carrierId),
    staleTime: 5 * 60 * 1000,
    enabled: isTenantUser && carrierId > 0,
  });

  const { data: userPref } = useQuery({
    queryKey: ["user-theme-pref"],
    queryFn: fetchUserPref,
    staleTime: 5 * 60 * 1000,
    enabled: isTenantUser && carrierId > 0,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["theme", carrierId] });
    queryClient.invalidateQueries({ queryKey: ["user-theme-pref"] });
  };

  const selectMutation = useMutation({
    mutationFn: ({ themeId, isSystem }: { themeId: number; isSystem: boolean }) =>
      setUserPref(carrierId, themeId, isSystem ? "SYSTEM" : "CUSTOM"),
    onSuccess: invalidate,
  });

  const clearMutation = useMutation({
    mutationFn: () => clearUserPref(carrierId),
    onSuccess: invalidate,
  });

  const darkThemes = themes.filter((t) => t.mode === "dark");
  const lightThemes = themes.filter((t) => t.mode === "light");

  const isActive = (t: ThemeOption) =>
    userPref?.theme_id === t.theme_id &&
    userPref?.theme_source === (t.is_system ? "SYSTEM" : "CUSTOM");

  const renderOption = (t: ThemeOption) => (
    <button
      key={t.theme_id}
      type="button"
      className={`user-theme-picker__option${isActive(t) ? " user-theme-picker__option--active" : ""}`}
      onClick={() =>
        selectMutation.mutate({ themeId: t.theme_id, isSystem: t.is_system })
      }
      data-testid={`theme-option-${t.theme_name}`}
    >
      <div className="user-theme-picker__swatches">
        {SWATCH_FIELDS.map((field) => (
          <div
            key={field}
            className="user-theme-picker__swatch"
            style={{ backgroundColor: `#${t[field]}` }}
          />
        ))}
      </div>
      <span className="user-theme-picker__name">{t.theme_name}</span>
      <span className={`user-theme-picker__mode-badge`}>{t.mode}</span>
      {isActive(t) && (
        <span className="user-theme-picker__check" aria-label="Currently selected">
          ✓
        </span>
      )}
    </button>
  );

  return (
    <div className="user-theme-picker" role="menu" aria-label="My theme">
      <div className="user-theme-picker__title">My Theme</div>

      {/* Carrier default option */}
      <button
        type="button"
        className={`user-theme-picker__option${!userPref ? " user-theme-picker__option--active" : ""}`}
        onClick={() => clearMutation.mutate()}
      >
        <span className="user-theme-picker__name" style={{ color: "var(--text-muted)" }}>
          Use Carrier Default
        </span>
        {!userPref && (
          <span className="user-theme-picker__check">✓</span>
        )}
      </button>

      {darkThemes.length > 0 && (
        <>
          <div className="user-theme-picker__group-label">Dark</div>
          {darkThemes.map(renderOption)}
        </>
      )}

      {lightThemes.length > 0 && (
        <>
          <div className="user-theme-picker__group-label">Light</div>
          {lightThemes.map(renderOption)}
        </>
      )}
    </div>
  );
}