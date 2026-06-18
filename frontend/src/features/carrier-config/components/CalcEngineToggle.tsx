// /**
//  * CalcEngineToggle — Phase 3.
//  *
//  * Renders the engine ON/OFF toggle switch in the Carrier Config Hub Tab 3.
//  * Calls PUT /api/v1/admin/calc-config/{carrierId} when toggled.
//  * TENANT_ADMIN only — read-only indicator shown for other roles.
//  *
//  * V9 S15.2 Tab 3 spec.
//  *
//  * Props contract:
//  *   Uncontrolled (production):  pass carrierId only — fetches config internally.
//  *   Controlled  (tests/parent): pass carrierId + currentValue + isAdmin + onToggle + isSaving.
//  *   When currentValue is defined the internal hook fetch is skipped entirely.
//  */

// import React, { useState } from "react";
// import { useLabels } from "@/hooks/useLabels";
// import { useCarrierCalcConfig } from "../hooks/useCarrierCalcConfig";

// interface CalcEngineToggleProps {
//   carrierId: number;
//   readonly?: boolean;
//   /** Controlled mode: current engine state. Skips internal hook when provided. */
//   currentValue?: boolean;
//   /** Controlled mode: whether the current user may toggle. */
//   isAdmin?: boolean;
//   /** Controlled mode: callback fired with the new value. */
//   onToggle?: (next: boolean) => void | Promise<void>;
//   /** Controlled mode: shows saving indicator. */
//   isSaving?: boolean;
// }

// export function CalcEngineToggle({
//   carrierId,
//   readonly = false,
//   currentValue,
//   isAdmin,
//   onToggle,
//   isSaving: isSavingProp,
// }: CalcEngineToggleProps): React.JSX.Element {
//   const label_calc_engine = useLabels("calc_engine");
//   const label_shared = useLabels("shared");

//   // Controlled mode: when currentValue is supplied, skip the hook.
//   const isControlled = currentValue !== undefined;
//   const hookResult = useCarrierCalcConfig(isControlled ? 0 : carrierId);

//   const isLoading  = isControlled ? false : hookResult.isLoading;
//   const isError    = isControlled ? false : hookResult.isError;
//   const isToggling = isControlled ? (isSavingProp ?? false) : hookResult.isToggling;

//   const [optimistic, setOptimistic] = useState<boolean | null>(null);

//   const engineOn = optimistic !== null
//     ? optimistic
//     : isControlled
//       ? currentValue!
//       : (hookResult.config?.use_calculation_engine ?? true);

//   // In controlled mode, isAdmin=false means read-only; in uncontrolled, use readonly prop.
//   const effectiveReadonly = isControlled ? (isAdmin === false) : readonly;

//   async function handleToggle(): Promise<void> {
//     if (effectiveReadonly || isToggling) return;
//     const next = !engineOn;
//     setOptimistic(next);
//     try {
//       if (isControlled && onToggle) {
//         await onToggle(next);
//       } else {
//         await hookResult.toggle(next);
//       }
//     } catch {
//       setOptimistic(null);
//     } finally {
//       setOptimistic(null);
//     }
//   }

//   if (isLoading) {
//     return <div className="calc-engine-toggle__skeleton" aria-busy="true" />;
//   }

//   if (isError) {
//     return (
//       <div className="calc-engine-toggle calc-engine-toggle--error">
//         <span className="calc-engine-toggle__error-text">
//           {label_shared("calc_engine_load_error", "calc_engine_load_error") ?? "Failed to load engine config"}
//         </span>
//       </div>
//     );
//   }

//   return (
//     <div className="calc-engine-toggle">
//       <div className="calc-engine-toggle__header">
//         <div className="calc-engine-toggle__title-group">
//           <h3 className="calc-engine-toggle__title">
//             {label_shared("calc_engine_title", "calc_engine_title") ?? "Calculation Engine"}
//           </h3>
//           <p className="calc-engine-toggle__description">
//             {label_shared("calc_engine_description", "calc_engine_description") ??
//               "When enabled, the audit calculation engine runs automatically after data ingestion, computing variance percentages, payroll metrics, and risk assessments."}
//           </p>
//         </div>

