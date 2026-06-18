/**
 * Step4ReviewActivate — Phase 7A update.
 *
 * Carrier list in review summary now handles the zero-carrier case gracefully,
 * showing an informational message instead of blocking activation.
 */

import React from "react";
import { useLabels } from "@/hooks/useLabels";
import type { Step1Data } from "./Step1TenantDetails"; // fields: tenantName, slug, tenantType
import type { Step2Data } from "./Step2AdminUser";
import type { Step3Data } from "./Step3CarrierAssign";

interface Props {
  step1: Step1Data;
  step2: Step2Data;
  step3: Step3Data;
  carrierNames: Record<number, string>;
  onActivate: () => void;
  onBack: () => void;
  isActivating: boolean;
}

export function Step4ReviewActivate({
  step1,
  step2,
  step3,
  carrierNames,
  onActivate,
  onBack,
  isActivating,
}: Props): React.JSX.Element {
  const label = useLabels("platform_admin");

  return (
    <div className="wizard-step">
      <h2 className="wizard-step__title">
        {label("step4.title", "Review & Activate")}
      </h2>

      <div className="wizard-review">
        <section className="wizard-review__section">
          <h3 className="wizard-review__section-title">
            {label("step4.section.tenant", "Tenant Details")}
          </h3>
          <dl className="wizard-review__dl">
            <dt>{label("field.tenant_name", "Tenant Name")}</dt>
            <dd>{step1.tenantName}</dd>
            <dt>{label("field.subdomain", "Subdomain")}</dt>
            <dd>{step1.slug}</dd>
            <dt>{label("field.tenant_type", "Type")}</dt>
            <dd>{step1.tenantType}</dd>
          </dl>
        </section>

        <section className="wizard-review__section">
          <h3 className="wizard-review__section-title">
            {label("step4.section.admin", "Administrator")}
          </h3>
          <dl className="wizard-review__dl">
            <dt>{label("field.admin_email", "Email")}</dt>
            <dd>{step2.email}</dd>
            <dt>{label("field.admin_first", "Name")}</dt>
            <dd>
              {step2.firstName} {step2.lastName}
            </dd>
          </dl>
        </section>

        <section className="wizard-review__section">
          <h3 className="wizard-review__section-title">
            {label("step4.section.carriers", "Carriers")}
          </h3>
          {step3.selectedCarrierIds.length === 0 ? (
            <p className="wizard-review__no-carriers">
              {label(
                "step4.no_carriers_note",
                "No carriers assigned at this time — carriers can be added from the Tenant Administration panel after activation."
              )}
            </p>
          ) : (
            <ul className="wizard-review__carrier-list">
              {step3.selectedCarrierIds.map((id) => (
                <li key={id} className="wizard-review__carrier-item">
                  {carrierNames[id] ?? `Carrier #${id}`}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="wizard-step__actions">
        <button
          type="button"
          className="btn btn--secondary"
          onClick={onBack}
          disabled={isActivating}
        >
          {label("btn.back", "Back")}
        </button>
        {/* Phase 7A: Activate is always enabled — zero carriers is valid */}
        <button
          type="button"
          className="btn btn--primary"
          onClick={onActivate}
          disabled={isActivating}
        >
          {isActivating
            ? label("btn.activating", "Activating…")
            : label("btn.activate", "Activate")}
        </button>
      </div>
    </div>
  );
}