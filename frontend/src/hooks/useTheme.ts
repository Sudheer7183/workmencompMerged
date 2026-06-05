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
 */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";

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

/** Applies a token map to :root CSS variables. */
function applyTokens(tokens: Record<string, string>): void {
  const root = document.documentElement;
  Object.entries(tokens).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });
}

// ---------------------------------------------------------------------------
// Branding response shape — matches GET /api/v1/tenant/branding
// ---------------------------------------------------------------------------
interface BrandingResponse {
  brand_color: string | null;
  logo_url: string | null;
  logo_dark_url: string | null;
}

/**
 * Fetches tenant branding via the Vite proxy.
 * Relative URL → proxied to backend by Vite dev server.
 * Never use an absolute URL here.
 */
async function fetchTenantBranding(): Promise<BrandingResponse> {
  const { data } = await axios.get<BrandingResponse>("/api/v1/tenant/branding");
  return data;
}

/**
 * useTheme
 *
 * Phase 2:
 * - Always applies all 12 non-brand Default Dark tokens.
 * - For non-SUPER_ADMIN users: fetches tenant_branding.brand_color and
 *   overrides only --brand. All other tokens remain hardcoded Default Dark.
 * - For SUPER_ADMIN: branding fetch is skipped; --brand uses the default.
 */
export function useTheme(): void {
  const { user } = useAuth();

  // SUPER_ADMIN has no tenant — skip the branding fetch entirely.
  // enabled: false prevents the query from ever firing.
  const isTenantUser = user !== null && user.role !== "SUPER_ADMIN";

  const { data: branding } = useQuery<BrandingResponse, Error>({
    queryKey: ["tenant-branding"],
    queryFn: fetchTenantBranding,
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled: isTenantUser,
    // Errors are intentionally swallowed — branding is cosmetic
  });

  useEffect(() => {
    // Apply the 12 non-brand Default Dark tokens unconditionally.
    const nonBrandTokens: Record<string, string> = {
      "--bg":           DEFAULT_DARK_TOKENS["--bg"],
      "--surface":      DEFAULT_DARK_TOKENS["--surface"],
      "--surface-2":    DEFAULT_DARK_TOKENS["--surface-2"],
      "--border":       DEFAULT_DARK_TOKENS["--border"],
      "--text-primary": DEFAULT_DARK_TOKENS["--text-primary"],
      "--text-muted":   DEFAULT_DARK_TOKENS["--text-muted"],
      "--brand-dark":   DEFAULT_DARK_TOKENS["--brand-dark"],
      "--accent":       DEFAULT_DARK_TOKENS["--accent"],
      "--color-green":  DEFAULT_DARK_TOKENS["--color-green"],
      "--color-amber":  DEFAULT_DARK_TOKENS["--color-amber"],
      "--color-red":    DEFAULT_DARK_TOKENS["--color-red"],
      "--color-blue":   DEFAULT_DARK_TOKENS["--color-blue"],
    };
    applyTokens(nonBrandTokens);

    // Phase 2 — brand_color override: V9 S14.3 + Theme Addendum S3
    // tenant_branding.brand_color overrides ONLY --brand (not --brand-dark).
    // Value is stored as 6-char hex WITHOUT leading "#".
    const brandHex =
      branding?.brand_color != null && branding.brand_color.length === 6
        ? `#${branding.brand_color}`
        : DEFAULT_DARK_TOKENS["--brand"];

    document.documentElement.style.setProperty("--brand", brandHex);
  }, [branding]);
}