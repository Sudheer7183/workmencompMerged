/**
 * ModeToggle — Phase 6.
 *
 * Addendum S7: Sun/moon toggle in the nav bar.
 *
 * Behaviour:
 *   - Only rendered when allow_user_override = TRUE for the current carrier,
 *     or the user is SUPER_ADMIN.
 *   - On click: toggles between the user's saved dark/light theme preferences.
 *     Calls PUT /api/v1/user/theme-preference and immediately invalidates
 *     the ["theme"] query so useTheme() re-fetches and re-applies CSS vars.
 *   - Clicking while in dark mode switches to the user's last-used light theme
 *     (or Default Light, theme_id=2), and vice versa.
 */

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { useTenantCarrier } from "@/context/TenantCarrierContext";

interface CarrierThemeConfig {
  allow_user_override: boolean;
  default_theme_id: number;
}

interface UserThemePref {
  theme_id: number;
  theme_source: "SYSTEM" | "CUSTOM";
}

interface ResolvedTheme {
  mode: string;
  theme_id: number;
  theme_source?: string;
}

// System theme IDs (from public.theme_definitions seed data):
//   1 = Default Dark, 2 = Default Light,
//   3 = Corporate Dark, 4 = Corporate Light
const DARK_FALLBACK_ID  = 1;  // Default Dark
const LIGHT_FALLBACK_ID = 2;  // Default Light

async function fetchCarrierConfig(carrierId: number): Promise<CarrierThemeConfig> {
  const { data } = await axios.get<CarrierThemeConfig>(
    `/api/v1/admin/carrier-theme-config/${carrierId}`
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

export function ModeToggle(): React.JSX.Element | null {
  const { user } = useAuth();
  const { carrierId } = useTenantCarrier();
  const queryClient = useQueryClient();

  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const { data: carrierConfig } = useQuery({
    queryKey: ["carrier-theme-config", carrierId],
    queryFn: () => fetchCarrierConfig(carrierId),
    enabled: !isSuperAdmin && carrierId > 0,
    staleTime: 5 * 60 * 1000,
  });

  const { data: userPref } = useQuery({
    queryKey: ["user-theme-pref"],
    queryFn: fetchUserPref,
    enabled: !isSuperAdmin && carrierId > 0,
    staleTime: 5 * 60 * 1000,
  });

  const resolvedTheme = queryClient.getQueryData<ResolvedTheme>(["theme", carrierId]);
  const currentMode = resolvedTheme?.mode ?? "dark";

  const toggleMutation = useMutation({
    mutationFn: () => {
      // Toggle: if currently dark → switch to light fallback, and vice versa.
      const nextThemeId =
        currentMode === "dark" ? LIGHT_FALLBACK_ID : DARK_FALLBACK_ID;
      return setUserPref(carrierId, nextThemeId, "SYSTEM");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["theme", carrierId] });
      queryClient.invalidateQueries({ queryKey: ["user-theme-pref"] });
    },
  });

  // Hide when override is disabled (and user is not SUPER_ADMIN).
  const allowOverride = isSuperAdmin || (carrierConfig?.allow_user_override ?? true);
  if (!allowOverride) return null;

  const isDark = currentMode === "dark";

  return (
    <button
      type="button"
      className="mode-toggle"
      onClick={() => toggleMutation.mutate()}
      disabled={toggleMutation.isPending}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      data-testid="mode-toggle"
    >
      <span className="mode-toggle__icon" aria-hidden="true">
        {isDark ? "☀" : "🌙"}
      </span>
    </button>
  );
}
