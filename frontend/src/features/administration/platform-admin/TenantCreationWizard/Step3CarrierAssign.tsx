/**
 * Step3CarrierAssign — Multi-select carriers from /platform/carriers.
 * V9 S12.2 — carrier assignment + Add New Carrier shortcut.
 *
 * API note: GET /platform/carriers returns objects with `name` and `slug`
 * fields (matching the public.carriers table), NOT `carrier_name`/`carrier_code`.
 * The interface is aligned to the actual backend response shape.
 */

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { AddCarrierModal } from "../AddCarrierModal";

// ---------------------------------------------------------------------------
// Type — matches actual backend CarrierResponse shape exactly
// GET /platform/carriers → { carrier_id, name, slug, ai_narrative_enabled }
// ---------------------------------------------------------------------------
interface CarrierOption {
  carrier_id: number;
  name: string;          // backend field — NOT carrier_name
  slug: string;          // backend field — NOT carrier_code
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

/**
 * Fetches carriers and normalises the response to a guaranteed array.
 * Guards against the backend wrapping in a paginated envelope in future.
 */
async function fetchCarriers(): Promise<CarrierOption[]> {
  const { data } = await axios.get<CarrierOption[] | { items: CarrierOption[] }>(
    "/platform/carriers"
  );
  if (Array.isArray(data)) return data;
  // Future-proof: handle paginated envelope
  if (data && Array.isArray((data as { items: CarrierOption[] }).items)) {
    return (data as { items: CarrierOption[] }).items;
  }
  return [];
}

export function Step3CarrierAssign({ initial, onNext, onBack }: Props): React.JSX.Element {
  const labels = useLabels();
  const [selected, setSelected] = useState<Set<number>>(
    new Set(initial?.selectedCarrierIds ?? [])
  );
  const [showAddModal, setShowAddModal] = useState(false);

  const { data: carriers = [], isLoading, refetch } = useQuery<CarrierOption[]>({
    queryKey: ["platform-carriers"],
    queryFn: fetchCarriers,
    staleTime: 60 * 1000,
  });

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="wizard-step">
      <h2 className="wizard-step__title">{labels.platform_wizard_step3}</h2>

      {isLoading ? (
        <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
          {labels.loading}
        </p>
      ) : carriers.length === 0 ? (
        <div className="empty-state" style={{ marginBottom: "var(--space-4)" }}>
          <span>No carriers configured yet. Add one below.</span>
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
        + {labels.platform_btn_new_carrier}
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

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.platform_btn_back}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => onNext({ selectedCarrierIds: Array.from(selected) })}
        >
          {labels.platform_btn_next}
        </button>
      </div>
    </div>
  );
}
