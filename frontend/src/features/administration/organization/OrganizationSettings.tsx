/**
 * OrganizationSettings — Phase 7BCD redesign.
 *
 * Replaces the original Phase 2 layout with the Phase 7B visual treatment:
 *  - Page-level header with title + subtitle
 *  - Tab bar using org-settings__tab-bar / org-settings__tab-btn BEM blocks
 *    (underline-style, border-bottom accent on active)
 *  - Tab panels using org-settings__tab-panel as the content region
 *  - Each tab's content uses org-settings__section cards with header/body/footer
 *    regions so every tab is visually consistent
 *
 * Tab logic and API calls inside each child component are unchanged.
 * V9 S13.2 — Carriers tab visible to TENANT_ADMIN only.
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";
import { ProfileTab } from "./ProfileTab";
import { ContactsTab } from "./ContactsTab";
import { BrandingTab } from "./BrandingTab";
import { CarrierManagementPanel } from "./CarrierManagementPanel";

type TabKey = "profile" | "contacts" | "branding" | "carriers";

interface TabDef {
  key: TabKey;
  labelKey: string;
  defaultLabel: string;
  adminOnly?: boolean;
}

const TAB_DEFS: TabDef[] = [
  { key: "profile",  labelKey: "tab.profile",  defaultLabel: "Profile"  },
  { key: "contacts", labelKey: "tab.contacts", defaultLabel: "Contacts" },
  { key: "branding", labelKey: "tab.branding", defaultLabel: "Branding" },
  { key: "carriers", labelKey: "tab.carriers", defaultLabel: "Carriers", adminOnly: true },
];

export function OrganizationSettings(): React.JSX.Element {
  const label = useLabels("org_settings");
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabKey>("profile");

  const isTenantAdmin = user?.role === "TENANT_ADMIN";

  const visibleTabs = TAB_DEFS.filter((t) => !t.adminOnly || isTenantAdmin);

  return (
    <div className="org-settings">
      {/* Page header */}
      <div className="org-settings__page-header">
        <h1 className="org-settings__page-title">
          {label("title", "Organisation Settings")}
        </h1>
        <p className="org-settings__page-subtitle">
          {label(
            "page_subtitle",
            "Manage your organisation profile, contacts, branding, and carrier assignments."
          )}
        </p>
      </div>

      {/* Tab bar */}
      <nav
        className="org-settings__tab-bar"
        role="tablist"
        aria-label={label("title", "Organisation Settings")}
      >
        {visibleTabs.map(({ key, labelKey, defaultLabel }) => (
          <button
            key={key}
            role="tab"
            type="button"
            id={`org-tab-${key}`}
            aria-selected={activeTab === key}
            aria-controls={`org-panel-${key}`}
            className={[
              "org-settings__tab-btn",
              activeTab === key ? "org-settings__tab-btn--active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={() => setActiveTab(key)}
          >
            {label(labelKey, defaultLabel)}
          </button>
        ))}
      </nav>

      {/* Tab panels */}
      <div
        className="org-settings__tab-panel"
        role="tabpanel"
        id={`org-panel-${activeTab}`}
        aria-labelledby={`org-tab-${activeTab}`}
      >
        {activeTab === "profile"  && <ProfileTab />}
        {activeTab === "contacts" && <ContactsTab />}
        {activeTab === "branding" && <BrandingTab />}
        {activeTab === "carriers" && isTenantAdmin && <CarrierManagementPanel />}
      </div>
    </div>
  );
}
