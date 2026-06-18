

// import React, { useEffect } from "react";
// import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
// import { useTheme } from "@/hooks/useTheme";
// import { useAuth } from "@/context/AuthContext";
// import { useTenantCarrier } from "@/context/TenantCarrierContext";
// import { useTenantFromSubdomain } from "@/hooks/useTenantFromSubdomain";
// import { TenantLogo } from "@/components/TenantLogo";
// import { ModeToggle } from "@/components/ModeToggle";
// import { UserThemePicker } from "@/components/UserThemePicker";
// import ProtectedRoute from "@/routes/ProtectedRoute";

// // Phase 1 features
// import { DashboardPage } from "@/features/dashboard/DashboardPage";
// import { PoliciesListPage } from "@/features/policies/PoliciesListPage";
// import { PolicyDetailPage } from "@/features/policies/PolicyDetailPage";

// // Phase 2 — Platform Admin (SUPER_ADMIN)
// import { PlatformDashboard } from "@/features/administration/platform-admin/PlatformDashboard";
// import { TenantsList } from "@/features/administration/platform-admin/TenantsList";
// import { TenantDetail } from "@/features/administration/platform-admin/TenantDetail";
// import { WizardShell } from "@/features/administration/platform-admin/TenantCreationWizard/WizardShell";
// import { CarriersList } from "@/features/administration/platform-admin/CarriersList";
// import { PlatformThemeEditor } from "@/features/administration/platform-admin/PlatformThemeEditor";

// // Phase 2 — Tenant Admin
// import { OrganizationSettings } from "@/features/administration/organization/OrganizationSettings";
// import { UsersList } from "@/features/administration/user-management/UsersList";

// // Phase 2 — Onboarding
// import { OnboardingWizard } from "@/features/onboarding/OnboardingWizard";

// // Phase 3 — Ingestion pipeline
// import { AuditRunnerPage }    from "@/features/ingestion/AuditRunnerPage";
// import { FieldMappingReview } from "@/features/ingestion/FieldMappingReview";
// import { IngestionProgress }  from "@/features/ingestion/IngestionProgress";

// // Phase 4 — Exception tracking
// import { ExceptionTracker }   from "@/features/ingestion/ExceptionTracker";

// // Phase 3 — Carrier Configuration Hub
// import { CarrierConfigHub }   from "@/features/carrier-config";
// import { DatabaseCleanupPage } from "@/features/administration/database-cleanup";
// import { AIConfigPage } from "@/features/carrier-config/components/AIConfigPage";

// // ---------------------------------------------------------------------------
// // Cross-origin guard — V9 S26
// // Only active in production (not on localhost).
// // ---------------------------------------------------------------------------
// function useCrossOriginGuard(): void {
//   const { user } = useAuth();
//   const tenantSlug = useTenantFromSubdomain();

//   useEffect(() => {
//     if (!user) return;
//     if (user.role === "SUPER_ADMIN") return;

//     const platformDomain = import.meta.env.VITE_PLATFORM_DOMAIN as string | undefined;
//     if (!platformDomain) return;
//     if (platformDomain === "localhost" || platformDomain === "127.0.0.1") return;

//     if (!tenantSlug && user.tenant_slug) {
//       window.location.href = `https://${user.tenant_slug}.${platformDomain}/dashboard`;
//       return;
//     }
//     if (tenantSlug && user.tenant_slug && tenantSlug !== user.tenant_slug) {
//       window.location.href = `https://${user.tenant_slug}.${platformDomain}/dashboard`;
//     }
//   }, [user, tenantSlug]);
// }

// // ---------------------------------------------------------------------------
// // LogoutIcon — inline SVG, no dependency
// // ---------------------------------------------------------------------------
// function LogoutIcon(): React.JSX.Element {
//   return (
//     <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
//       <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
//       <polyline points="16 17 21 12 16 7" />
//       <line x1="21" y1="12" x2="9" y2="12" />
//     </svg>
//   );
// }

