// /**
//  * CarrierManagementPanel — Phase 7A
//  *
//  * TENANT_ADMIN self-service carrier management panel.
//  * Mounted as the "Carriers" tab in OrganizationSettings.
//  *
//  * Two sections:
//  *   1. Assigned Carriers — lists active carriers with a Remove button each.
//  *   2. Add a Carrier — search/select from available platform carriers,
//  *      calls POST /api/v1/admin/carriers on confirm.
//  *
//  * Routes: /admin/carriers (also embedded as a tab in OrganizationSettings)
//  * Access: TENANT_ADMIN only
//  */

// import React, { useState } from "react";
// import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
// import axios from "axios";
// import { useLabels } from "@/hooks/useLabels";

// // ---------------------------------------------------------------------------
// // Types
// // ---------------------------------------------------------------------------

// interface AssignedCarrier {
//   carrier_id: number;
//   carrier_name: string;
//   carrier_slug: string;
//   carrier_code: string;
//   is_active: boolean;
// }

// interface AvailableCarrier {
//   carrier_id: number;
//   carrier_name: string;
//   slug: string;
// }

// // ---------------------------------------------------------------------------
// // API functions
// // ---------------------------------------------------------------------------

// async function fetchAssignedCarriers(): Promise<AssignedCarrier[]> {
//   const { data } = await axios.get<AssignedCarrier[]>("/api/v1/tenant/carriers");
//   return data;
// }

// async function fetchAvailableCarriers(): Promise<AvailableCarrier[]> {
//   const { data } = await axios.get<AvailableCarrier[]>("/api/v1/tenant/carriers/available");
//   return data;
// }

// async function addCarrier(carrierId: number): Promise<void> {
//   await axios.post("/api/v1/tenant/carriers", { carrier_id: carrierId });
// }

// async function removeCarrier(carrierId: number): Promise<void> {
//   await axios.delete(`/api/v1/tenant/carriers/${carrierId}`);
// }

// // ---------------------------------------------------------------------------
// // Component
// // ---------------------------------------------------------------------------

// export function CarrierManagementPanel(): React.JSX.Element {
//   const label = useLabels("org_settings");
//   const label_shared = useLabels("shared");
//   const qc = useQueryClient();
//   const [selectedAvailableId, setSelectedAvailableId] = useState<number | null>(null);
//   const [addError, setAddError] = useState<string | null>(null);
//   const [removeConfirmId, setRemoveConfirmId] = useState<number | null>(null);

//   const { data: assigned = [], isLoading: loadingAssigned } = useQuery<AssignedCarrier[]>({
//     queryKey: ["tenant-carriers-assigned"],
//     queryFn: fetchAssignedCarriers,
//     staleTime: 30 * 1000,
//   });

//   const { data: available = [], isLoading: loadingAvailable } = useQuery<AvailableCarrier[]>({
//     queryKey: ["tenant-carriers-available"],
//     queryFn: fetchAvailableCarriers,
//     staleTime: 30 * 1000,
//   });

//   const addMutation = useMutation({
//     mutationFn: (carrierId: number) => addCarrier(carrierId),
//     onSuccess: () => {
//       setSelectedAvailableId(null);
//       setAddError(null);
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers-assigned"] });
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers-available"] });
//       // Invalidate the global carrier context so new carrier appears in hub
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers"] });
//     },
//     onError: (err: unknown) => {
//       const message =
//         axios.isAxiosError(err)
//           ? (err.response?.data?.detail ?? label_shared("error_generic", "Something went wrong."))
//           : label_shared("error_generic", "Something went wrong.");
//       setAddError(String(message));
//     },
//   });

//   const removeMutation = useMutation({
//     mutationFn: (carrierId: number) => removeCarrier(carrierId),
//     onSuccess: () => {
//       setRemoveConfirmId(null);
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers-assigned"] });
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers-available"] });
//       void qc.invalidateQueries({ queryKey: ["tenant-carriers"] });
//     },
//   });

//   return (
//     <div className="carrier-mgmt">
//       {/* ── Section 1: Assigned Carriers ───────────────────────────────── */}
//       <section className="carrier-mgmt__section">
//         <h2 className="carrier-mgmt__section-title">
//           {label("carriers.assigned_title", "Assigned Carriers")}
//         </h2>

