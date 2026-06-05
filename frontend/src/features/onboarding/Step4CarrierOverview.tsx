/**
 * Onboarding Step 4 — Read-only carrier overview.
 * Reads tenant_carriers; shows each carrier's config status badge.
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
  const labels = useLabels();
  const { data: carriers = [], isLoading } = useQuery<TenantCarrierItem[]>({
    queryKey: ["tenant-carriers-onboarding"],
    queryFn: fetchCarriers,
    staleTime: 60 * 1000,
  });

  return (
    <div className="onboarding-step">
      <h2 className="onboarding-step__title">{labels.onboarding_s4_title}</h2>

      {isLoading ? (
        <p>{labels.loading}</p>
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
                  ? labels.onboarding_carrier_config_status
                  : labels.onboarding_carrier_not_configured}
              </span>
            </li>
          ))}
          {carriers.length === 0 && (
            <li className="carrier-overview__empty">{labels.no_data}</li>
          )}
        </ul>
      )}

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.onboarding_btn_prev}
        </button>
        <button type="button" className="btn btn--primary" onClick={onNext}>
          {labels.onboarding_btn_continue}
        </button>
      </div>
    </div>
  );
}