// // ---------------------------------------------------------------------------
// // TopNav — matches the reference HTML nav exactly
// // ---------------------------------------------------------------------------
// function TopNav(): React.JSX.Element {
//   const { user, logout } = useAuth();
//   const { carrierId, setCarrierId, availableCarriers } = useTenantCarrier();
//   const navigate = useNavigate();

//   if (!user) return <></>;

//   const isSuperAdmin    = user.role === "SUPER_ADMIN";
//   const isTenantAdmin   = user.role === "TENANT_ADMIN";
//   const isSingleCarrier = availableCarriers.length <= 1;

//   const linkClass = ({ isActive }: { isActive: boolean }): string =>
//     ["topnav__link", isActive ? "topnav__link--active" : ""].filter(Boolean).join(" ");

//   function handleLogout(): void {
//     logout();
//     navigate("/login", { replace: true });
//   }

//   return (
//     <nav className="topnav">
//       {/* ── Brand ── */}
//       <div className="topnav__brand">
//         <div className="topnav__logo">
//           <TenantLogo variant="light" height={16} />
//         </div>
//         <div>
//           <div className="topnav__label">Carrier Portal</div>
//           <div className="topnav__title">Workers' Comp Audit</div>
//         </div>
//       </div>

//       {/* ── Navigation links — role-gated ── */}
//       <div className="topnav__links">
//         {isSuperAdmin ? (
//           <>
//             <NavLink to="/platform"          className={linkClass} end>Platform</NavLink>
//             <NavLink to="/platform/tenants"  className={linkClass}>Tenants</NavLink>
//             <NavLink to="/platform/carriers" className={linkClass}>Carriers</NavLink>
//             <NavLink to="/platform/themes"   className={linkClass}>Themes</NavLink>
//           </>
//         ) : (
//           <>
//             <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
//             <NavLink to="/policies"  className={linkClass}>Policies</NavLink>
//             {isTenantAdmin && (
//               <>
//                 <NavLink to="/admin/organization"     className={linkClass}>Organisation</NavLink>
//                 <NavLink to="/admin/users"            className={linkClass}>Users</NavLink>
//                 <NavLink to="/admin/ai-config"        className={linkClass}>AI Config</NavLink>
//                 <NavLink to="/admin/database-cleanup" className={linkClass}>DB Cleanup</NavLink>
//               </>
//             )}
//             {/* Audit Runner is accessible to AUDITOR and above */}
//             {(user.role === "AUDITOR" || isTenantAdmin) && (
//               <NavLink to="/audit-runner" className={linkClass}>Audit Runner</NavLink>
//             )}
//             {isTenantAdmin && (
//               <NavLink to={`/admin/carriers/${carrierId}/config`} className={linkClass}>Config</NavLink>
//             )}
//           </>
//         )}
//       </div>

//       {/* ── Mode toggle + carrier switcher + user + logout ── */}
//       <div className="topnav__right">
//         <ModeToggle />
//         {/* Carrier switcher — only shown when tenant has multiple carriers */}
//         {!isSuperAdmin && !isSingleCarrier && (
//           <div className="topnav__carrier-switcher" data-testid="carrier-switcher">
//             <label className="topnav__carrier-label" htmlFor="carrier-select">
//               Carrier
//             </label>
//             <select
//               id="carrier-select"
//               className="topnav__carrier-select"
//               value={carrierId}
//               onChange={(e) => setCarrierId(Number(e.target.value))}
//               aria-label="Switch active carrier"
//             >
//               {availableCarriers.map((c) => (
//                 <option key={c.carrier_id} value={c.carrier_id}>
//                   {c.carrier_name}
//                 </option>
//               ))}
//             </select>
//           </div>
//         )}
//         <div
//           className="topnav__user"
//           data-testid="user-avatar-btn"
//           tabIndex={0}
//           role="button"
//           aria-label="User menu"
//         >
//           <span className="topnav__user-email">{user.email}</span>
//           <span className="topnav__user-role">{user.role.replace("_", " ")}</span>
//           {/*
//             FIX: removed style={{ display: "none", position: "absolute", ... }} inline styles.
//             Inline display:none permanently hides the dropdown regardless of CSS hover rules.
//             Visibility and positioning are now controlled exclusively by components.css:
//               .topnav__user-dropdown          { display: none; position: absolute; ... }
//               .topnav__user:hover .topnav__user-dropdown,
//               .topnav__user:focus-within .topnav__user-dropdown { display: block; }
//           */}
//           <div
//             className="topnav__user-dropdown"
//             data-testid="my-theme-link"
//           >
//             <UserThemePicker />
//           </div>
//         </div>
//         <button
//           className="topnav__logout"
//           title="Sign out"
//           onClick={handleLogout}
//           aria-label="Sign out"
//         >
//           <LogoutIcon />
//         </button>
//       </div>
//     </nav>
//   );
// }

