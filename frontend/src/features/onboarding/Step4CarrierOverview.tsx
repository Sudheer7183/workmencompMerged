/**
 * Onboarding Step 4 — Read-only carrier overview.
 * Reads tenant_carriers; shows each carrier's config status badge.
 *
 * Fix: replaced label_shared("onboarding_s", "onboarding_s")4_title
 * with label_onboarding("step4.title", "Carrier Configuration") per V9 S23.3.
 */

import React from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

interface TenantCarrierItem {
  carrier_id: number;
  carrier_name: string;
  carrier_code: string;
  is_configured: boolean;
}

async function fetchCarriers(): Promise<TenantCarrierItem[]> {
  const { data } = await axios.get<TenantCarrierItem[]>("/api/v1/tenant/carriers");
  return data;
}

interface Props {
  onNext: () => void;
  onBack: () => void;
}

export function Step4CarrierOverview({ onNext, onBack }: Props): React.JSX.Element {
  const label_onboarding = useLabels("onboarding");
  const label_shared = useLabels("shared");
  const { data: carriers = [], isLoading } = useQuery<TenantCarrierItem[]>({
    queryKey: ["tenant-carriers-onboarding"],
    queryFn: fetchCarriers,
    staleTime: 60 * 1000,
  });

  return (
    <div className="onboarding-step">
      {/* FIX: was label_shared("onboarding_s", "onboarding_s")4_title */}
      <h2 className="onboarding-step__title">
        {label_onboarding("step4.title", "Carrier Configuration")}
      </h2>

      {isLoading ? (
        <p>{label_shared("loading", "Loading…")}</p>
      ) : (
        <ul className="carrier-overview__list">
          {carriers.map((c) => (
            <li key={c.carrier_id} className="carrier-overview__item">
              <span className="carrier-overview__name">{c.carrier_name}</span>
              <span className="carrier-overview__code">{c.carrier_code}</span>
              <span
                className={`badge ${c.is_configured ? "badge--active" : "badge--draft"}`}
              >
                {c.is_configured
                  ? label_onboarding("carrier.configured", "Configured")
                  : label_onboarding("carrier.not_configured", "Not configured")}
              </span>
            </li>
          ))}
          {carriers.length === 0 && (
            <li className="carrier-overview__empty">
              {label_shared("no_data", "No data available.")}
            </li>
          )}
        </ul>
      )}

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_onboarding("btn.prev", "Previous")}
        </button>
        <button type="button" className="btn btn--primary" onClick={onNext}>
          {label_onboarding("btn.continue", "Continue")}
        </button>
      </div>
    </div>
  );
}