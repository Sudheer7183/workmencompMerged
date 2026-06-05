/**
 * CarriersList — SUPER_ADMIN carrier master management table.
 * V9 S12.5 / S11.2 — lists all carriers from /platform/carriers.
 *
 * API note: GET /platform/carriers returns { carrier_id, name, slug,
 * ai_narrative_enabled } matching public.carriers — NOT carrier_name/carrier_code.
 */

import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { AddCarrierModal } from "./AddCarrierModal";

// Matches actual backend CarrierResponse shape
interface CarrierItem {
  carrier_id: number;
  name: string;                  // backend field
  slug: string;                  // backend field (used as code/identifier)
  ai_narrative_enabled: boolean;
}

async function fetchCarriers(): Promise<CarrierItem[]> {
  const { data } = await axios.get<CarrierItem[] | { items: CarrierItem[] }>(
    "/platform/carriers"
  );
  if (Array.isArray(data)) return data;
  if (data && Array.isArray((data as { items: CarrierItem[] }).items)) {
    return (data as { items: CarrierItem[] }).items;
  }
  return [];
}

export function CarriersList(): React.JSX.Element {
  const labels = useLabels();
  const qc = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);

  const { data: carriers = [], isLoading } = useQuery<CarrierItem[]>({
    queryKey: ["platform-carriers"],
    queryFn: fetchCarriers,
    staleTime: 30 * 1000,
  });

  return (
    <div className="carriers-list">
      <div className="carriers-list__header">
        <h1 className="carriers-list__title">{labels.platform_carriers_title}</h1>
        <button
          className="btn btn--primary"
          onClick={() => setShowAddModal(true)}
        >
          {labels.platform_btn_new_carrier}
        </button>
      </div>

      {isLoading ? (
        <p className="carriers-list__loading">{labels.loading}</p>
      ) : carriers.length === 0 ? (
        <div className="empty-state">
          <span>No carriers yet. Add one to get started.</span>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>{labels.platform_col_name}</th>
              <th>Slug / Code</th>
              <th>AI Narrative</th>
            </tr>
          </thead>
          <tbody>
            {carriers.map((c) => (
              <tr key={c.carrier_id} className="data-table__row">
                <td className="data-table__cell">{c.name}</td>
                <td className="data-table__cell">
                  <code>{c.slug}</code>
                </td>
                <td className="data-table__cell">
                  <span className={`badge ${c.ai_narrative_enabled ? "badge--active" : "badge--inactive"}`}>
                    {c.ai_narrative_enabled ? "Enabled" : "Disabled"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showAddModal && (
        <AddCarrierModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => {
            void qc.invalidateQueries({ queryKey: ["platform-carriers"] });
            setShowAddModal(false);
          }}
        />
      )}
    </div>
  );
}