//         {loadingAssigned ? (
//           <p className="carrier-mgmt__loading">{label_shared("loading", "Loading…")}</p>
//         ) : assigned.length === 0 ? (
//           <div className="carrier-mgmt__empty">
//             <p>{label("carriers.none_assigned", "No carriers assigned yet. Use the section below to add your first carrier.")}</p>
//           </div>
//         ) : (
//           <table className="carrier-mgmt__table">
//             <thead>
//               <tr>
//                 <th>{label("carriers.col.name", "Carrier Name")}</th>
//                 <th>{label("carriers.col.slug", "Identifier")}</th>
//                 <th>{label("carriers.col.actions", "Actions")}</th>
//               </tr>
//             </thead>
//             <tbody>
//               {assigned.map((c) => (
//                 <tr key={c.carrier_id} className="carrier-mgmt__row">
//                   <td className="carrier-mgmt__cell carrier-mgmt__cell--name">
//                     {c.carrier_name}
//                   </td>
//                   <td className="carrier-mgmt__cell carrier-mgmt__cell--slug">
//                     <code>{c.carrier_slug}</code>
//                   </td>
//                   <td className="carrier-mgmt__cell carrier-mgmt__cell--actions">
//                     {removeConfirmId === c.carrier_id ? (
//                       <span className="carrier-mgmt__confirm">
//                         <span className="carrier-mgmt__confirm-text">
//                           {label("carriers.confirm_remove", "Remove this carrier?")}
//                         </span>
//                         <button
//                           className="btn btn--danger btn--sm"
//                           onClick={() => removeMutation.mutate(c.carrier_id)}
//                           disabled={removeMutation.isPending}
//                         >
//                           {label("carriers.btn.confirm", "Confirm")}
//                         </button>
//                         <button
//                           className="btn btn--secondary btn--sm"
//                           onClick={() => setRemoveConfirmId(null)}
//                         >
//                           {label("carriers.btn.cancel", "Cancel")}
//                         </button>
//                       </span>
//                     ) : (
//                       <button
//                         className="btn btn--secondary btn--sm"
//                         onClick={() => setRemoveConfirmId(c.carrier_id)}
//                       >
//                         {label("carriers.btn.remove", "Remove")}
//                       </button>
//                     )}
//                   </td>
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         )}
//       </section>

//       {/* ── Section 2: Add a Carrier ────────────────────────────────────── */}
//       <section className="carrier-mgmt__section">
//         <h2 className="carrier-mgmt__section-title">
//           {label("carriers.add_title", "Add a Carrier")}
//         </h2>

//         {loadingAvailable ? (
//           <p className="carrier-mgmt__loading">{label_shared("loading", "Loading…")}</p>
//         ) : available.length === 0 ? (
//           <p className="carrier-mgmt__all-assigned">
//             {label("carriers.all_assigned", "All available platform carriers are already assigned to your organisation.")}
//           </p>
//         ) : (
//           <div className="carrier-mgmt__add-form">
//             <label className="carrier-mgmt__add-label" htmlFor="carrier-select">
//               {label("carriers.select_label", "Select carrier to add")}
//             </label>
//             <div className="carrier-mgmt__add-row">
//               <select
//                 id="carrier-select"
//                 className="carrier-mgmt__select"
//                 value={selectedAvailableId ?? ""}
//                 onChange={(e) => {
//                   setSelectedAvailableId(e.target.value ? Number(e.target.value) : null);
//                   setAddError(null);
//                 }}
//               >
//                 <option value="">
//                   {label("carriers.select_placeholder", "— Select a carrier —")}
//                 </option>
//                 {available.map((c) => (
//                   <option key={c.carrier_id} value={c.carrier_id}>
//                     {c.carrier_name}
//                   </option>
//                 ))}
//               </select>
//               <button
//                 className="btn btn--primary"
//                 onClick={() => {
//                   if (selectedAvailableId !== null) {
//                     addMutation.mutate(selectedAvailableId);
//                   }
//                 }}
//                 disabled={selectedAvailableId === null || addMutation.isPending}
//               >
//                 {addMutation.isPending
//                   ? label("carriers.btn.adding", "Adding…")
//                   : label("carriers.btn.add", "Add Carrier")}
//               </button>
//             </div>
//             {addError && (
//               <p className="carrier-mgmt__error" role="alert">
//                 {addError}
//               </p>
//             )}
//             <p className="carrier-mgmt__add-hint">
//               {label(
//                 "carriers.add_hint",
//                 "Adding a carrier seeds default calculation rules and configuration. Rules can be customised from the Carrier Configuration Hub."
//               )}
//             </p>
//           </div>
//         )}
//       </section>
//     </div>
//   );
// }


