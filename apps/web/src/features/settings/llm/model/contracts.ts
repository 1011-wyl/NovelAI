export type LlmProvider = "deepseek" | "dashscope" | "openai" | "openai_compatible";

export type LlmCardStatus = "enabled" | "unconfigured" | "unverified" | "needs_attention" | "disabled";

export type LlmConfigSource = "saved" | "environment" | "offline" | "none";

export type LlmPreset = {
  provider: LlmProvider;
  provider_label: string;
  base_url: string;
  model: string;
};

export type LlmSettingsView = {
  provider: LlmProvider | string | null;
  provider_label: string | null;
  base_url: string | null;
  model: string | null;
  enabled: boolean;
  has_api_key: boolean;
  api_key_mask: string | null;
  verification_status: "unverified" | "valid" | "invalid" | string;
  last_tested_at: string | null;
  last_error_code: string | null;
  source: LlmConfigSource;
  version: number;
  timeout_seconds: number;
  max_retries: number;
  card_status: LlmCardStatus;
  presets: LlmPreset[];
};

export type LlmTestResult = {
  ok: boolean;
  code: string;
  message: string;
  latency_ms: number;
  tested_at: string;
};

export type LlmSavePayload = {
  provider: LlmProvider;
  base_url: string;
  model: string;
  api_key?: string;
  keep_existing_api_key?: boolean;
  enabled: boolean;
  timeout_seconds: number;
  max_retries: number;
  expected_version: number;
};
