import { defineStore } from "pinia";
import { ref } from "vue";
import type { HealthPayload } from "@/api/contracts";
import { requestJson } from "@/api/http-client";

export type HealthState = "unknown" | "ok" | "degraded" | "down";

const SIDEBAR_COLLAPSED_KEY = "novelAgentSidebarCollapsed";

function readSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export const useAppStore = defineStore("app", () => {
  const sidebarOpen = ref(false);
  const sidebarCollapsed = ref(readSidebarCollapsed());
  const health = ref<HealthState>("unknown");
  const healthMessage = ref("服务状态未知");
  const busy = ref(false);
  const busyLabel = ref("智能体正在工作");
  const flashMessage = ref<string | null>(null);
  const flashError = ref(false);
  let flashTimer: ReturnType<typeof setTimeout> | null = null;

  function toggleSidebar(force?: boolean) {
    sidebarOpen.value = force ?? !sidebarOpen.value;
  }

  function toggleSidebarCollapsed(force?: boolean) {
    sidebarCollapsed.value = force ?? !sidebarCollapsed.value;
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed.value ? "1" : "0");
    } catch {
      /* ignore private mode / quota failures */
    }
  }

  function setHealth(next: HealthState, message: string) {
    health.value = next;
    healthMessage.value = message;
  }

  function setBusy(value: boolean, label = "智能体正在工作") {
    busy.value = value;
    busyLabel.value = label;
  }

  function flash(message: string, isError = false) {
    flashMessage.value = message;
    flashError.value = isError;
    if (flashTimer) clearTimeout(flashTimer);
    flashTimer = setTimeout(() => {
      flashMessage.value = null;
    }, 5000);
  }

  async function refreshHealth() {
    try {
      const payload = await requestJson<HealthPayload>("/api/health");
      const mode = payload.mode === "offline" ? "离线安全模式" : "在线模式";
      const enabled = Object.entries(payload.apis || {})
        .filter(([, item]) => item?.enabled)
        .map(([name]) => name.toUpperCase());
      const hint = enabled.length ? `${enabled.join(" · ")} 已启用` : "外部 API 未启用";
      setHealth(payload.mode === "offline" ? "degraded" : "ok", `${mode} · ${hint}`);
      return payload;
    } catch {
      setHealth("down", "服务未连接 · 请启动本地 API");
      return null;
    }
  }

  return {
    sidebarOpen,
    sidebarCollapsed,
    health,
    healthMessage,
    busy,
    busyLabel,
    flashMessage,
    flashError,
    toggleSidebar,
    toggleSidebarCollapsed,
    setHealth,
    setBusy,
    flash,
    refreshHealth,
  };
});
