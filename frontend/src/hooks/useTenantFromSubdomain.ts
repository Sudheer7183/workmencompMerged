/**
 * useTenantFromSubdomain — V9 S26
 *
 * Extracts the tenant slug from window.location.hostname.
 * Returns null for:
 *   - localhost / 127.0.0.1 (dev mode — no subdomain routing)
 *   - hostnames with fewer than three parts (no subdomain present)
 *   - reserved subdomains (www, api, admin, etc.)
 *
 * Used by:
 *   - App.tsx — cross-origin JWT guard (redirect to correct subdomain)
 *   - TenantCarrierContext — to validate JWT tenant matches current host
 */

const RESERVED_SUBDOMAINS = new Set([
  "www",
  "api",
  "app",
  "admin",
  "platform",
  "mail",
  "auth",
  "health",
  "docs",
  "redoc",
  "cdn",
  "assets",
  "static",
]);

/**
 * Returns the tenant slug derived from the current subdomain,
 * or null when running on localhost / a reserved / missing subdomain.
 *
 * Pure function — reads window.location.hostname at call time.
 * Calling from a custom hook ensures React can re-run on route changes.
 */
export function useTenantFromSubdomain(): string | null {
  const host = window.location.hostname;

  // Exact localhost — no subdomain routing in dev
  if (host === "localhost" || host === "127.0.0.1") {
    return null;
  }

  const parts = host.split(".");

  // Special case: demo.localhost (2 parts, TLD is "localhost")
  // Chrome resolves *.localhost to 127.0.0.1 natively — no hosts file needed.
  if (parts.length === 2 && parts[1] === "localhost") {
    const subdomain = parts[0]?.toLowerCase();
    if (!subdomain || RESERVED_SUBDOMAINS.has(subdomain)) return null;
    return subdomain;
  }

  // Production: require subdomain.domain.tld (3+ parts)
  if (parts.length < 3) {
    return null;
  }

  const subdomain = parts.at(0)?.toLowerCase();
  if (!subdomain) return null;
  if (RESERVED_SUBDOMAINS.has(subdomain)) return null;

  return subdomain;
}
