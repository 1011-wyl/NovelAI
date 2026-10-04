import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import SettingsPage from "./SettingsPage.vue";
import { RouteNames } from "@/router/route-names";

const getSettings = vi.fn();
const saveSettings = vi.fn();

vi.mock("../api/settings.api", () => ({
  getSettings: () => getSettings(),
  saveSettings: (payload: unknown) => saveSettings(payload),
}));

vi.mock("../llm/components/LlmSettingsDrawer.vue", () => ({
  default: {
    props: ["open"],
    emits: ["close", "saved"],
    template: '<div v-if="open" data-testid="llm-drawer">drawer</div>',
  },
}));

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/settings", name: RouteNames.Settings, component: { template: "<div />" } }],
  });
  await router.push("/settings");
  await router.isReady();
  return mount(SettingsPage, {
    global: {
      plugins: [createPinia(), router],
      stubs: {
        AppShell: { template: "<div><slot /></div>" },
      },
    },
  });
}

describe("SettingsPage LLM card", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    getSettings.mockResolvedValue({
      preferences: { daily_chapters: 2, reserve_target: 5, budget_limit: 0, debug_mode: false },
      runtime: {
        llm: { card_status: "unconfigured", configured: false, enabled: false },
        search: { configured: false, enabled: false },
      },
    });
  });

  it("opens the LLM drawer with mouse and keyboard", async () => {
    const wrapper = await mountPage();
    await flushPromises();
    const card = wrapper.get('button[aria-label="配置大模型，当前未配置"]');
    expect(card.text()).toContain("点击配置模型服务");
    await card.trigger("click");
    expect(wrapper.get('[data-testid="llm-drawer"]').exists()).toBe(true);
    await wrapper.get('[data-testid="llm-drawer"]').trigger("close");
    await card.trigger("keydown.enter");
    expect(wrapper.get('[data-testid="llm-drawer"]').exists()).toBe(true);
    await card.trigger("keydown.space");
    expect(wrapper.get('[data-testid="llm-drawer"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("renders enabled / pending / attention / disabled card states", async () => {
    const cases = [
      { card_status: "enabled", label: "已启用", extra: "阿里云百炼 DashScope · qwen-plus" },
      { card_status: "unverified", label: "待验证", extra: "qwen-plus" },
      { card_status: "needs_attention", label: "需要处理", extra: "qwen-plus" },
      { card_status: "disabled", label: "已停用", extra: "qwen-plus" },
    ];
    for (const item of cases) {
      getSettings.mockResolvedValue({
        preferences: {},
        runtime: {
          llm: {
            card_status: item.card_status,
            provider: "dashscope",
            provider_label: "阿里云百炼 DashScope",
            model: "qwen-plus",
            configured: true,
            enabled: item.card_status === "enabled",
          },
        },
      });
      const wrapper = await mountPage();
      await flushPromises();
      expect(wrapper.text()).toContain(item.label);
      expect(wrapper.text()).toContain(item.extra);
      wrapper.unmount();
    }
  });
});
