/**
 * CarriersList — SUPER_ADMIN carrier master management table.
 * Phase 7BCD: Added Edit action per row (opens carrier-create-panel in edit mode).
 */

import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { AddCarrierModal, type CarrierFormData } from "./AddCarrierModal";

interface CarrierItem {
  carrier_id: number;
  name: string;
  slug: string;
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
  const label = useLabels("platform_admin");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<CarrierFormData | null>(null);

  const { data: carriers = [], isLoading } = useQuery<CarrierItem[]>({
    queryKey: ["platform-carriers"],
    queryFn: fetchCarriers,
    staleTime: 30 * 1000,
  });

  const handlePanelClose = (): void => {
    setShowCreate(false);
    setEditTarget(null);
  };

  const handlePanelCreated = (): void => {
    void qc.invalidateQueries({ queryKey: ["platform-carriers"] });
    handlePanelClose();
  };

  return (
    <div className="carriers-list">
      <div className="carriers-list__header">
        <h1 className="carriers-list__title">{label("carriers.title", "Carriers")}</h1>
        <button
          className="btn btn--primary"
          type="button"
          onClick={() => setShowCreate(true)}
        >
          {label("btn.new_carrier", "Add Carrier")}
        </button>
      </div>

      {isLoading ? (
        <p className="carriers-list__loading">{labelShared("loading", "Loading…")}</p>
      ) : carriers.length === 0 ? (
        <div className="empty-state">
          <span>{label("carriers.empty", "No carriers yet. Add one to get started.")}</span>
        </div>
      ) : (
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>{label("col.name", "Name")}</th>
                <th>{label("carrier.slug_label", "Slug")}</th>
                <th>{label("carrier.ai_narrative_label", "AI Narrative")}</th>
                <th>{label("col.actions", "Actions")}</th>
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
                    <span
                      className={`badge ${
                        c.ai_narrative_enabled ? "badge-green" : "badge-muted"
                      }`}
                    >
                      {c.ai_narrative_enabled
                        ? label("carrier.ai_enabled", "Enabled")
                        : label("carrier.ai_disabled", "Disabled")}
                    </span>
                  </td>
                  <td className="data-table__cell">
                    <button
                      type="button"
                      className="btn btn--sm btn--secondary"
                      onClick={() =>
                        setEditTarget({
                          carrier_id: c.carrier_id,
                          name: c.name,
                          slug: c.slug,
                          ai_narrative_enabled: c.ai_narrative_enabled,
                        })
                      }
                    >
                      {label("col.edit", "Edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <AddCarrierModal onClose={handlePanelClose} onCreated={handlePanelCreated} />
      )}

      {editTarget && (
        <AddCarrierModal
          editCarrier={editTarget}
          onClose={handlePanelClose}
          onCreated={handlePanelCreated}
        />
      )}
    </div>
  );
}
