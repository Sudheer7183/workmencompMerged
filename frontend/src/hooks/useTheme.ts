// /**
//  * useTheme — Theme token injection hook
//  *
//  * Phase 2 partial update: still uses hardcoded Default Dark tokens for 12 of 13
//  * tokens, but overrides --brand with tenant_branding.brand_color when set.
//  *
//  * ONLY this file may contain hardcoded hex colour values.
//  *
//  * CORS note: branding is fetched via the relative URL /api/v1/tenant/branding
//  * so that the Vite dev-server proxy forwards it to the FastAPI backend.
//  * Never use an absolute http://localhost:8000 URL — that bypasses the proxy
//  * and triggers a browser CORS block.
//  *
//  * SUPER_ADMIN note: SUPER_ADMIN users have no tenant, so the branding endpoint
//  * returns 400 (no tenant resolved). The query is disabled for SUPER_ADMIN.
//  *
//  * Phase 6: full dynamic useTheme() — replaces all hardcoded tokens from
//  * carrier_theme_config + user_theme_prefs resolution chain.
//  */

// import { useEffect } from "react";
// import { useQuery } from "@tanstack/react-query";
// import axios from "axios";
// import { useAuth } from "@/context/AuthContext";

// // ---------------------------------------------------------------------------
// // Default Dark — Addendum S4 exact hex values.
// // ONLY place in the codebase where hardcoded hex is permitted.
// // ---------------------------------------------------------------------------
// export const DEFAULT_DARK_TOKENS = {
//   "--bg":           "#0f1117",
//   "--surface":      "#181c27",
//   "--surface-2":    "#1e2436",
//   "--border":       "#2a2f45",
//   "--text-primary": "#e8ecf4",
//   "--text-muted":   "#7a84a0",
//   "--brand":        "#4ade80",
//   "--brand-dark":   "#15803d",
//   "--accent":       "#818cf8",
//   "--color-green":  "#22c55e",
//   "--color-amber":  "#f59e0b",
//   "--color-red":    "#ef4444",
//   "--color-blue":   "#60a5fa",
// } as const;

// export type ThemeTokens = typeof DEFAULT_DARK_TOKENS;



// /**
//  * useTheme
//  *
//  * Phase 2:
//  * - Always applies all 12 non-brand Default Dark tokens.
//  * - For non-SUPER_ADMIN users: fetches tenant_branding.brand_color and
//  *   overrides only --brand. All other tokens remain hardcoded Default Dark.
//  * - For SUPER_ADMIN: branding fetch is skipped; --brand uses the default.
//  */
// // ---------------------------------------------------------------------------
// // ResolvedTheme — shape of GET /api/v1/theme/resolved
// // ---------------------------------------------------------------------------
// interface ResolvedTheme {
//   theme_id: number;
//   theme_name: string;
//   mode: string;
//   source: string;
//   bg: string;
//   surface: string;
//   surface2: string;
//   border_col: string;
//   text_primary: string;
//   text_muted: string;
//   brand: string;
//   brand_dark: string;
//   accent: string;
//   color_green: string;
//   color_amber: string;
//   color_red: string;
//   color_blue: string;
// }

// async function fetchResolvedTheme(carrierId: number): Promise<ResolvedTheme> {
//   const { data } = await axios.get<ResolvedTheme>(
//     `/api/v1/theme/resolved?carrier_id=${carrierId}`
//   );
//   return data;
// }

// /**
//  * useTheme — Phase 6 full dynamic implementation.
//  *
//  * Fetches the resolved theme (all 13 tokens) from GET /api/v1/theme/resolved.
//  * The resolution chain (user pref → carrier default → Default Dark) and
//  * brand_color overlay are handled server-side.
//  *
//  * Behaviour guarantees:
//  *   - Falls back to DEFAULT_DARK_TOKENS silently if the request fails.
//  *   - SUPER_ADMIN: query disabled; DEFAULT_DARK_TOKENS applied unconditionally.
//  *   - Always applies a complete 13-token set — never leaves :root in a partial state.
//  *
//  * Cache: TanStack Query staleTime 5 minutes (matches Redis TTL on the backend).
//  */
// export function useTheme(): void {
//   const { user }      = useAuth();
//   const { carrierId } = useTenantCarrier();
//   const isTenantUser  = user !== null && user.role !== "SUPER_ADMIN";

//   const { data: theme } = useQuery<ResolvedTheme | null, Error>({
//     queryKey: ["theme", carrierId],
//     queryFn:  () => fetchResolvedTheme(carrierId),
//     staleTime: 5 * 60 * 1000,
//     enabled:   isTenantUser && carrierId > 0,
//     placeholderData: null,
//     retry: false,
//     // Errors swallowed — DEFAULT_DARK_TOKENS is the silent fallback.
//   });

//   useEffect(() => {
//     // Map API field names (no dashes) → CSS custom property names (with dashes).
//     // When theme is null (loading, disabled, or failed), fall back to DEFAULT_DARK_TOKENS.
//     const cssMap: Record<string, string> = theme
//       ? {
//           "--bg":           `#${theme.bg}`,
//           "--surface":      `#${theme.surface}`,
//           "--surface-2":    `#${theme.surface2}`,
//           "--border":       `#${theme.border_col}`,
//           "--text-primary": `#${theme.text_primary}`,
//           "--text-muted":   `#${theme.text_muted}`,
//           "--brand":        `#${theme.brand}`,
//           "--brand-dark":   `#${theme.brand_dark}`,
//           "--accent":       `#${theme.accent}`,
//           "--color-green":  `#${theme.color_green}`,
//           "--color-amber":  `#${theme.color_amber}`,
//           "--color-red":    `#${theme.color_red}`,
//           "--color-blue":   `#${theme.color_blue}`,
//         }
//       : { ...DEFAULT_DARK_TOKENS };  // DEFAULT_DARK_TOKENS already has '#' prefix values