/**
 * CarrierManagementPanel — Phase 7A (updated with Create Carrier)
 *
 * TENANT_ADMIN self-service carrier management panel.
 * Three sections:
 *   1. Assigned Carriers — table with Remove per row
 *   2. Add a Carrier    — assign an existing platform carrier to this tenant
 *   3. Create a Carrier — create a brand-new carrier and assign it immediately
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AssignedCarrier {
  carrier_id: number;
  carrier_name: string;
  carrier_slug: string;
  is_active: boolean;
}

interface AvailableCarrier {
  carrier_id: number;
  carrier_name: string;
  slug: string;
}

// ── API ───────────────────────────────────────────────────────────────────────

const fetchAssigned  = () =>
  axios.get<AssignedCarrier[]>("/api/v1/tenant/carriers").then((r) => r.data);

const fetchAvailable = () =>
  axios.get<AvailableCarrier[]>("/api/v1/tenant/carriers/available").then((r) => r.data);

const assignCarrier  = (carrierId: number) =>
  axios.post("/api/v1/tenant/carriers", { carrier_id: carrierId });

const removeCarrier  = (carrierId: number) =>
  axios.delete(`/api/v1/tenant/carriers/${carrierId}`);

const createCarrier  = (body: { carrier_name: string; slug: string }) =>
  axios.post("/api/v1/tenant/carriers/create", body).then((r) => r.data);

// ── Slug helper ───────────────────────────────────────────────────────────────

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

// ── Component ─────────────────────────────────────────────────────────────────

export function CarrierManagementPanel(): React.JSX.Element {
  const label        = useLabels("org_settings");
  const label_shared = useLabels("shared");
  const qc           = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────────
  const [selectedAvailableId, setSelectedAvailableId] = useState<number | null>(null);
  const [addError,            setAddError]            = useState<string | null>(null);
  const [removeConfirmId,     setRemoveConfirmId]     = useState<number | null>(null);

  // Create-carrier form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newCarrierName, setNewCarrierName] = useState("");
  const [newCarrierSlug, setNewCarrierSlug] = useState("");
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [createError,     setCreateError]     = useState<string | null>(null);

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: assigned  = [], isLoading: loadingAssigned  } =
    useQuery<AssignedCarrier[]>({
      queryKey: ["tenant-carriers-assigned"],
      queryFn:  fetchAssigned,
      staleTime: 30_000,
    });

  const { data: available = [], isLoading: loadingAvailable } =
    useQuery<AvailableCarrier[]>({
      queryKey: ["tenant-carriers-available"],
      queryFn:  fetchAvailable,
      staleTime: 30_000,
    });

  // ── Mutations ──────────────────────────────────────────────────────────────
  const invalidateAll = () => {
    void qc.invalidateQueries({ queryKey: ["tenant-carriers-assigned"] });
    void qc.invalidateQueries({ queryKey: ["tenant-carriers-available"] });
    void qc.invalidateQueries({ queryKey: ["tenant-carriers"] });
  };

  const addMutation = useMutation({
    mutationFn: (id: number) => assignCarrier(id),
    onSuccess: () => { setSelectedAvailableId(null); setAddError(null); invalidateAll(); },
    onError: (err: unknown) => {
      setAddError(String(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? label_shared("error_generic", "Something went wrong."))
          : label_shared("error_generic", "Something went wrong.")
      ));
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => removeCarrier(id),
    onSuccess: () => { setRemoveConfirmId(null); invalidateAll(); },
  });

  const createMutation = useMutation({
    mutationFn: (body: { carrier_name: string; slug: string }) => createCarrier(body),
    onSuccess: () => {
      setShowCreateForm(false);
      setNewCarrierName("");
      setNewCarrierSlug("");
      setSlugManuallyEdited(false);
      setCreateError(null);
      invalidateAll();
    },
    onError: (err: unknown) => {
      setCreateError(String(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? label_shared("error_generic", "Something went wrong."))
          : label_shared("error_generic", "Something went wrong.")
      ));
    },
  });

  function handleNameChange(name: string): void {
    setNewCarrierName(name);
    if (!slugManuallyEdited) {
      setNewCarrierSlug(toSlug(name));
    }
  }

  function handleCreateSubmit(): void {
    const name = newCarrierName.trim();
    const slug = newCarrierSlug.trim();
    if (!name || !slug) return;
    setCreateError(null);
    createMutation.mutate({ carrier_name: name, slug });
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="carrier-mgmt">

      {/* ── Section 1: Assigned Carriers ───────────────────────────────── */}
      <section className="carrier-mgmt__section">
        <h2 className="carrier-mgmt__section-title">
          {label("carriers.assigned_title", "Assigned Carriers")}
        </h2>

        {loadingAssigned ? (
          <p className="carrier-mgmt__loading">{label_shared("loading", "Loading…")}</p>
        ) : assigned.length === 0 ? (
          <div className="carrier-mgmt__empty">
            <p>{label("carriers.none_assigned", "No carriers assigned yet. Use the section below to add your first carrier.")}</p>
          </div>
        ) : (
          <table className="carrier-mgmt__table">
            <thead>
              <tr>
                <th>{label("carriers.col.name",    "Carrier Name")}</th>
                <th>{label("carriers.col.slug",    "Identifier")}</th>
                <th>{label("carriers.col.actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {assigned.map((c) => (
                <tr key={c.carrier_id} className="carrier-mgmt__row">
                  <td className="carrier-mgmt__cell carrier-mgmt__cell--name">{c.carrier_name}</td>
                  <td className="carrier-mgmt__cell carrier-mgmt__cell--slug">
                    <code>{c.carrier_slug}</code>
                  </td>
                  <td className="carrier-mgmt__cell carrier-mgmt__cell--actions">
                    {removeConfirmId === c.carrier_id ? (
                      <span className="carrier-mgmt__confirm">
                        <span className="carrier-mgmt__confirm-text">
                          {label("carriers.confirm_remove", "Remove this carrier?")}
                        </span>
                        <button
                          className="btn btn--danger btn--sm"
                          onClick={() => removeMutation.mutate(c.carrier_id)}
                          disabled={removeMutation.isPending}
                        >
                          {label("carriers.btn.confirm", "Confirm")}
                        </button>
                        <button
                          className="btn btn--secondary btn--sm"
                          onClick={() => setRemoveConfirmId(null)}
                        >
                          {label("carriers.btn.cancel", "Cancel")}
                        </button>
                      </span>
                    ) : (
                      <button
                        className="btn btn--secondary btn--sm"
                        onClick={() => setRemoveConfirmId(c.carrier_id)}
                      >
                        {label("carriers.btn.remove", "Remove")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ── Section 2: Add an Existing Carrier ─────────────────────────── */}
      <section className="carrier-mgmt__section">
        <h2 className="carrier-mgmt__section-title">
          {label("carriers.add_title", "Add a Carrier")}
        </h2>

        {loadingAvailable ? (
          <p className="carrier-mgmt__loading">{label_shared("loading", "Loading…")}</p>
        ) : available.length === 0 ? (
          <p className="carrier-mgmt__all-assigned">
            {label("carriers.all_assigned", "All available platform carriers are already assigned to your organisation.")}
          </p>
        ) : (
          <div className="carrier-mgmt__add-form">
            <label className="carrier-mgmt__add-label" htmlFor="carrier-select">
              {label("carriers.select_label", "Select carrier to add")}
            </label>
            <div className="carrier-mgmt__add-row">
              <select
                id="carrier-select"
                className="carrier-mgmt__select"
                value={selectedAvailableId ?? ""}
                onChange={(e) => {
                  setSelectedAvailableId(e.target.value ? Number(e.target.value) : null);
                  setAddError(null);
                }}
              >
                <option value="">{label("carriers.select_placeholder", "— Select a carrier —")}</option>
                {available.map((c) => (
                  <option key={c.carrier_id} value={c.carrier_id}>{c.carrier_name}</option>
                ))}
              </select>
              <button
                className="btn btn--primary"
                onClick={() => { if (selectedAvailableId !== null) addMutation.mutate(selectedAvailableId); }}
                disabled={selectedAvailableId === null || addMutation.isPending}
              >
                {addMutation.isPending
                  ? label("carriers.btn.adding", "Adding…")
                  : label("carriers.btn.add",    "Add Carrier")}
              </button>
            </div>
            {addError && <p className="carrier-mgmt__error" role="alert">{addError}</p>}
            <p className="carrier-mgmt__add-hint">
              {label("carriers.add_hint", "Adding a carrier seeds default calculation rules and configuration. Rules can be customised from the Carrier Configuration Hub.")}
            </p>
          </div>
        )}
      </section>

      {/* ── Section 3: Create a New Carrier ────────────────────────────── */}
      <section className="carrier-mgmt__section">
        <div className="carrier-mgmt__create-header">
          <h2 className="carrier-mgmt__section-title">
            {label("carriers.create_title", "Create a New Carrier")}
          </h2>
          {!showCreateForm && (
            <button
              className="btn btn--secondary btn--sm"
              onClick={() => setShowCreateForm(true)}
            >
              {label("carriers.btn.create", "+ New Carrier")}
            </button>
          )}
        </div>

        {!showCreateForm ? (
          <p className="carrier-mgmt__create-hint">
            {label(
              "carriers.create_hint",
              "Don't see the carrier you need? Create a new one and it will be assigned to your organisation immediately."
            )}
          </p>
        ) : (
          <div className="carrier-mgmt__create-form">
            <div className="carrier-mgmt__create-fields">
              <div className="carrier-mgmt__field">
                <label className="carrier-mgmt__field-label" htmlFor="new-carrier-name">
                  {label("carriers.create_name_label", "Carrier Name")}
                </label>
                <input
                  id="new-carrier-name"
                  type="text"
                  className="carrier-mgmt__input"
                  placeholder={label("carriers.create_name_placeholder", "e.g. Acme Insurance")}
                  value={newCarrierName}
                  onChange={(e) => handleNameChange(e.target.value)}
                  maxLength={200}
                />
              </div>

              <div className="carrier-mgmt__field">
                <label className="carrier-mgmt__field-label" htmlFor="new-carrier-slug">
                  {label("carriers.create_slug_label", "Identifier (slug)")}
                </label>
                <input
                  id="new-carrier-slug"
                  type="text"
                  className="carrier-mgmt__input"
                  placeholder={label("carriers.create_slug_placeholder", "e.g. acme-insurance")}
                  value={newCarrierSlug}
                  onChange={(e) => {
                    setNewCarrierSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""));
                    setSlugManuallyEdited(true);
                  }}
                  maxLength={62}
                />
                <span className="carrier-mgmt__field-hint">
                  {label("carriers.create_slug_hint", "Lowercase letters, numbers, and hyphens only. Cannot be changed later.")}
                </span>
              </div>
            </div>

            {createError && (
              <p className="carrier-mgmt__error" role="alert">{createError}</p>
            )}

            <div className="carrier-mgmt__create-actions">
              <button
                className="btn btn--primary"
                onClick={handleCreateSubmit}
                disabled={
                  !newCarrierName.trim() ||
                  !newCarrierSlug.trim() ||
                  newCarrierSlug.length < 2 ||
                  createMutation.isPending
                }
              >
                {createMutation.isPending
                  ? label("carriers.btn.creating", "Creating…")
                  : label("carriers.btn.create_confirm", "Create & Assign")}
              </button>
              <button
                className="btn btn--secondary"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewCarrierName("");
                  setNewCarrierSlug("");
                  setSlugManuallyEdited(false);
                  setCreateError(null);
                }}
                disabled={createMutation.isPending}
              >
                {label("carriers.btn.cancel", "Cancel")}
              </button>
            </div>
          </div>
        )}
      </section>

    </div>
  );
}