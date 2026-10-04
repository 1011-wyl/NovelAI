import type { SettingsPayload } from "@/api/contracts";
import { requestJson } from "@/api/http-client";

export async function getSettings(): Promise<SettingsPayload> {
  return requestJson<SettingsPayload>("/api/settings");
}

export async function saveSettings(payload: {
  daily_chapters: number;
  reserve_target: number;
  budget_limit: number;
  debug_mode: boolean;
}): Promise<SettingsPayload> {
  return requestJson<SettingsPayload>("/api/settings", {
    method: "PUT",
    body: payload,
  });
}
