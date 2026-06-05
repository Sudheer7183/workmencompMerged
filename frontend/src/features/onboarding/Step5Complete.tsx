/**
 * Onboarding Step 5 — Completion.
 *
 * PATCH /api/v1/tenant/users/me  { onboarding_completed: true }
 * Navigates to /dashboard on success.
 */

import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext"

interface Props {
  onBack: () => void;
}

export function Step5Complete({ onBack }: Props): React.JSX.Element {
  const labels = useLabels();
  const navigate = useNavigate();
  const { completeOnboarding } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  const handleFinish = async () => {
    setError(null);
    setCompleting(true);
    try {
      await axios.patch("/api/v1/tenant/users/me", { onboarding_completed: true });
      completeOnboarding(); // update in-memory user so ProtectedRoute unlocks immediately
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data as { detail?: string })?.detail ?? labels.error_generic
          : labels.error_generic
      );
      setCompleting(false);
    }
  };

  return (
    <div className="onboarding-step onboarding-step--complete">
      <div className="onboarding-step__complete-icon" aria-hidden="true">✓</div>
      <h2 className="onboarding-step__title">{labels.onboarding_s5_title}</h2>
      <p className="onboarding-step__message">{labels.onboarding_s5_complete_msg}</p>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <div className="wizard-step__actions">
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          {labels.onboarding_btn_prev}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void handleFinish()}
          disabled={completing}
        >
          {completing ? labels.loading : labels.onboarding_btn_finish}
        </button>
      </div>
    </div>
  );
}
