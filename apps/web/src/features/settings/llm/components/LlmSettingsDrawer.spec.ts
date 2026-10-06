import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { ApiError } from "@/api/api-error";
import LlmSettingsDrawer from "./LlmSettingsDrawer.vue";

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
  version: 1,
  timeout_seconds: 120,
  max_retries: 2,
  card_status: "enabled",
  presets: [
    { provider: "deepseek", provider_label: "DeepSeek", base_url: "https://api.deepseek.com", model: "deepseek-chat" },
  ],
};

describe("LlmSettingsDrawer", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    getLlmSettings.mockResolvedValue(view);
    saveLlmSettings.mockResolvedValue(view);
    testLlmSettings.mockResolvedValue({
      ok: true,
      code: "CONNECTION_OK",
      message: "连接成功",
      latency_ms: 8,
      tested_at: "2026-10-04T10:00:00+08:00",
    });
  });

  it("asks before closing dirty form and keeps the drawer open when cancelled", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const wrapper = mount(LlmSettingsDrawer, {
      props: { open: true },
      attachTo: document.body,
    });
    await flushPromises();
    await wrapper.get('input[autocomplete="off"]').setValue("https://example.com/v1");
    await wrapper.get(".text-close").trigger("click");
    expect(confirm).toHaveBeenCalled();
    expect(wrapper.emitted("close")).toBeFalsy();
    confirm.mockRestore();
    wrapper.unmount();
  });

  it("does not show save success after a failed connection test", async () => {
    testLlmSettings.mockRejectedValue(
      new ApiError("API Key 无效或已失效", {
        status: 502,
        payload: { error: "INVALID_API_KEY", message: "API Key 无效或已失效" },
      })
    );
    const wrapper = mount(LlmSettingsDrawer, { props: { open: true } });
    await flushPromises();
    const buttons = wrapper.findAll("button");
    const testButton = buttons.find((button) => button.text() === "测试连接");
    await testButton!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("API Key 无效或已失效");
    expect(wrapper.find('[data-testid="llm-save-success"]').exists()).toBe(false);
    expect(saveLlmSettings).not.toHaveBeenCalled();
    expect(wrapper.html()).not.toContain("test-secret-value-do-not-use");
    wrapper.unmount();
  });

  it("disables without requiring a new API key", async () => {
    getLlmSettings.mockResolvedValue({ ...view, source: "environment", version: 0 });
    saveLlmSettings.mockResolvedValue({
      ...view,
      enabled: false,
      card_status: "disabled",
      source: "saved",
      version: 1,
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mount(LlmSettingsDrawer, { props: { open: true }, attachTo: document.body });
    await flushPromises();
    const disableButton = wrapper.findAll("button").find((button) => button.text() === "停用");
    await disableButton!.trigger("click");
    await flushPromises();
    expect(confirm).toHaveBeenCalled();
    expect(saveLlmSettings).toHaveBeenCalled();
    expect((saveLlmSettings.mock.calls[0][0] as { enabled: boolean }).enabled).toBe(false);
    expect(wrapper.emitted("saved")?.[0]).toEqual(["disable"]);
    confirm.mockRestore();
    wrapper.unmount();
  });

  it("uses full-width panel on a narrow viewport without horizontal overflow", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    const wrapper = mount(LlmSettingsDrawer, {
      props: { open: true },
      attachTo: document.body,
    });
    await flushPromises();
    const panel = wrapper.get('[role="dialog"]').element as HTMLElement;
    expect(panel.scrollWidth).toBeLessThanOrEqual(panel.clientWidth + 1);
    wrapper.unmount();
  });
});
