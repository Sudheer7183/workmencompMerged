import React from "react";
import { Navigate } from "react-router-dom";
import { hasRole, useAuth, type Role } from "@/context/AuthContext";

interface ProtectedRouteProps {
  /** Minimum role required to access this route */
  requiredRole?: Role;
  children: React.ReactNode;
}

/**
 * ProtectedRoute — Phase 2.
 *
 * - Redirects to /login when the user is not authenticated.
 * - Redirects to /unauthorized when the user lacks the required role.
 * - Redirects TENANT_ADMIN with onboarding_completed = false to /onboarding.
 *   The onboarding wizard is a blocking redirect — the user cannot skip it.
 */
export default function ProtectedRoute({
  requiredRole = "REVIEWER",
  children,
}: ProtectedRouteProps): React.JSX.Element {
  const { user, isAuthenticated, isLoading } = useAuth();

  // While Keycloak is initialising, render nothing (avoid flash-of-redirect)
  if (isLoading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          color: "var(--text-muted)",
          fontSize: "14px",
        }}
      >
        Authenticating…
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!hasRole(user.role, requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  // Phase 2: TENANT_ADMIN must complete onboarding before accessing any route.
  // Exempt the /onboarding route itself to prevent an infinite redirect loop.
  if (
    user.role === "TENANT_ADMIN" &&
    !user.onboarding_completed &&
    window.location.pathname !== "/onboarding"
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