// // ---------------------------------------------------------------------------
// // LoginPage — shown when Keycloak silently fails to detect a session
// // ---------------------------------------------------------------------------
// function LoginPage(): React.JSX.Element {
//   const { login, isLoading } = useAuth();
//   const skipAuth = import.meta.env.VITE_SKIP_AUTH === "true";

//   return (
//     <div className="auth-page">
//       <div className="topnav__logo" style={{ width: 48, height: 48, fontSize: 20, marginBottom: 8 }}>
//         WC
//       </div>
//       <h1 className="auth-page__title">Workers' Comp Audit Platform</h1>
//       <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Sign in to continue</p>
//       {isLoading ? (
//         <p style={{ color: "var(--text-muted)" }}>Authenticating…</p>
//       ) : (
//         <button
//           className="btn btn--primary"
//           style={{ marginTop: 8 }}
//           onClick={skipAuth ? () => window.location.reload() : login}
//         >
//           {skipAuth ? "Continue (Dev Mode)" : "Sign in with Keycloak"}
//         </button>
//       )}
//     </div>
//   );
// }

// function UnauthorizedPage(): React.JSX.Element {
//   return (
//     <div className="auth-page">
//       <h1 className="auth-page__title">403 — Access denied</h1>
//       <p style={{ color: "var(--text-muted)" }}>You do not have permission to view this page.</p>
//       <a href="/dashboard" className="btn btn--secondary">Go to Dashboard</a>
//     </div>
//   );
// }

// // ---------------------------------------------------------------------------
// // PoliciesRouteWrapper — Forces PoliciesListPage to remount on every navigation
// // to /policies, so initialFilters from location.state are always read fresh.
// // ---------------------------------------------------------------------------
// function PoliciesRouteWrapper(): React.JSX.Element {
//   const location = useLocation();
//   return (
//     <ProtectedRoute requiredRole="REVIEWER">
//       <PoliciesListPage key={location.key} />
//     </ProtectedRoute>
//   );
// }

// // ---------------------------------------------------------------------------
// // App root
// // ---------------------------------------------------------------------------
// export default function App(): React.JSX.Element {
//   useTheme();
//   useCrossOriginGuard();

//   const { isLoading, isAuthenticated } = useAuth();

//   if (isLoading) {
//     return (
//       <div className="app-loading">
//         <span>Loading…</span>
//       </div>
//     );
//   }

//   return (
//     <div className="app-shell">
//       {/* Top nav only shown when authenticated */}
//       {isAuthenticated && <TopNav />}

//       <Routes>
//         {/* Public */}
//         <Route path="/login"        element={<LoginPage />} />
//         <Route path="/unauthorized" element={<UnauthorizedPage />} />

//         {/* Onboarding — TENANT_ADMIN first-login (blocking) */}
//         <Route
//           path="/onboarding"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <OnboardingWizard />
//             </ProtectedRoute>
//           }
//         />

