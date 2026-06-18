/**
 * CarrierConfigHub — Phase 4 update.
 *
 * 6-tab carrier configuration hub per V9 S15.2.
 * Phase 4: Tab 1 (Data Sources) and Tab 2 (Field Mapping) are now active.
 * Phase 3: Tab 3 (Calc Engine) remains fully active.
 * Tabs 4, 5, 6 are stubbed with "Coming in Phase N" placeholders.
 *
 * Route: /admin/carriers/:carrierId/config
 *
 * Fix: tab bar was rendering `label[tab.labelKey]` which references an undefined
 * variable `label`. The three label hooks in this file are label_carrier_config,
 * label_shared, and label_reports — none is named `label`.
 * Corrected to `label_carrier_config(tab.labelKey, tab.defaultLabel)`.
 *
 * Secondary fix: removed the `?? "fallback"` pattern from label_shared() calls —
 * useLabels() already returns the fallback string when a key is missing, so the
 * nullish coalescing is redundant and misleading (the hook never returns null).
 */

import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { CalcEngineToggle } from "./CalcEngineToggle";
import { CalcRulesList } from "./CalcRulesList";
import { DataSourcesTab } from "./DataSourcesTab";
import { FieldMappingTab } from "./FieldMappingTab";
import { ReportTemplateTab } from "./ReportTemplateTab";
import { LabelsDisplayTab } from "./LabelsDisplayTab";
import { ThemeTab } from "./theme/ThemeTab";
import { AIConfigTab } from "./AIConfigTab";
import { useAuth } from "@/context/AuthContext";

interface Tab {
  id: number;
  key: string;
  labelKey: string;
  defaultLabel: string;
  phase: number;
}

const TABS: Tab[] = [
  { id: 1, key: "data-sources",    labelKey: "tab_data_sources",    defaultLabel: "Data Sources",     phase: 4 },
  { id: 2, key: "field-mapping",   labelKey: "tab_field_mapping",   defaultLabel: "Field Mapping",    phase: 4 },
  { id: 3, key: "calc-engine",     labelKey: "tab_calc_engine",     defaultLabel: "Calc Engine",      phase: 3 },
  { id: 4, key: "label-display",   labelKey: "tab_labels_display",  defaultLabel: "Labels & Display", phase: 6 },
  { id: 5, key: "report-template", labelKey: "tab_report_template", defaultLabel: "Report Template",  phase: 5 },
  { id: 6, key: "theme",           labelKey: "tab_theme",           defaultLabel: "Theme",            phase: 6 },
  { id: 7, key: "ai-config",       labelKey: "tab_ai_config",       defaultLabel: "AI Configuration", phase: 7 },
];

interface CarrierConfigHubProps {
  carrierId?: number;
  carrierName?: string;
}

function ComingSoonTab({ phase }: { phase: number }): React.JSX.Element {
  return (
    <div className="carrier-config-hub__coming-soon" data-testid="carrier-config-hub__coming-soon">
      <p>Coming in Phase {phase}</p>
    </div>
  );
}

export function CarrierConfigHub({
  carrierId: carrierIdProp,
  carrierName,
}: CarrierConfigHubProps): React.JSX.Element {
  const label_carrier_config = useLabels("carrier_config");
  const label_reports        = useLabels("reports");
  const label_shared         = useLabels("shared");
  const { user } = useAuth();
  const params = useParams<{ carrierId?: string }>();

  const carrierId    = carrierIdProp ?? Number(params.carrierId ?? 0);
  const [activeTab, setActiveTab] = useState(3);
  const isTenantAdmin = user?.role === "TENANT_ADMIN";

  function renderTabContent(): React.JSX.Element {
    switch (activeTab) {
      case 1:
        return <DataSourcesTab carrierId={carrierId} />;

      case 2:
        return <FieldMappingTab carrierId={carrierId} />;

      case 3:
        return (
          <div className="carrier-config-hub__tab-content">
            <section className="carrier-config-hub__section">
              <CalcEngineToggle carrierId={carrierId} readonly={!isTenantAdmin} />
            </section>
            {isTenantAdmin && (
              <section className="carrier-config-hub__section">
                <CalcRulesList carrierId={carrierId} />
              </section>
            )}
            {!isTenantAdmin && (
              <div className="carrier-config-hub__access-note">
                {label_shared(
                  "calc_rules_admin_only",
                  "Calculation rule editing requires Tenant Administrator access."
                )}
              </div>
            )}
          </div>
        );

      case 4:
        return isTenantAdmin
          ? <LabelsDisplayTab carrierId={carrierId} />
          : (
            <div className="carrier-config-hub__coming-soon">
              <p>Labels &amp; Display configuration requires Tenant Administrator access.</p>
            </div>
          );

      case 5:
        return isTenantAdmin
          ? <ReportTemplateTab carrierId={carrierId} />
          : (
            <div className="carrier-config-hub__coming-soon">
              <p>
                {label_reports(
                  "template.admin_only",
                  "Report template configuration is available to Tenant Admins only."
                )}
              </p>
            </div>
          );

      case 6:
        return isTenantAdmin
          ? <ThemeTab carrierId={carrierId} />
          : (
            <div className="carrier-config-hub__coming-soon">
              <p>Theme configuration requires Tenant Administrator access.</p>
            </div>
          );

      case 7:
        return isTenantAdmin
          ? <AIConfigTab carrierId={carrierId} />
          : (
            <div className="carrier-config-hub__coming-soon">
              <p>AI configuration requires Tenant Administrator access.</p>
            </div>
          );

      default:
        return <ComingSoonTab phase={activeTab} />;
    }
  }

  return (
    <div className="carrier-config-hub" data-testid="carrier-config-hub">
      {/* Header */}
      <div className="carrier-config-hub__header">
        <h1 className="carrier-config-hub__title">
          {label_carrier_config("title", "Carrier Configuration")}
          {carrierName && (
            <span className="carrier-config-hub__carrier-name"> — {carrierName}</span>
          )}
        </h1>
      </div>

      {/* Tab bar */}
      <nav
        className="carrier-config-hub__tabs"
        aria-label="Carrier configuration tabs"
        data-testid="carrier-config-hub__tabs"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={[
              "carrier-config-hub__tab",
              activeTab === tab.id ? "carrier-config-hub__tab--active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={() => setActiveTab(tab.id)}
            aria-selected={activeTab === tab.id}
            aria-controls={`tab-panel-${tab.key}`}
            data-testid={
              tab.key === "report-template"
                ? "tab-report-template"
                : `carrier-config-hub__tab-${tab.id}`
            }
          >
            {/* FIX: was label[tab.labelKey] — `label` is not defined in this component.
                Corrected to label_carrier_config(tab.labelKey, tab.defaultLabel). */}
            {label_carrier_config(tab.labelKey, tab.defaultLabel)}
          </button>
        ))}
      </nav>

      {/* Tab content */}
      <div
        id={`tab-panel-${TABS.find((t) => t.id === activeTab)?.key ?? ""}`}
        className="carrier-config-hub__panel"
        role="tabpanel"
        data-testid="carrier-config-hub__panel"
      >
        {renderTabContent()}
      </div>
    </div>
  );
}