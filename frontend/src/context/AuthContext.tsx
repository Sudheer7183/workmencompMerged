/**
 * AuthContext — Phase 2 — Proper Keycloak session-based auth.
 *
 * PROBLEM WITH THE OLD APPROACH:
 *   kc.init({ onLoad: "login-required" }) redirects to Keycloak on EVERY page
 *   load. If Keycloak's in-memory session expired or the execution= param went
 *   stale, the user gets the "Unexpected error" screen and must restart Keycloak.
 *
 * NEW APPROACH — check-sso + silent iframe:
 *   1. kc.init({ onLoad: "check-sso", silentCheckSsoRedirectUri })
 *      → Keycloak checks for an existing session silently (hidden iframe).
 *      → If a valid session exists: authenticates with no redirect.
 *      → If no session: sets authenticated=false, shows our LoginPage.
 *        The user then clicks "Sign in" which calls kc.login() explicitly.
 *   2. Token refresh: kc.updateToken() called proactively 60s before expiry
 *      via kc.onTokenExpired. This keeps the session alive indefinitely for
 *      active users without any manual intervention.
 *   3. Refresh failure: if the refresh server-side token (SSO session) has
 *      truly expired, kc.updateToken() rejects → we show the LoginPage
 *      rather than the Keycloak "We are sorry" error screen.
 *
 * SILENT SSO SETUP:
 *   Requires a static file at /silent-check-sso.html served by Vite.
 *   This file is committed to frontend/public/silent-check-sso.html.
 *
 * DEV BYPASS:
 *   VITE_SKIP_AUTH=true skips Keycloak entirely and injects a hardcoded
 *   AUDITOR user for local development without Docker.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import Keycloak from "keycloak-js";
import axios from "axios";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type Role = "REVIEWER" | "AUDITOR" | "TENANT_ADMIN" | "SUPER_ADMIN";

export interface AuthUser {
  sub: string;
  email: string;
  role: Role;
  tenant_slug: string | null;
  onboarding_completed: boolean;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  token: string | null;
  login: () => void;
  logout: () => void;
  isLoading: boolean;
  completeOnboarding: () => void;
}

// ---------------------------------------------------------------------------
// Keycloak singleton — created once at module level.
// ---------------------------------------------------------------------------
const SKIP_AUTH = import.meta.env.VITE_SKIP_AUTH === "true";

let keycloak: Keycloak | null = null;
if (!SKIP_AUTH) {
  keycloak = new Keycloak({
    url:      import.meta.env.VITE_KEYCLOAK_URL      ?? "http://localhost:8080",
    realm:    import.meta.env.VITE_KEYCLOAK_REALM    ?? "audit-platform",
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "audit-platform-frontend",
  });
}

// ---------------------------------------------------------------------------
// Dev bypass user
// ---------------------------------------------------------------------------
const DEV_MOCK_USER: AuthUser = {
  sub: "dev-sub-001",
  email: "tenant-admin@demo.example.com",
  role: "TENANT_ADMIN",
  tenant_slug: "demo",
  onboarding_completed: true,
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Role extraction — handles both the V9 custom attribute mapper (single string)
// and the Keycloak native realm_access.roles array as fallback.
// ---------------------------------------------------------------------------
function extractRole(parsedToken: Record<string, unknown>): Role {
  const r = parsedToken["role"];
  if (r === "SUPER_ADMIN" || r === "TENANT_ADMIN" || r === "AUDITOR" || r === "REVIEWER") {
    return r;
  }
  const realmRoles =
    (parsedToken["realm_access"] as { roles?: string[] } | undefined)?.roles ?? [];
  const ROLE_MAP: Record<string, Role> = {
    super_admin:  "SUPER_ADMIN",
    tenant_admin: "TENANT_ADMIN",
    auditor:      "AUDITOR",
    reviewer:     "REVIEWER",
  };
  for (const role of realmRoles) {
    const mapped = ROLE_MAP[role.toLowerCase()];
    if (mapped) return mapped;
  }
  return "REVIEWER";
}

// ---------------------------------------------------------------------------
// Onboarding check — uses axios (headers already set by this point)
// ---------------------------------------------------------------------------
async function fetchOnboardingCompleted(): Promise<boolean> {
  try {
    const { data } = await axios.get<{ onboarding_completed: boolean }>(
      "/api/v1/tenant/users/me"
    );
    return data.onboarding_completed ?? false;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Token refresh helper — called by onTokenExpired and proactive timer
// ---------------------------------------------------------------------------
function scheduleTokenRefresh(
  kc: Keycloak,
  setToken: (t: string) => void,
  setUser: (u: null) => void,
): void {
  kc.onTokenExpired = () => {
    kc.updateToken(70)
      .then((refreshed) => {
        if (refreshed && kc.token) {
          setToken(kc.token);
          axios.defaults.headers.common["Authorization"] = `Bearer ${kc.token}`;
        }
      })
      .catch(() => {
        // SSO session truly expired — clear auth state.
        // ProtectedRoute will redirect to /login on the next render.
        delete axios.defaults.headers.common["Authorization"];
        delete axios.defaults.headers.common["X-Tenant-Slug"];
        setUser(null);
        setToken(null as unknown as string); // triggers isAuthenticated = false
      });
  };
}

// ---------------------------------------------------------------------------
// AuthProvider
// ---------------------------------------------------------------------------
export function AuthProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [user, setUser]       = useState<AuthUser | null>(SKIP_AUTH ? DEV_MOCK_USER : null);
  const [token, setToken]     = useState<string | null>(null);
  const [isLoading, setLoading] = useState(!SKIP_AUTH);

  // Pre-set axios headers for dev bypass so API calls work without a token
  if (SKIP_AUTH && DEV_MOCK_USER.tenant_slug) {
    axios.defaults.headers.common["X-Tenant-Slug"] = DEV_MOCK_USER.tenant_slug;
    // Dev bypass: no real token; backend must have SKIP_JWT_VERIFICATION=true
    axios.defaults.headers.common["Authorization"] = "Bearer dev-bypass";
  }

  // Guard against React StrictMode double-invoke
  const initialized = useRef(false);

  useEffect(() => {
    if (SKIP_AUTH) return;
    if (initialized.current) return;
    initialized.current = true;

    const kc = keycloak!;

    kc.init({
      // check-sso: silently checks for an existing Keycloak session via a hidden
      // iframe. Does NOT force a redirect if no session exists — we show our own
      // LoginPage instead, which is far better UX than the "We are sorry" screen.
      onLoad: "check-sso",
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      checkLoginIframe: false,
      pkceMethod: "S256",
    })
      .then(async (authenticated) => {
        if (!authenticated || !kc.token || !kc.tokenParsed) {
          // No active session — isLoading=false will render the LoginPage
          setLoading(false);
          return;
        }

        const parsed     = kc.tokenParsed as Record<string, unknown>;
        const role       = extractRole(parsed);
        const tenantSlug = (parsed["tenant_slug"] as string | undefined) ?? null;

        // Set axios defaults BEFORE any downstream API call
        axios.defaults.headers.common["Authorization"] = `Bearer ${kc.token}`;
        if (tenantSlug) {
          axios.defaults.headers.common["X-Tenant-Slug"] = tenantSlug;
        }

        const onboarding_completed =
          role === "SUPER_ADMIN" ? true : await fetchOnboardingCompleted();

        setToken(kc.token);
        setUser({
          sub:    kc.subject ?? "",
          email:  (parsed["email"] as string | undefined) ?? "",
          role,
          tenant_slug: tenantSlug,
          onboarding_completed,
        });

        // Wire up automatic token refresh
      scheduleTokenRefresh(
          kc,
          (t) => setToken(t),
          () => { setUser(null); setToken(null); },
        );

        // Proactive refresh interceptor — refreshes the token before EVERY
        // outgoing axios request if it expires within the next 60 seconds.
        // This prevents 401s from polling intervals (IngestionProgress) and
        // any other long-lived page that makes repeated API calls.
        axios.interceptors.request.use(async (config) => {
          if (!kc.isTokenExpired(60)) return config;
          try {
            await kc.updateToken(60);
            if (kc.token) {
              axios.defaults.headers.common["Authorization"] = `Bearer ${kc.token}`;
              config.headers["Authorization"] = `Bearer ${kc.token}`;
              setToken(kc.token);
            }
          } catch {
            // Refresh failed — let the request proceed; backend will 401
            // and the onTokenExpired handler will redirect to /login.
          }
          return config;
        });
      })
      .catch((err: unknown) => {
        // Init itself failed (Keycloak unreachable, realm doesn't exist, etc.)
        // Do NOT crash — show LoginPage so the user can try again.
        console.error("[AuthContext] Keycloak init error:", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = useCallback((): void => {
    if (SKIP_AUTH || !keycloak) return;
    // Explicit login — safe to call from a button click, no stale execution risk
    keycloak.login({
      redirectUri: `${window.location.origin}/dashboard`,
    });
  }, []);

  const logout = useCallback((): void => {
    if (SKIP_AUTH || !keycloak) {
      setUser(null);
      setToken(null);
      return;
    }
    // Clear axios headers before Keycloak redirects away
    delete axios.defaults.headers.common["Authorization"];
    delete axios.defaults.headers.common["X-Tenant-Slug"];
    keycloak.logout({
      redirectUri: `${window.location.origin}/login`,
    });
  }, []);

  const completeOnboarding = useCallback((): void => {
    setUser((prev) => (prev ? { ...prev, onboarding_completed: true } : prev));
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    token,
    login,
    logout,
    isLoading,
    completeOnboarding,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error("useAuth must be used within AuthProvider.");
  return ctx;
}

// ---------------------------------------------------------------------------
// Role hierarchy helper
// ---------------------------------------------------------------------------
const ROLE_ORDER: Record<Role, number> = {
  REVIEWER: 1, AUDITOR: 2, TENANT_ADMIN: 3, SUPER_ADMIN: 4,
};

export function hasRole(userRole: Role, required: Role): boolean {
  return ROLE_ORDER[userRole] >= ROLE_ORDER[required];
}