//     const root = document.documentElement;
//     Object.entries(cssMap).forEach(([property, value]) => {
//       root.style.setProperty(property, value);
//     });
//   }, [theme]);
// }
/**
 * useTheme — Theme token injection hook
 *
 * Phase 2 partial update: still uses hardcoded Default Dark tokens for 12 of 13
 * tokens, but overrides --brand with tenant_branding.brand_color when set.
 *
 * ONLY this file may contain hardcoded hex colour values.
 *
 * CORS note: branding is fetched via the relative URL /api/v1/tenant/branding
 * so that the Vite dev-server proxy forwards it to the FastAPI backend.
 * Never use an absolute http://localhost:8000 URL — that bypasses the proxy
 * and triggers a browser CORS block.
 *
 * SUPER_ADMIN note: SUPER_ADMIN users have no tenant, so the branding endpoint
 * returns 400 (no tenant resolved). The query is disabled for SUPER_ADMIN.
 *
 * Phase 6: full dynamic useTheme() — replaces all hardcoded tokens from
 * carrier_theme_config + user_theme_prefs resolution chain.
 *
 * Fix: added missing import for useTenantCarrier from TenantCarrierContext.
 * The hook called useTenantCarrier() but it was never imported, causing the
 * ReferenceError that crashed <App>.
 */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { useTenantCarrier } from "@/context/TenantCarrierContext";  // FIX: was missing

// ---------------------------------------------------------------------------
// Default Dark — Addendum S4 exact hex values.
// ONLY place in the codebase where hardcoded hex is permitted.
// ---------------------------------------------------------------------------
export const DEFAULT_DARK_TOKENS = {
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
} as const;

export type ThemeTokens = typeof DEFAULT_DARK_TOKENS;

// ---------------------------------------------------------------------------
// ResolvedTheme — shape of GET /api/v1/theme/resolved
// ---------------------------------------------------------------------------
interface ResolvedTheme {
  theme_id: number;
  theme_name: string;
  mode: string;
  source: string;
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

async function fetchResolvedTheme(carrierId: number): Promise<ResolvedTheme> {
  const { data } = await axios.get<ResolvedTheme>(
    `/api/v1/theme/resolved?carrier_id=${carrierId}`
  );
  return data;
}

/**
 * useTheme — Phase 6 full dynamic implementation.
 *
 * Fetches the resolved theme (all 13 tokens) from GET /api/v1/theme/resolved.
 * The resolution chain (user pref → carrier default → Default Dark) and
 * brand_color overlay are handled server-side.
 *
 * Behaviour guarantees:
 *   - Falls back to DEFAULT_DARK_TOKENS silently if the request fails.
 *   - SUPER_ADMIN: query disabled; DEFAULT_DARK_TOKENS applied unconditionally.
 *   - Always applies a complete 13-token set — never leaves :root in a partial state.
 *
 * Cache: TanStack Query staleTime 5 minutes (matches Redis TTL on the backend).
 */
export function useTheme(): void {
  const { user }      = useAuth();
  const { carrierId } = useTenantCarrier();
  const isTenantUser  = user !== null && user.role !== "SUPER_ADMIN";

  const { data: theme } = useQuery<ResolvedTheme | null, Error>({
    queryKey: ["theme", carrierId],
    queryFn:  () => fetchResolvedTheme(carrierId),
    staleTime: 5 * 60 * 1000,
    enabled:   isTenantUser && carrierId > 0,
    placeholderData: null,
    retry: false,
    // Errors swallowed — DEFAULT_DARK_TOKENS is the silent fallback.
  });

  useEffect(() => {
    // Map API field names (no dashes) → CSS custom property names (with dashes).
    // When theme is null (loading, disabled, or failed), fall back to DEFAULT_DARK_TOKENS.
    const cssMap: Record<string, string> = theme
      ? {
          "--bg":           `#${theme.bg}`,
          "--surface":      `#${theme.surface}`,
          "--surface-2":    `#${theme.surface2}`,
          "--border":       `#${theme.border_col}`,
          "--text-primary": `#${theme.text_primary}`,
          "--text-muted":   `#${theme.text_muted}`,
          "--brand":        `#${theme.brand}`,
          "--brand-dark":   `#${theme.brand_dark}`,
          "--accent":       `#${theme.accent}`,
          "--color-green":  `#${theme.color_green}`,
          "--color-amber":  `#${theme.color_amber}`,
          "--color-red":    `#${theme.color_red}`,
          "--color-blue":   `#${theme.color_blue}`,
        }
      : { ...DEFAULT_DARK_TOKENS };  // DEFAULT_DARK_TOKENS already has '#' prefix values

    const root = document.documentElement;
    Object.entries(cssMap).forEach(([property, value]) => {
      root.style.setProperty(property, value);
    });
  }, [theme]);
}