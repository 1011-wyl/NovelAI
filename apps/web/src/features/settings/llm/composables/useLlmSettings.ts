import { computed, reactive, ref } from "vue";
import { isApiError } from "@/api/api-error";
import { deleteLlmSettings, getLlmSettings, saveLlmSettings, testLlmSettings } from "../api/llm-settings.api";
import type { LlmProvider, LlmSettingsView, LlmTestResult } from "../model/contracts";
import { presetFor } from "../model/providers";
import { validateLlmForm } from "../model/validation";

export type LlmFormState = "idle" | "loading" | "testing" | "saving" | "deleting" | "success" | "error";

const emptyView = (): LlmSettingsView => ({
  provider: null,
  provider_label: null,
  base_url: null,
  model: null,
  enabled: false,
  has_api_key: false,
  api_key_mask: null,
  verification_status: "unverified",
  last_tested_at: null,
  last_error_code: null,
  source: "none",
  version: 0,
  timeout_seconds: 120,
  max_retries: 2,
  card_status: "unconfigured",
  presets: [],
});

export function useLlmSettings() {
  const view = ref<LlmSettingsView>(emptyView());
  const formState = ref<LlmFormState>("idle");
  const errorMessage = ref<string | null>(null);
  const testResult = ref<LlmTestResult | null>(null);
  const showKey = ref(false);
  const advancedOpen = ref(false);
  const dirty = ref(false);
  const userEdited = reactive({ baseUrl: false, model: false });

  const form = reactive({
    provider: "deepseek" as LlmProvider,
    baseUrl: "",
    model: "",
    apiKey: "",
    timeoutSeconds: 120,
    maxRetries: 2,
    enabled: true,
  });

  const busy = computed(() => ["loading", "testing", "saving", "deleting"].includes(formState.value));

  function applyView(next: LlmSettingsView) {
    view.value = next;
    form.provider = (next.provider as LlmProvider) || "deepseek";
    form.baseUrl = next.base_url || presetFor(next.presets, form.provider)?.base_url || "";
    form.model = next.model || presetFor(next.presets, form.provider)?.model || "";
    form.apiKey = "";
    form.timeoutSeconds = next.timeout_seconds || 120;
    form.maxRetries = next.max_retries ?? 2;
    form.enabled = next.enabled || next.card_status === "unconfigured";
    dirty.value = false;
    userEdited.baseUrl = false;
    userEdited.model = false;
    showKey.value = false;
  }

  function markDirty() {
    dirty.value = true;
    if (view.value.card_status === "enabled" || view.value.card_status === "disabled") {
      view.value.card_status = "unverified";
      view.value.verification_status = "unverified";
    }
  }

  function onProviderChange(provider: LlmProvider) {
    form.provider = provider;
    const preset = presetFor(view.value.presets, provider);
    if (preset && !userEdited.baseUrl) form.baseUrl = preset.base_url;
    if (preset && !userEdited.model) form.model = preset.model;
    markDirty();
  }

  async function load() {
    formState.value = "loading";
    errorMessage.value = null;
    try {
      applyView(await getLlmSettings());
      formState.value = "idle";
    } catch (error) {
      formState.value = "error";
      errorMessage.value = isApiError(error) ? error.message : "加载大模型配置失败";
    }
  }

  function payload(includeKey: boolean) {
    return {
      provider: form.provider,
      base_url: form.baseUrl.trim(),
      model: form.model.trim(),
      api_key: includeKey && form.apiKey.trim() ? form.apiKey.trim() : undefined,
      keep_existing_api_key: !form.apiKey.trim() && view.value.has_api_key,
      enabled: form.enabled,
      timeout_seconds: Number(form.timeoutSeconds),
      max_retries: Number(form.maxRetries),
      expected_version: view.value.version,
    };
  }

  async function testConnection() {
    const invalid = validateLlmForm({
      provider: form.provider,
      baseUrl: form.baseUrl,
      model: form.model,
      timeoutSeconds: Number(form.timeoutSeconds),
      maxRetries: Number(form.maxRetries),
    });
    if (invalid) {
      errorMessage.value = invalid;
      formState.value = "error";
      return;
    }
    if (!form.apiKey.trim() && !view.value.has_api_key) {
      errorMessage.value = "请填写 API Key";
      formState.value = "error";
      return;
    }
    formState.value = "testing";
    errorMessage.value = null;
    try {
      testResult.value = await testLlmSettings(payload(true));
      formState.value = "idle";
    } catch (error) {
      formState.value = "error";
      errorMessage.value = isApiError(error) ? error.message : "测试连接失败";
      testResult.value = null;
    }
  }

  async function saveAndEnable() {
    const invalid = validateLlmForm({
      provider: form.provider,
      baseUrl: form.baseUrl,
      model: form.model,
      timeoutSeconds: Number(form.timeoutSeconds),
      maxRetries: Number(form.maxRetries),
    });
    if (invalid) {
      errorMessage.value = invalid;
      formState.value = "error";
      return false;
    }
    form.enabled = true;
    formState.value = "saving";
    errorMessage.value = null;
    try {
      applyView(await saveLlmSettings(payload(true)));
      formState.value = "success";
      return true;
    } catch (error) {
      formState.value = "error";
      errorMessage.value = isApiError(error) ? error.message : "保存失败";
      return false;
    }
  }

  async function disable() {
    form.enabled = false;
    formState.value = "saving";
    try {
      applyView(await saveLlmSettings(payload(true)));
      formState.value = "success";
      return true;
    } catch (error) {
      formState.value = "error";
      errorMessage.value = isApiError(error) ? error.message : "停用失败";
      return false;
    }
  }

  async function clear() {
    formState.value = "deleting";
    try {
      applyView(await deleteLlmSettings());
      formState.value = "success";
      testResult.value = null;
      return true;
    } catch (error) {
      formState.value = "error";
      errorMessage.value = isApiError(error) ? error.message : "清除失败";
      return false;
    }
  }

  return {
    view,
    form,
    formState,
    errorMessage,
    testResult,
    showKey,
    advancedOpen,
    dirty,
    userEdited,
    busy,
    load,
    applyView,
    markDirty,
    onProviderChange,
    testConnection,
    saveAndEnable,
    disable,
    clear,
  };
}
