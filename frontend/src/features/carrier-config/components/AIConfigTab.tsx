/**
 * AIConfigTab — Phase 7C — Tab 7 of CarrierConfigHub.
 *
 * Allows TENANT_ADMIN to configure a carrier-scoped LLM provider.
 * The api_key field is write-only; only the last 4 digits are shown after save.
 * All colours via CSS custom properties. No style={{}} props for visual styling.
 */

import React, { useState, useEffect } from "react";
import axios from "axios";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLabels } from "@/hooks/useLabels";

// ── Provider options ─────────────────────────────────────────────────────────

interface ModelOption {
  value: string;
  label: string;
}

interface ProviderOption {
  value: string;
  label: string;
  requiresApiKey: boolean;
  requiresBaseUrl: boolean;
  models: ModelOption[];
}

export const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    value: "anthropic",
    label: "Anthropic (Claude)",
    requiresApiKey: true,
    requiresBaseUrl: false,
    models: [
      { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
      { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
      { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
    ],
  },
  {
    value: "openai",
    label: "OpenAI",
    requiresApiKey: true,
    requiresBaseUrl: false,
    models: [
      { value: "gpt-4o", label: "GPT-4o" },
      { value: "gpt-4o-mini", label: "GPT-4o Mini" },
      { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
    ],
  },
  {
    value: "azure_openai",
    label: "Azure OpenAI",
    requiresApiKey: true,
    requiresBaseUrl: true,
    models: [
      { value: "gpt-4o", label: "GPT-4o (deployment name)" },
      { value: "gpt-35-turbo", label: "GPT-3.5 Turbo (deployment name)" },
    ],
  },
  {
    value: "google",
    label: "Google (Gemini)",
    requiresApiKey: true,
    requiresBaseUrl: false,
    models: [
      { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash (recommended)" },
      { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
      { value: "gemini-1.5-flash-001", label: "Gemini 1.5 Flash 001" },
      { value: "gemini-1.5-flash-002", label: "Gemini 1.5 Flash 002" },
      { value: "gemini-1.5-pro-001", label: "Gemini 1.5 Pro 001" },
      { value: "gemini-1.5-pro-002", label: "Gemini 1.5 Pro 002" },
    ],
  },
  {
    value: "groq",
    label: "Groq",
    requiresApiKey: true,
    requiresBaseUrl: false,
    models: [
      { value: "llama-3.3-70b-versatile", label: "LLaMA 3.3 70B Versatile (recommended)" },
      { value: "llama-3.1-8b-instant", label: "LLaMA 3.1 8B Instant" },
      { value: "llama3-70b-8192", label: "LLaMA 3 70B" },
      { value: "llama3-8b-8192", label: "LLaMA 3 8B" },
      { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B" },
      { value: "gemma2-9b-it", label: "Gemma 2 9B" },
    ],
  },
  {
    value: "ollama",
    label: "Ollama (Self-hosted)",
    requiresApiKey: false,
    requiresBaseUrl: true,
    models: [
      { value: "llama3", label: "LLaMA 3" },
      { value: "mistral", label: "Mistral" },
      { value: "phi3", label: "Phi-3" },
    ],
  },
  {
    value: "openai_compatible",
    label: "OpenAI-Compatible",
    requiresApiKey: false,
    requiresBaseUrl: true,
    models: [
      { value: "local-model", label: "Local Model (custom)" },
    ],
  },
];

// ── Types ────────────────────────────────────────────────────────────────────

interface LLMConfigResponse {
  config_id: number;
  carrier_id: number;
  provider_name: string | null;
  model_name: string | null;
  api_key_last4: string | null;
  api_base_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface TestResult {
  success: boolean;
  latency_ms: number;
  provider: string;
  model: string;
  error?: string | null;
}

interface AIConfigTabProps {
  carrierId: number;
}

// ── Component ────────────────────────────────────────────────────────────────

export function AIConfigTab({ carrierId }: AIConfigTabProps): React.JSX.Element {
  const label = useLabels("ai_config");
  const labelShared = useLabels("shared");
  const qc = useQueryClient();

  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [apiKey, setApiKey] = useState<string>("");
  const [apiBaseUrl, setApiBaseUrl] = useState<string>("");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const { data: config, isLoading } = useQuery<LLMConfigResponse | null>({
    queryKey: ["llm-config", carrierId],
    queryFn: async () => {
      try {
        const { data } = await axios.get<LLMConfigResponse | null>(
          `/api/v1/admin/llm-config?carrier_id=${carrierId}`
        );
        return data;
      } catch {
        return null;
      }
    },
    staleTime: 30 * 1000,
    enabled: carrierId > 0,
  });

  // Pre-fill form from existing config
  useEffect(() => {
    if (config?.provider_name) {
      setSelectedProvider(config.provider_name);
      setSelectedModel(config.model_name ?? "");
      setApiBaseUrl(config.api_base_url ?? "");
    }
  }, [config]);

  const currentProvider = PROVIDER_OPTIONS.find((p) => p.value === selectedProvider);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        carrier_id: carrierId,
        provider_name: selectedProvider,
        model_name: selectedModel,
        api_base_url: apiBaseUrl || null,
      };
      if (apiKey) {
        payload.api_key = apiKey;
      }
      const { data } = await axios.post<LLMConfigResponse>(
        "/api/v1/admin/llm-config",
        payload
      );
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["llm-config", carrierId] });
      setApiKey(""); // Clear key field after save
      setSaveMsg(label("save_success", "AI configuration saved."));
      setTimeout(() => setSaveMsg(null), 4000);
    },
    onError: () => {
      setSaveMsg(label("save_error", "Failed to save configuration."));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!config?.config_id) return;
      await axios.delete(`/api/v1/admin/llm-config/${config.config_id}`);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["llm-config", carrierId] });
      setSelectedProvider("");
      setSelectedModel("");
      setApiKey("");
      setApiBaseUrl("");
    },
  });

  const testMutation = useMutation({
    mutationFn: async (): Promise<TestResult> => {
      const { data } = await axios.post<TestResult>(
        "/api/v1/admin/llm-config/test",
        { carrier_id: carrierId }
      );
      return data;
    },
    onSuccess: (data) => {
      setTestResult(data);
    },
  });

  if (isLoading) {
    return (
      <div className="ai-config-tab">
        <p className="text-muted">{labelShared("loading", "Loading…")}</p>
      </div>
    );
  }

  const hasConfig = config?.provider_name != null && config.is_active;

  return (
    <div className="ai-config-tab" data-testid="ai-config-tab">
      <div>
        <h2 className="section-title">{label("page_title", "AI Narrative Configuration")}</h2>
        <p className="ai-config-tab__subtitle">
          {label(
            "page_subtitle",
            "Configure the language model used to generate audit narratives for this carrier. Leave unconfigured to use the platform default (Anthropic Claude)."
          )}
        </p>
      </div>

      {/* Current configuration display */}
      <div className="ai-config-tab__current">
        <h3 className="ai-config-tab__current-title">
          {label("section_current", "Current Configuration")}
        </h3>
        {hasConfig ? (
          <dl className="detail-panel__dl">
            <dt>{label("provider_label", "Provider")}</dt>
            <dd>
              {PROVIDER_OPTIONS.find((p) => p.value === config.provider_name)?.label ??
                config.provider_name}
            </dd>
            <dt>{label("model_label", "Model")}</dt>
            <dd>{config.model_name}</dd>
            {config.api_key_last4 && (
              <>
                <dt>{label("api_key_label", "API Key")}</dt>
                <dd>
                  {label("api_key_stored_hint", "API key stored securely. Last 4 digits:")}{" "}
                  <code>••••{config.api_key_last4}</code>
                </dd>
              </>
            )}
            {config.api_base_url && (
              <>
                <dt>{label("api_base_url_label", "Base URL")}</dt>
                <dd>{config.api_base_url}</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="ai-config-tab__no-config">
            {label(
              "no_config_notice",
              "No AI configuration for this carrier. Using platform default (Anthropic Claude)."
            )}
          </p>
        )}
      </div>

      {/* Configuration form */}
      <div className="ai-config-tab__form">
        <div className="ai-config-tab__provider-grid">
          {/* Provider select */}
          <div className="form-field">
            <label className="form-field__label" htmlFor="ai-provider">
              {label("provider_label", "LLM Provider")}
            </label>
            <select
              id="ai-provider"
              className="form-field__select"
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value);
                setSelectedModel("");
              }}
              data-testid="select-provider"
            >
              <option value="">
                {label("select_provider_placeholder", "— Select a provider —")}
              </option>
              {PROVIDER_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {/* Model select */}
          <div className="form-field">
            <label className="form-field__label" htmlFor="ai-model">
              {label("model_label", "Model")}
            </label>
            <select
              id="ai-model"
              className="form-field__select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={!selectedProvider}
              data-testid="select-model"
            >
              <option value="">
                {label("select_model_placeholder", "— Select a model —")}
              </option>
              {currentProvider?.models.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* API Key (write-only) */}
        {currentProvider?.requiresApiKey && (
          <div className="form-field">
            <label className="form-field__label" htmlFor="ai-api-key">
              {label("api_key_label", "API Key")}
            </label>
            <input
              id="ai-api-key"
              className="form-field__input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                config?.api_key_last4
                  ? `Current key: ••••${config.api_key_last4} (leave blank to keep)`
                  : label("api_key_placeholder", "Enter API key (stored encrypted)")
              }
              data-testid="input-api-key"
              autoComplete="off"
            />
          </div>
        )}

        {/* Base URL */}
        {currentProvider?.requiresBaseUrl && (
          <div className="form-field">
            <label className="form-field__label" htmlFor="ai-base-url">
              {label("api_base_url_label", "API Base URL")}
            </label>
            <input
              id="ai-base-url"
              className="form-field__input"
              type="url"
              value={apiBaseUrl}
              onChange={(e) => setApiBaseUrl(e.target.value)}
              placeholder={label(
                "api_base_url_placeholder",
                "e.g. https://resource.openai.azure.com/"
              )}
              data-testid="input-base-url"
            />
          </div>
        )}

        {/* Save success/error message */}
        {saveMsg && (
          <div
            className={`alert ${
              saveMsg.includes("saved") ? "alert--success" : "alert--error"
            }`}
            role="status"
          >
            {saveMsg}
          </div>
        )}

        {/* Test result */}
        {testResult && (
          <div
            className={`ai-config-tab__test-result ai-config-tab__test-result--${
              testResult.success ? "success" : "error"
            }`}
            data-testid="test-result"
          >
            {testResult.success ? (
              <>
                ✓ {label("test_success", "Connection successful")} —{" "}
                {label("test_latency", "Latency:")} {testResult.latency_ms}ms
              </>
            ) : (
              <>
                ✗ {label("test_failed", "Connection failed")}: {testResult.error}
              </>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="ai-config-tab__actions">
          <button
            className="btn btn--primary"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !selectedProvider || !selectedModel}
            type="button"
            data-testid="btn-save-config"
          >
            {saveMutation.isPending
              ? label("btn_saving", "Saving…")
              : label("btn_save", "Save Configuration")}
          </button>

          {hasConfig && (
            <button
              className="btn btn--ghost"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
              type="button"
              data-testid="btn-test-connection"
            >
              {testMutation.isPending
                ? label("btn_testing", "Testing…")
                : label("btn_test", "Test Connection")}
            </button>
          )}

          {hasConfig && (
            <button
              className="btn btn--danger btn--sm"
              onClick={() => {
                if (confirm(label("delete_confirm", "Remove AI configuration for this carrier? The platform default will be used."))) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
              type="button"
              data-testid="btn-delete-config"
            >
              {label("btn_delete", "Remove Configuration")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}