//         <div className="calc-engine-toggle__control">
//           {/*
//            * .calc-engine-toggle__track is the clickable outer element.
//            * Tests locate the toggle by this class name.
//            */}
//           <button
//             type="button"
//             role="switch"
//             aria-checked={engineOn}
//             aria-label={
//               engineOn
//                 ? (label_shared("calc_engine_on", "calc_engine_on") ?? "Engine enabled — click to disable")
//                 : (label_shared("calc_engine_off", "calc_engine_off") ?? "Engine disabled — click to enable")
//             }
//             className={[
//               "calc-engine-toggle__track",
//               engineOn ? "calc-engine-toggle__track--on" : "calc-engine-toggle__track--off",
//               effectiveReadonly ? "calc-engine-toggle__track--readonly" : "",
//               isToggling ? "calc-engine-toggle__track--loading" : "",
//             ]
//               .filter(Boolean)
//               .join(" ")}
//             onClick={handleToggle}
//             disabled={effectiveReadonly || isToggling}
//           >
//             <span className="calc-engine-toggle__thumb" />
//           </button>

//           <span
//             className={[
//               "calc-engine-toggle__label",
//               engineOn
//                 ? "calc-engine-toggle__label--on"
//                 : "calc-engine-toggle__label--off",
//             ].join(" ")}
//           >
//             {isToggling
//               ? (label_calc_engine("toggle.saving", "Saving…") ?? "Saving…")
//               : engineOn
//               ? (label_shared("calc_engine_status_on", "calc_engine_status_on") ?? "ON")
//               : (label_shared("calc_engine_status_off", "calc_engine_status_off") ?? "OFF")}
//           </span>
//         </div>
//       </div>

//       {/* Warning banner — shown when engine is OFF */}
//       {!engineOn && (
//         <div className="calc-engine-toggle__warning" role="alert">
//           <span className="calc-engine-toggle__warning-icon">⚠</span>
//           <span>
//             {label_calc_engine("toggle.off_warning", "Engine is OFF. All engine-derived fields (Variance %, Risk Level) will show N/A on the dashboard.") ??
//               "Engine is OFF. Variance percentages and risk levels will show N/A after ingestion."}
//           </span>
//         </div>
//       )}

//       {/* Read-only notice — shown for non-admin users */}
//       {effectiveReadonly && (
//         <p className="calc-engine-toggle__readonly">
//           {label_shared("calc_engine_readonly_note", "calc_engine_readonly_note") ??
//             "Only Tenant Administrators can change the engine configuration."}
//         </p>
//       )}
//     </div>
//   );
// }

/**
 * CalcEngineToggle — Phase 3.
 *
 * Renders the engine ON/OFF toggle switch in the Carrier Config Hub Tab 3.
 * Calls PUT /api/v1/admin/calc-config/{carrierId} when toggled.
 * TENANT_ADMIN only — read-only indicator shown for other roles.
 *
 * V9 S15.2 Tab 3 spec.
 *
 * Props contract:
 *   Uncontrolled (production):  pass carrierId only — fetches config internally.
 *   Controlled  (tests/parent): pass carrierId + currentValue + isAdmin + onToggle + isSaving.
 *   When currentValue is defined the internal hook fetch is skipped entirely.
 */

import React, { useState } from "react";
import { useLabels } from "@/hooks/useLabels";
import { useCarrierCalcConfig } from "../hooks/useCarrierCalcConfig";

interface CalcEngineToggleProps {
  carrierId: number;
  readonly?: boolean;
  /** Controlled mode: current engine state. Skips internal hook when provided. */
  currentValue?: boolean;
  /** Controlled mode: whether the current user may toggle. */
  isAdmin?: boolean;
  /** Controlled mode: callback fired with the new value. */
  onToggle?: (next: boolean) => void | Promise<void>;
  /** Controlled mode: shows saving indicator. */
  isSaving?: boolean;
}

