/**
 * useTenantFromSubdomain — 8 test cases (Phase 2, V9 S26)
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useTenantFromSubdomain } from "@/hooks/useTenantFromSubdomain";

function setHostname(hostname: string) {
  Object.defineProperty(window, "location", {
    value: { ...window.location, hostname },
    writable: true,
    configurable: true,
  });
}

describe("useTenantFromSubdomain", () => {
  const originalHostname = window.location.hostname;

  afterEach(() => {
    setHostname(originalHostname);
  });

  it("returns null on localhost", () => {
    setHostname("localhost");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns null on 127.0.0.1", () => {
    setHostname("127.0.0.1");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns null when only two hostname parts (no subdomain)", () => {
    setHostname("platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns subdomain for a valid three-part hostname", () => {
    setHostname("acme.platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBe("acme");
  });

  it("returns null for reserved subdomain 'www'", () => {
    setHostname("www.platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns null for reserved subdomain 'api'", () => {
    setHostname("api.platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns null for reserved subdomain 'admin'", () => {
    setHostname("admin.platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBeNull();
  });

  it("returns correct slug for valid subdomain 'beta-tenant'", () => {
    setHostname("beta-tenant.platform.local");
    const { result } = renderHook(() => useTenantFromSubdomain());
    expect(result.current).toBe("beta-tenant");
  });
});