//         {/* Standard tenant/auditor/reviewer routes */}
//         <Route path="/" element={<Navigate to="/dashboard" replace />} />
//         <Route
//           path="/dashboard"
//           element={
//             <ProtectedRoute requiredRole="REVIEWER">
//               <DashboardPage />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/policies"
//           element={<PoliciesRouteWrapper />}
//         />
//         <Route
//           path="/policies/:policyId"
//           element={
//             <ProtectedRoute requiredRole="REVIEWER">
//               <PolicyDetailPage />
//             </ProtectedRoute>
//           }
//         />

//         {/* Tenant Admin */}
//         <Route
//           path="/admin/organization"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <OrganizationSettings />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/admin/users"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <UsersList />
//             </ProtectedRoute>
//           }
//         />

//         {/* Phase 3 — Audit Runner / Ingestion pipeline */}
//         <Route
//           path="/audit-runner"
//           element={
//             <ProtectedRoute requiredRole="AUDITOR">
//               <AuditRunnerPage />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/audit-runner/:runId/mapping"
//           element={
//             <ProtectedRoute requiredRole="AUDITOR">
//               <FieldMappingReview />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/audit-runner/:runId/progress"
//           element={
//             <ProtectedRoute requiredRole="AUDITOR">
//               <IngestionProgress />
//             </ProtectedRoute>
//           }
//         />

//         {/* Phase 4 — Exception Tracker (REVIEWER+) */}
//         <Route
//           path="/audit-runner/:runId/exceptions"
//           element={
//             <ProtectedRoute requiredRole="REVIEWER">
//               <ExceptionTracker />
//             </ProtectedRoute>
//           }
//         />

//         {/* Phase 6 — Database Cleanup (TENANT_ADMIN) */}
//         <Route
//           path="/admin/database-cleanup"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <DatabaseCleanupPage />
//             </ProtectedRoute>
//           }
//         />

//         {/* Phase 7C — AI Config standalone page (TENANT_ADMIN) */}
//         <Route
//           path="/admin/ai-config"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <AIConfigPage />
//             </ProtectedRoute>
//           }
//         />

//         {/* Phase 3 — Carrier Config Hub (TENANT_ADMIN) */}
//         <Route
//           path="/admin/carriers/:carrierId/config"
//           element={
//             <ProtectedRoute requiredRole="TENANT_ADMIN">
//               <CarrierConfigHub />
//             </ProtectedRoute>
//           }
//         />

//         {/* Platform Admin — SUPER_ADMIN only */}
//         <Route
//           path="/platform"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <PlatformDashboard />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/platform/tenants"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <TenantsList />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/platform/tenants/new"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <WizardShell />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/platform/tenants/:slug"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <TenantDetail />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/platform/carriers"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <CarriersList />
//             </ProtectedRoute>
//           }
//         />
//         <Route
//           path="/platform/themes"
//           element={
//             <ProtectedRoute requiredRole="SUPER_ADMIN">
//               <PlatformThemeEditor />
//             </ProtectedRoute>
//           }
//         />

//         <Route path="*" element={<Navigate to="/dashboard" replace />} />
//       </Routes>
//     </div>
//   );
// }

import React, { useEffect } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/context/AuthContext";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useTenantFromSubdomain } from "@/hooks/useTenantFromSubdomain";
import { TenantLogo } from "@/components/TenantLogo";
import { ModeToggle } from "@/components/ModeToggle";
import { UserThemePicker } from "@/components/UserThemePicker";
import ProtectedRoute from "@/routes/ProtectedRoute";

// Phase 1 features
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { PoliciesListPage } from "@/features/policies/PoliciesListPage";
import { PolicyDetailPage } from "@/features/policies/PolicyDetailPage";

// Phase 2 — Platform Admin (SUPER_ADMIN)
import { PlatformDashboard } from "@/features/administration/platform-admin/PlatformDashboard";
import { TenantsList } from "@/features/administration/platform-admin/TenantsList";
import { TenantDetail } from "@/features/administration/platform-admin/TenantDetail";
import { WizardShell } from "@/features/administration/platform-admin/TenantCreationWizard/WizardShell";
import { CarriersList } from "@/features/administration/platform-admin/CarriersList";
import { PlatformThemeEditor } from "@/features/administration/platform-admin/PlatformThemeEditor";

