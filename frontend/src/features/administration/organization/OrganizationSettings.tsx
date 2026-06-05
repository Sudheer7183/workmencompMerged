/**
 * OrganizationSettings — Tabbed container for TENANT_ADMIN settings.
 * Tabs: Profile | Contacts | Branding
 * V9 S13.2
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import { ProfileTab } from "./ProfileTab";
import { ContactsTab } from "./ContactsTab";
import { BrandingTab } from "./BrandingTab";

type TabKey = "profile" | "contacts" | "branding";

export function OrganizationSettings(): React.JSX.Element {
  const labels = useLabels();
  const [activeTab, setActiveTab] = useState<TabKey>("profile");

  const tabs: { key: TabKey; label: string }[] = [
    { key: "profile", label: labels.org_tab_profile },
    { key: "contacts", label: labels.org_tab_contacts },
    { key: "branding", label: labels.org_tab_branding },
  ];

  return (
    <div className="org-settings">
      <h1 className="org-settings__title">{labels.org_settings_title}</h1>

      <nav className="org-settings__tabs" role="tablist">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            role="tab"
            aria-selected={activeTab === key}
            className={`org-settings__tab ${activeTab === key ? "org-settings__tab--active" : ""}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="org-settings__panel" role="tabpanel">
        {activeTab === "profile" && <ProfileTab />}
        {activeTab === "contacts" && <ContactsTab />}
        {activeTab === "branding" && <BrandingTab />}
      </div>
    </div>
  );
}
