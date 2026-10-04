import { describe, expect, it, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { ApiError } from "@/api/api-error";
import { useLlmSettings } from "./useLlmSettings";

const getLlmSettings = vi.fn();
const saveLlmSettings = vi.fn();
const testLlmSettings = vi.fn();
const deleteLlmSettings = vi.fn();

vi.mock("../api/llm-settings.api", () => ({
  getLlmSettings: () => getLlmSettings(),
  saveLlmSettings: (payload: unknown) => saveLlmSettings(payload),
  testLlmSettings: (payload: unknown) => testLlmSettings(payload),
  deleteLlmSettings: () => deleteLlmSettings(),
}));

const view = {
  provider: "deepseek",
  provider_label: "DeepSeek",
  base_url: "https://api.deepseek.com",
  model: "deepseek-chat",
  enabled: true,
  has_api_key: true,
  api_key_mask: "••••1234",
  verification_status: "valid",
  last_tested_at: null,
  last_error_code: null,
  source: "saved",
  version: 3,
  timeout_seconds: 120,
  max_retries: 2,
  card_status: "enabled",
  presets: [
    { provider: "deepseek", provider_label: "DeepSeek", base_url: "https://api.deepseek.com", model: "deepseek-chat" },
    {
      provider: "dashscope",
      provider_label: "阿里云百炼 DashScope",
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen-plus",
    },
  ],
};

describe("useLlmSettings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    getLlmSettings.mockResolvedValue(view);
    saveLlmSettings.mockResolvedValue(view);
    testLlmSettings.mockResolvedValue({
      ok: true,
      code: "CONNECTION_OK",
      message: "连接成功",
      latency_ms: 12,
      tested_at: "2026-10-04T10:00:00+08:00",
    });
  });

  it("does not refill a complete key and keeps old key when empty", async () => {
    const llm = useLlmSettings();
    await llm.load();
    expect(llm.form.apiKey).toBe("");
    expect(llm.view.value.api_key_mask).toBe("••••1234");
    const payload = llm.payload ? undefined : undefined;
    await llm.saveAndEnable();
    const sent = saveLlmSettings.mock.calls[0][0] as { api_key?: string; keep_existing_api_key?: boolean };
    expect(sent.api_key).toBeUndefined();
    expect(sent.keep_existing_api_key).toBe(true);
    expect(JSON.stringify(sent)).not.toContain("sk-real");
    expect(payload).toBeUndefined();
  });

  it("updates presets unless the user already edited fields", async () => {
    const llm = useLlmSettings();
    await llm.load();
    llm.onProviderChange("dashscope");
    expect(llm.form.baseUrl).toContain("dashscope");
    llm.userEdited.model = true;
    llm.form.model = "my-custom";
    llm.onProviderChange("deepseek");
    expect(llm.form.model).toBe("my-custom");
  });

  it("marks edited config as pending and does not save after a failed test", async () => {
    const llm = useLlmSettings();
    await llm.load();
    llm.markDirty();
    expect(llm.view.value.card_status).toBe("unverified");
    testLlmSettings.mockRejectedValue(
      new ApiError("API Key 无效或已失效", {
        status: 502,
        payload: { error: "INVALID_API_KEY", message: "API Key 无效或已失效" },
      })
    );
    llm.form.apiKey = "typed-secret";
    await llm.testConnection();
    expect(llm.formState.value).toBe("error");
    expect(llm.errorMessage.value).toBe("API Key 无效或已失效");
    expect(saveLlmSettings).not.toHaveBeenCalled();
    expect(JSON.stringify(testLlmSettings.mock.calls[0][0])).not.toContain("sk-real");
  });
});
