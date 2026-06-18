/**
 * AIConfigPage — Standalone TENANT_ADMIN route /admin/ai-config.
 * Phase 7BCD Item 2.5.
 *
 * Carrier-scoped AI LLM configuration screen accessible from the top nav.
 * Wraps AIConfigTab with a carrier selector at the top when the tenant has
 * multiple carriers. Delegates all form logic to AIConfigTab.
 */

import React, { useState, useEffect } from "react";
import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { AIConfigTab } from "./AIConfigTab";

interface CarrierOption {
  carrier_id: number;
  carrier_name: string;
}

async function fetchTenantCarriers(): Promise<CarrierOption[]> {
  try {
    const { data } = await axios.get<CarrierOption[]>("/api/v1/admin/carriers");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export function AIConfigPage(): React.JSX.Element {
  const label = useLabels("ai_config");
  const labelShared = useLabels("shared");
  const { carrierId: contextCarrierId } = useTenantCarrier();

  const { data: carriers = [], isLoading } = useQuery<CarrierOption[]>({
    queryKey: ["tenant-carriers-ai-config"],
    queryFn: fetchTenantCarriers,
    staleTime: 60 * 1000,
  });

  const [selectedCarrierId, setSelectedCarrierId] = useState<number>(contextCarrierId);

  // Sync to context carrierId if the page is loaded fresh
  useEffect(() => {
    if (contextCarrierId && selectedCarrierId !== contextCarrierId) {
      setSelectedCarrierId(contextCarrierId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextCarrierId]);

  const activeCarrierId = selectedCarrierId || contextCarrierId;

  return (
    <div className="ai-config-page">
      {/* Carrier selector — shown when tenant has more than one carrier */}
      {!isLoading && carriers.length > 1 && (
        <div className="ai-config-page__carrier-selector">
          <span className="ai-config-page__carrier-label">
            {label("carrier_selector_label", "Carrier:")}
          </span>
          <select
            className="form-field__select"
            value={activeCarrierId}
            onChange={(e) => setSelectedCarrierId(Number(e.target.value))}
            aria-label={label("carrier_selector_aria", "Select carrier")}
          >
            {carriers.map((c) => (
              <option key={c.carrier_id} value={c.carrier_id}>
                {c.carrier_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {isLoading ? (
        <p className="text-muted">{labelShared("loading", "Loading…")}</p>
      ) : activeCarrierId ? (
        <AIConfigTab carrierId={activeCarrierId} />
      ) : (
        <p className="text-muted">
          {label("no_carriers_notice", "No carriers available. Please configure a carrier first.")}
        </p>
      )}
    </div>
  );
}
