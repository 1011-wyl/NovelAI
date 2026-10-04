import { requestJson } from "@/api/http-client";
import type { LlmSavePayload, LlmSettingsView, LlmTestResult } from "../model/contracts";

export function getLlmSettings(): Promise<LlmSettingsView> {
  return requestJson<LlmSettingsView>("/api/settings/llm");
}

export function saveLlmSettings(payload: LlmSavePayload): Promise<LlmSettingsView> {
  return requestJson<LlmSettingsView>("/api/settings/llm", { method: "PUT", body: payload });
}

export function testLlmSettings(payload: LlmSavePayload): Promise<LlmTestResult> {
  return requestJson<LlmTestResult>("/api/settings/llm/test", { method: "POST", body: payload });
}

export function deleteLlmSettings(): Promise<LlmSettingsView> {
  return requestJson<LlmSettingsView>("/api/settings/llm", { method: "DELETE", body: {} });
}
