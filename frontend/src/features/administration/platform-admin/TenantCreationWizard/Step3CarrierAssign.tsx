/**
 * Step3CarrierAssign — Phase 7A: Carrier assignment is now OPTIONAL.
 *
 * V9 S12.2 (Phase 7A update): Removing the "minimum 1 carrier" gate.
 * Tenants may be activated with zero carriers. TENANT_ADMIN adds carriers
 * post-provisioning from their Administration panel.
 *
 * The step still supports selecting carriers at wizard time for convenience
 * (e.g. operators who already know which carrier to assign).
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { AddCarrierModal } from "../AddCarrierModal";

interface CarrierOption {
  carrier_id: number;
  name: string;
  slug: string;
  ai_narrative_enabled: boolean;
}

export interface Step3Data {
  selectedCarrierIds: number[];
}

interface Props {
  initial: Step3Data | null;
  onNext: (data: Step3Data) => void;
  onBack: () => void;
}

async function fetchCarriers(): Promise<CarrierOption[]> {
  const { data } = await axios.get<CarrierOption[] | { items: CarrierOption[] }>(
    "/platform/carriers"
  );
  if (Array.isArray(data)) return data;
  if (data && Array.isArray((data as { items: CarrierOption[] }).items)) {
    return (data as { items: CarrierOption[] }).items;
  }
  return [];
}

export function Step3CarrierAssign({ initial, onNext, onBack }: Props): React.JSX.Element {
  const label_platform_admin = useLabels("platform_admin");
  const label_shared = useLabels("shared");
  const [selected, setSelected] = useState<Set<number>>(
    new Set(initial?.selectedCarrierIds ?? [])
  );
  const [showAddModal, setShowAddModal] = useState(false);

  const { data: carriers = [], isLoading, refetch } = useQuery<CarrierOption[]>({
    queryKey: ["platform-carriers"],
    queryFn: fetchCarriers,
    staleTime: 60 * 1000,
  });

  const toggle = (id: number): void => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="wizard-step">
      <h2 className="wizard-step__title">
        {label_platform_admin("step3.title", "Carrier Assignment (Optional)")}
      </h2>

      <p className="wizard-step__hint">
        {label_platform_admin(
          "step3.optional_hint",
          "Carrier assignment is optional at this stage. You can add carriers after activation from the Tenant Administration panel."
        )}
      </p>

      {isLoading ? (
        <p className="wizard-step__loading">
          {label_shared("loading", "Loading…")}
        </p>
      ) : carriers.length === 0 ? (
        <div className="empty-state wizard-step__empty">
          <span>{label_platform_admin("step3.no_carriers", "No carriers configured yet. Add one below.")}</span>
        </div>
      ) : (
        <div className="carrier-assign__list" role="group" aria-label="Available carriers">
          {carriers.map((c) => (
            <label key={c.carrier_id} className="carrier-assign__item">
              <input
                type="checkbox"
                checked={selected.has(c.carrier_id)}
                onChange={() => toggle(c.carrier_id)}
                className="carrier-assign__checkbox"
              />
              <span className="carrier-assign__name">{c.name}</span>
              <span className="carrier-assign__code">{c.slug}</span>
            </label>
          ))}
        </div>
      )}

      <button
        type="button"
        className="btn btn--link"
        onClick={() => setShowAddModal(true)}
      >
        + {label_platform_admin("btn.new_carrier", "Add Carrier")}
      </button>

      {showAddModal && (
        <AddCarrierModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => {
            void refetch();
            setShowAddModal(false);
          }}
        />
      )}

      {selected.size === 0 && (
        <div className="wizard-step__info-banner">
          <span className="wizard-step__info-icon">ℹ</span>
          <span>
            {label_platform_admin(
              "step3.zero_carriers_notice",
              "No carriers selected — the tenant will be activated without carriers. Carriers can be added later from the Tenant Administration panel."
            )}
          </span>
        </div>
      )}

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_platform_admin("btn.back", "Back")}
        </button>
        {/* Phase 7A: Next is always enabled regardless of carrier selection */}
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => onNext({ selectedCarrierIds: Array.from(selected) })}
        >
          {label_platform_admin("btn.next", "Next")}
        </button>
      </div>
    </div>
  );
}