// Phase 2 — Tenant Admin
import { OrganizationSettings } from "@/features/administration/organization/OrganizationSettings";
import { UsersList } from "@/features/administration/user-management/UsersList";

// Phase 2 — Onboarding
import { OnboardingWizard } from "@/features/onboarding/OnboardingWizard";

// Phase 3 — Ingestion pipeline
import { AuditRunnerPage }    from "@/features/ingestion/AuditRunnerPage";
import { BulkUploadPage }     from "@/features/ingestion/BulkUploadPage";
import { FieldMappingReview } from "@/features/ingestion/FieldMappingReview";
import { IngestionProgress }  from "@/features/ingestion/IngestionProgress";

// Phase 4 — Exception tracking
import { ExceptionTracker }   from "@/features/ingestion/ExceptionTracker";

// Phase 3 — Carrier Configuration Hub
import { CarrierConfigHub }   from "@/features/carrier-config";
import { DatabaseCleanupPage } from "@/features/administration/database-cleanup";
import { AIConfigPage } from "@/features/carrier-config/components/AIConfigPage";

// ---------------------------------------------------------------------------
// Cross-origin guard — V9 S26
// Only active in production (not on localhost).
// ---------------------------------------------------------------------------
function useCrossOriginGuard(): void {
  const { user } = useAuth();
  const tenantSlug = useTenantFromSubdomain();

  useEffect(() => {
    if (!user) return;
    if (user.role === "SUPER_ADMIN") return;

    const platformDomain = import.meta.env.VITE_PLATFORM_DOMAIN as string | undefined;
    if (!platformDomain) return;
    if (platformDomain === "localhost" || platformDomain === "127.0.0.1") return;

    if (!tenantSlug && user.tenant_slug) {
      window.location.href = `https://${user.tenant_slug}.${platformDomain}/dashboard`;
      return;
    }
    if (tenantSlug && user.tenant_slug && tenantSlug !== user.tenant_slug) {
      window.location.href = `https://${user.tenant_slug}.${platformDomain}/dashboard`;
    }
  }, [user, tenantSlug]);
}

