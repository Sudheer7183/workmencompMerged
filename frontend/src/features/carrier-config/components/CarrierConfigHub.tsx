/**
 * CarrierConfigHub — Phase 3.
 *
 * 6-tab carrier configuration hub per V9 S15.2.
 * Phase 3: Tab 3 (Calc Engine) is fully active.
 * Tabs 1, 2, 4, 5, 6 are stubbed with "Coming in Phase N" placeholders.
 *
 * Route: /admin/carriers/:carrierId/config
 *
 * carrierId may be passed as a prop (when embedded) or read from the
 * :carrierId route param (when used directly in the router).
 */

import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useLabels } from "@/hooks/useLabels";
import { CalcEngineToggle } from "./CalcEngineToggle";
import { CalcRulesList } from "./CalcRulesList";
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
  { id: 4, key: "labels-display",  labelKey: "tab_labels_display",  defaultLabel: "Labels & Display", phase: 6 },
  { id: 5, key: "report-template", labelKey: "tab_report_template", defaultLabel: "Report Template",  phase: 5 },
  { id: 6, key: "theme",           labelKey: "tab_theme",           defaultLabel: "Theme",            phase: 6 },
];

interface CarrierConfigHubProps {
  /** When provided, takes precedence over the :carrierId route param. */
  carrierId?: number;
  carrierName?: string;
}

export function CarrierConfigHub({
  carrierId: carrierIdProp,
  carrierName,
}: CarrierConfigHubProps): React.JSX.Element {
  const labels = useLabels();
  const { user } = useAuth();
  const params = useParams<{ carrierId?: string }>();

  // Resolve carrierId: explicit prop wins, then route param, then 0 as a safe default.
  const carrierId = carrierIdProp ?? Number(params.carrierId ?? 0);

  const [activeTab, setActiveTab] = useState(3); // Tab 3 active by default per V9 S15.2

  const isTenantAdmin = user?.role === "TENANT_ADMIN";

  function renderTabContent(): React.JSX.Element {
    switch (activeTab) {
      case 3:
        return (
          <div className="carrier-config-hub__tab-content">
            {/* Calc engine ON/OFF toggle */}
            <section className="carrier-config-hub__section">
              <CalcEngineToggle carrierId={carrierId} readonly={!isTenantAdmin} />
            </section>

            {/* Calc rules editor — TENANT_ADMIN only */}
            {isTenantAdmin && (
              <section className="carrier-config-hub__section">
                <CalcRulesList carrierId={carrierId} />
              </section>
            )}

            {!isTenantAdmin && (
              <div className="carrier-config-hub__access-note">
                {labels.calc_rules_admin_only ??
                  "Calculation rule editing requires Tenant Administrator access."}
              </div>
            )}
          </div>
        );

      default: {
        const tab = TABS.find((t) => t.id === activeTab);
        const phase = tab?.phase ?? 4;
        const tabLabel =
          tab
            ? ((labels[tab.labelKey as keyof typeof labels] as string) ?? tab.defaultLabel)
            : "Tab";
        return (
          <div className="carrier-config-hub__coming-soon">
            <div className="carrier-config-hub__coming-soon-icon">🔧</div>
            <h3 className="carrier-config-hub__coming-soon-title">{tabLabel}</h3>
            <p className="carrier-config-hub__coming-soon-text">
              {labels.tab_coming_in_phase
                ? (labels.tab_coming_in_phase as string).replace("{phase}", String(phase))
                : `This feature is coming in Phase ${phase}.`}
            </p>
          </div>
        );
      }
    }
  }

  return (
    <div className="carrier-config-hub">
      {/* Header */}
      <div className="carrier-config-hub__header">
        <div>
          <h2 className="carrier-config-hub__title">
            {labels.carrier_config_hub_title ?? "Carrier Configuration"}
          </h2>
          {carrierName && (
            <p className="carrier-config-hub__carrier-name">{carrierName}</p>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="carrier-config-hub__tabs" role="tablist">
        {TABS.map((tab) => {
          const tabLabel =
            (labels[tab.labelKey as keyof typeof labels] as string) ?? tab.defaultLabel;
          const isActive = activeTab === tab.id;
          const isAvailable = tab.phase === 3; // Only the Phase 3 tab is interactive now

          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-disabled={!isAvailable}
              className={[
                "carrier-config-hub__tab",
                isActive ? "carrier-config-hub__tab--active" : "",
                !isAvailable ? "carrier-config-hub__tab--disabled" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => setActiveTab(tab.id)}
              title={
                !isAvailable
                  ? (labels.tab_coming_in_phase
                      ? (labels.tab_coming_in_phase as string).replace("{phase}", String(tab.phase))
                      : `Coming in Phase ${tab.phase}`)
                  : tabLabel
              }
            >
              {tabLabel}
              {!isAvailable && (
                <span className="carrier-config-hub__tab-phase-badge">
                  {labels.phase_badge_prefix ?? "P"}
                  {tab.phase}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content area */}
      <div
        className="carrier-config-hub__content"
        role="tabpanel"
        aria-label={TABS.find((t) => t.id === activeTab)?.defaultLabel}
      >
        {renderTabContent()}
      </div>
    </div>
  );
}