export function CalcEngineToggle({
  carrierId,
  readonly = false,
  currentValue,
  isAdmin,
  onToggle,
  isSaving: isSavingProp,
}: CalcEngineToggleProps): React.JSX.Element {
  const label_calc_engine = useLabels("calc_engine");

  // Controlled mode: when currentValue is supplied, skip the hook.
  const isControlled = currentValue !== undefined;
  const hookResult = useCarrierCalcConfig(isControlled ? 0 : carrierId);

  const isLoading  = isControlled ? false : hookResult.isLoading;
  const isError    = isControlled ? false : hookResult.isError;
  const isToggling = isControlled ? (isSavingProp ?? false) : hookResult.isToggling;

  const [optimistic, setOptimistic] = useState<boolean | null>(null);

  const engineOn = optimistic !== null
    ? optimistic
    : isControlled
      ? currentValue!
      : (hookResult.config?.use_calculation_engine ?? true);

  // In controlled mode, isAdmin=false means read-only; in uncontrolled, use readonly prop.
  const effectiveReadonly = isControlled ? (isAdmin === false) : readonly;

  async function handleToggle(): Promise<void> {
    if (effectiveReadonly || isToggling) return;
    const next = !engineOn;
    setOptimistic(next);
    try {
      if (isControlled && onToggle) {
        await onToggle(next);
      } else {
        await hookResult.toggle(next);
      }
    } catch {
      setOptimistic(null);
    } finally {
      setOptimistic(null);
    }
  }

  if (isLoading) {
    return <div className="calc-engine-toggle__skeleton" aria-busy="true" />;
  }

  if (isError) {
    return (
      <div className="calc-engine-toggle calc-engine-toggle--error">
        <span className="calc-engine-toggle__error-text">
          {label_calc_engine("toggle.load_error", "Failed to load engine config")}
        </span>
      </div>
    );
  }

  return (
    <div className="calc-engine-toggle">
      <div className="calc-engine-toggle__header">
        <div className="calc-engine-toggle__title-group">
          <h3 className="calc-engine-toggle__title">
            {label_calc_engine("toggle.label", "Calculation Engine")}
          </h3>
          <p className="calc-engine-toggle__description">
            {label_calc_engine("toggle.description", "When enabled, the audit calculation engine runs automatically after data ingestion, computing variance percentages, payroll metrics, and risk assessments.")}
          </p>
        </div>

        <div className="calc-engine-toggle__control">
          {/*
           * .calc-engine-toggle__track is the clickable outer element.
           * Tests locate the toggle by this class name.
           */}
          <button
            type="button"
            role="switch"
            aria-checked={engineOn}
            aria-label={
              engineOn
                ? label_calc_engine("toggle.aria_on", "Engine enabled — click to disable")
                : label_calc_engine("toggle.aria_off", "Engine disabled — click to enable")
            }
            className={[
              "calc-engine-toggle__track",
              engineOn ? "calc-engine-toggle__track--on" : "calc-engine-toggle__track--off",
              effectiveReadonly ? "calc-engine-toggle__track--readonly" : "",
              isToggling ? "calc-engine-toggle__track--loading" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={handleToggle}
            disabled={effectiveReadonly || isToggling}
          >
            <span className="calc-engine-toggle__thumb" />
          </button>

          <span
            className={[
              "calc-engine-toggle__label",
              engineOn
                ? "calc-engine-toggle__label--on"
                : "calc-engine-toggle__label--off",
            ].join(" ")}
          >
            {isToggling
              ? (label_calc_engine("toggle.saving", "Saving…") ?? "Saving…")
              : engineOn
              ? label_calc_engine("toggle.on", "ON")
              : label_calc_engine("toggle.off", "OFF")}
          </span>
        </div>
      </div>

      {/* Warning banner — shown when engine is OFF */}
      {!engineOn && (
        <div className="calc-engine-toggle__warning" role="alert">
          <span className="calc-engine-toggle__warning-icon">⚠</span>
          <span>
            {label_calc_engine("toggle.off_warning", "Engine is OFF. All engine-derived fields (Variance %, Risk Level) will show N/A on the dashboard.") ??
              "Engine is OFF. Variance percentages and risk levels will show N/A after ingestion."}
          </span>
        </div>
      )}

      {/* Read-only notice — shown for non-admin users */}
      {effectiveReadonly && (
        <p className="calc-engine-toggle__readonly">
          {label_calc_engine("toggle.readonly_note", "Only Tenant Administrators can change the engine configuration.")}
        </p>
      )}
    </div>
  );
}