// ---------------------------------------------------------------------------
// LogoutIcon — inline SVG, no dependency
// ---------------------------------------------------------------------------
function LogoutIcon(): React.JSX.Element {
  return (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// TopNav — matches the reference HTML nav exactly
// ---------------------------------------------------------------------------
function TopNav(): React.JSX.Element {
  const { user, logout } = useAuth();
  const { carrierId, setCarrierId, availableCarriers } = useTenantCarrier();
  const navigate = useNavigate();

  if (!user) return <></>;

  const isSuperAdmin    = user.role === "SUPER_ADMIN";
  const isTenantAdmin   = user.role === "TENANT_ADMIN";
  const isSingleCarrier = availableCarriers.length <= 1;

  const linkClass = ({ isActive }: { isActive: boolean }): string =>
    ["topnav__link", isActive ? "topnav__link--active" : ""].filter(Boolean).join(" ");

  function handleLogout(): void {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="topnav">
      {/* ── Brand ── */}
      <div className="topnav__brand">
        <div className="topnav__logo">
          <TenantLogo variant="light" height={16} />
        </div>
        <div>
          <div className="topnav__label">Carrier Portal</div>
          <div className="topnav__title">Workers' Comp Audit</div>
        </div>
      </div>

      {/* ── Navigation links — role-gated ── */}
      <div className="topnav__links">
        {isSuperAdmin ? (
          <>
            <NavLink to="/platform"          className={linkClass} end>Platform</NavLink>
            <NavLink to="/platform/tenants"  className={linkClass}>Tenants</NavLink>
            <NavLink to="/platform/carriers" className={linkClass}>Carriers</NavLink>
            <NavLink to="/platform/themes"   className={linkClass}>Themes</NavLink>
          </>
        ) : (
          <>
            <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
            <NavLink to="/policies"  className={linkClass}>Policies</NavLink>
            {isTenantAdmin && (
              <>
                <NavLink to="/admin/organization"     className={linkClass}>Organisation</NavLink>
                <NavLink to="/admin/users"            className={linkClass}>Users</NavLink>
                <NavLink to="/admin/ai-config"        className={linkClass}>AI Config</NavLink>
                <NavLink to="/admin/database-cleanup" className={linkClass}>DB Cleanup</NavLink>
              </>
            )}
            {/* Audit Runner is accessible to AUDITOR and above */}
            {(user.role === "AUDITOR" || isTenantAdmin) && (
              <NavLink to="/audit-runner" className={linkClass}>Audit Runner</NavLink>
            )}
            {isTenantAdmin && (
              <NavLink to={`/admin/carriers/${carrierId}/config`} className={linkClass}>Config</NavLink>
            )}
          </>
        )}
      </div>

      {/* ── Mode toggle + carrier switcher + user + logout ── */}
      <div className="topnav__right">
        <ModeToggle />
        {/* Carrier switcher — only shown when tenant has multiple carriers */}
        {!isSuperAdmin && !isSingleCarrier && (
          <div className="topnav__carrier-switcher" data-testid="carrier-switcher">
            <label className="topnav__carrier-label" htmlFor="carrier-select">
              Carrier
            </label>
            <select
              id="carrier-select"
              className="topnav__carrier-select"
              value={carrierId}
              onChange={(e) => setCarrierId(Number(e.target.value))}
              aria-label="Switch active carrier"
            >
              {availableCarriers.map((c) => (
                <option key={c.carrier_id} value={c.carrier_id}>
                  {c.carrier_name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div
          className="topnav__user"
          data-testid="user-avatar-btn"
          tabIndex={0}
          role="button"
          aria-label="User menu"
        >
          <span className="topnav__user-email">{user.email}</span>
          <span className="topnav__user-role">{user.role.replace("_", " ")}</span>
          {/*
            FIX: removed style={{ display: "none", position: "absolute", ... }} inline styles.
            Inline display:none permanently hides the dropdown regardless of CSS hover rules.
            Visibility and positioning are now controlled exclusively by components.css:
              .topnav__user-dropdown          { display: none; position: absolute; ... }
              .topnav__user:hover .topnav__user-dropdown,
              .topnav__user:focus-within .topnav__user-dropdown { display: block; }
          */}
          <div
            className="topnav__user-dropdown"
            data-testid="my-theme-link"
          >
            <UserThemePicker />
          </div>
        </div>
        <button
          className="topnav__logout"
          title="Sign out"
          onClick={handleLogout}
          aria-label="Sign out"
        >
          <LogoutIcon />
        </button>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// LoginPage — shown when Keycloak silently fails to detect a session
// ---------------------------------------------------------------------------
function LoginPage(): React.JSX.Element {
  const { login, isLoading } = useAuth();
  const skipAuth = import.meta.env.VITE_SKIP_AUTH === "true";

  return (
    <div className="auth-page">
      <div className="topnav__logo" style={{ width: 48, height: 48, fontSize: 20, marginBottom: 8 }}>
        WC
      </div>
      <h1 className="auth-page__title">Workers' Comp Audit Platform</h1>
      <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Sign in to continue</p>
      {isLoading ? (
        <p style={{ color: "var(--text-muted)" }}>Authenticating…</p>
      ) : (
        <button
          className="btn btn--primary"
          style={{ marginTop: 8 }}
          onClick={skipAuth ? () => window.location.reload() : login}
        >
          {skipAuth ? "Continue (Dev Mode)" : "Sign in with Keycloak"}
        </button>
      )}
    </div>
  );
}

function UnauthorizedPage(): React.JSX.Element {
  return (
    <div className="auth-page">
      <h1 className="auth-page__title">403 — Access denied</h1>
      <p style={{ color: "var(--text-muted)" }}>You do not have permission to view this page.</p>
      <a href="/dashboard" className="btn btn--secondary">Go to Dashboard</a>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PoliciesRouteWrapper — Forces PoliciesListPage to remount on every navigation
// to /policies, so initialFilters from location.state are always read fresh.
// ---------------------------------------------------------------------------
function PoliciesRouteWrapper(): React.JSX.Element {
  const location = useLocation();
  return (
    <ProtectedRoute requiredRole="REVIEWER">
      <PoliciesListPage key={location.key} />
    </ProtectedRoute>
  );
}

// ---------------------------------------------------------------------------
// App root
// ---------------------------------------------------------------------------
export default function App(): React.JSX.Element {
  useTheme();
  useCrossOriginGuard();

  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return (
      <div className="app-loading">
        <span>Loading…</span>
      </div>
    );
  }

  return (
    <div className="app-shell">
      {/* Top nav only shown when authenticated */}
      {isAuthenticated && <TopNav />}

      <Routes>
        {/* Public */}
        <Route path="/login"        element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />

        {/* Onboarding — TENANT_ADMIN first-login (blocking) */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <OnboardingWizard />
            </ProtectedRoute>
          }
        />

        {/* Standard tenant/auditor/reviewer routes */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute requiredRole="REVIEWER">
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/policies"
          element={<PoliciesRouteWrapper />}
        />
        <Route
          path="/policies/:policyId"
          element={
            <ProtectedRoute requiredRole="REVIEWER">
              <PolicyDetailPage />
            </ProtectedRoute>
          }
        />

        {/* Tenant Admin */}
        <Route
          path="/admin/organization"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <OrganizationSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <UsersList />
            </ProtectedRoute>
          }
        />

        {/* Phase 3 — Audit Runner / Ingestion pipeline */}
        <Route
          path="/audit-runner"
          element={
            <ProtectedRoute requiredRole="AUDITOR">
              <AuditRunnerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/bulk-upload"
              element={
              <ProtectedRoute>
                  <BulkUploadPage />
              </ProtectedRoute>
              }
            />
            <Route
          path="/audit-runner/:runId/mapping"
          element={
            <ProtectedRoute requiredRole="AUDITOR">
              <FieldMappingReview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/audit-runner/:runId/progress"
          element={
            <ProtectedRoute requiredRole="AUDITOR">
              <IngestionProgress />
            </ProtectedRoute>
          }
        />

        {/* Phase 4 — Exception Tracker (REVIEWER+) */}
        <Route
          path="/audit-runner/:runId/exceptions"
          element={
            <ProtectedRoute requiredRole="REVIEWER">
              <ExceptionTracker />
            </ProtectedRoute>
          }
        />

        {/* Phase 6 — Database Cleanup (TENANT_ADMIN) */}
        <Route
          path="/admin/database-cleanup"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <DatabaseCleanupPage />
            </ProtectedRoute>
          }
        />

        {/* Phase 7C — AI Config standalone page (TENANT_ADMIN) */}
        <Route
          path="/admin/ai-config"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <AIConfigPage />
            </ProtectedRoute>
          }
        />

        {/* Phase 3 — Carrier Config Hub (TENANT_ADMIN) */}
        <Route
          path="/admin/carriers/:carrierId/config"
          element={
            <ProtectedRoute requiredRole="TENANT_ADMIN">
              <CarrierConfigHub />
            </ProtectedRoute>
          }
        />

        {/* Platform Admin — SUPER_ADMIN only */}
        <Route
          path="/platform"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <PlatformDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platform/tenants"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <TenantsList />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platform/tenants/new"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <WizardShell />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platform/tenants/:slug"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <TenantDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platform/carriers"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <CarriersList />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platform/themes"
          element={
            <ProtectedRoute requiredRole="SUPER_ADMIN">
              <PlatformThemeEditor />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </div>
  );
}