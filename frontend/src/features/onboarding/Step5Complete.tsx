/**
 * Onboarding Step 5 — Completion.
 *
 * PATCH /api/v1/tenant/users/me  { onboarding_completed: true }
 * Navigates to /dashboard on success.
 *
 * Fixes applied:
 *  1. Removed large commented-out duplicate block that contained the broken
 *     label call AND a stray `const label_shared = useLabels("shared")` sitting
 *     outside any component body (a React rules-of-hooks violation that would
 *     also cause a compile error).
 *  2. label_shared("onboarding_s", "onboarding_s")5_title      → label_onboarding("step5.title", …)
 *  3. label_shared("onboarding_s", "onboarding_s")5_complete_msg → label_onboarding("step5.message", …)
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";

interface Props {
  onBack: () => void;
}

export function Step5Complete({ onBack }: Props): React.JSX.Element {
  const label_onboarding = useLabels("onboarding");
  const label_shared = useLabels("shared");
  const navigate = useNavigate();
  const { completeOnboarding } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  const handleFinish = async (): Promise<void> => {
    setError(null);
    setCompleting(true);
    try {
      await axios.patch("/api/v1/tenant/users/me", { onboarding_completed: true });
      completeOnboarding(); // update in-memory user so ProtectedRoute unlocks immediately
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail
            ?? label_shared("error_generic", "Something went wrong. Please try again.")
          : label_shared("error_generic", "Something went wrong. Please try again.")
      );
      setCompleting(false);
    }
  };

  return (
    <div className="onboarding-step onboarding-step--complete">
      <div className="onboarding-step__complete-icon" aria-hidden="true">✓</div>

      {/* FIX: was label_shared("onboarding_s", "onboarding_s")5_title */}
      <h2 className="onboarding-step__title">
        {label_onboarding("step5.title", "Setup Complete")}
      </h2>

      {/* FIX: was label_shared("onboarding_s", "onboarding_s")5_complete_msg */}
      <p className="onboarding-step__message">
        {label_onboarding("step5.message", "Your organization is ready. Head to the dashboard to get started.")}
      </p>

      {error && (
        <div className="alert alert--error" role="alert">{error}</div>
      )}

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {label_onboarding("btn.prev", "Previous")}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void handleFinish()}
          disabled={completing}
        >
          {completing
            ? label_shared("loading", "Loading…")
            : label_onboarding("btn.finish", "Go to Dashboard")}
        </button>
      </div>
    </div>
  );
}