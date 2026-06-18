/**
 * TenantLogo — Phase 2 full implementation.
 *
 * V9 S14.2 logo resolution chain:
 *   1. tenant_branding.logo_url (or logo_dark_url for dark variant)
 *   2. Text fallback: "the Audit Platform"
 *
 * CORS note: uses relative URL /api/v1/tenant/branding so the Vite proxy
 * forwards the request to the backend. Never use an absolute localhost URL.
 *
 * SUPER_ADMIN note: SUPER_ADMIN has no tenant so the branding endpoint
 * returns 400. The fetch is disabled for SUPER_ADMIN users and the text
 * fallback is rendered instead.
 *
 * BEM classes:
 *   .tenant-logo           — root wrapper
 *   .tenant-logo__img      — <img> element
 *   .tenant-logo__text     — text fallback
 *   .tenant-logo--dark     — dark variant modifier
 */

import React from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";

interface BrandingResponse {
  logo_url: string | null;
  logo_dark_url: string | null;
  brand_color: string | null;
}

/**
 * Fetches tenant branding via the Vite proxy.
 * Uses a relative URL — never an absolute http://localhost:8000 URL.
 */
async function fetchTenantBranding(): Promise<BrandingResponse> {
  const { data } = await axios.get<BrandingResponse>("/api/v1/tenant/branding");
  return data;
}

export interface TenantLogoProps {
  /** Light (default) or dark — selects logo_url vs logo_dark_url */
  variant?: "light" | "dark";
  /** Height in px — width scales proportionally via object-fit: contain */
  height?: number;
  /** Additional BEM modifier or utility class */
  className?: string;
}

export function TenantLogo({
  variant = "light",
  height = 32,
  className,
}: TenantLogoProps): React.JSX.Element {
  const { user } = useAuth();

  // SUPER_ADMIN has no tenant context — disable the branding fetch.
  const isTenantUser = user !== null && user.role !== "SUPER_ADMIN";

  const { data: branding } = useQuery<BrandingResponse, Error>({
    queryKey: ["tenant-branding"],
    queryFn: fetchTenantBranding,
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled: isTenantUser,
  });

  // V9 S14.2 — logo resolution chain
  const logoUrl =
    variant === "dark"
      ? (branding?.logo_dark_url ?? branding?.logo_url ?? null)
      : (branding?.logo_url ?? null);

  const blockClass = [
    "tenant-logo",
    variant === "dark" ? "tenant-logo--dark" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  if (logoUrl) {
    return (
      <span className={blockClass}>
        <img
          src={logoUrl}
          alt="Organisation logo"
          className="tenant-logo__img"
          style={{ height, width: "auto", objectFit: "contain" }}
        />
      </span>
    );
  }

  return (
    <span className={blockClass}>
      <span className="tenant-logo__text">the Audit Platform</span>
    </span>
  );
}

export default TenantLogo;
