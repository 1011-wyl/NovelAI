import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import AppSidebar from "./AppSidebar.vue";
import { useAppStore } from "@/stores/app.store";
import { useProjectsStore } from "@/stores/projects.store";
import { RouteNames } from "@/router/route-names";

vi.mock("lucide-vue-next", () => ({
  BookOpen: { template: "<span />" },
  LayoutDashboard: { template: "<span />" },
  Library: { template: "<span />" },
  MemoryStick: { template: "<span />" },
  PanelLeftClose: { template: "<span />" },
  Settings: { template: "<span />" },
  PenLine: { template: "<span />" },
}));

async function mountSidebar(path = "/novels") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/novels", name: RouteNames.Library, component: { template: "<div />" } },
      {
        path: "/novels/:projectId/workbench",
        name: RouteNames.Workbench,
        component: { template: "<div />" },
      },
      {
        path: "/novels/:projectId/reader",
        name: RouteNames.Reader,
        component: { template: "<div />" },
      },
      {
        path: "/novels/:projectId/memory",
        name: RouteNames.Memory,
        component: { template: "<div />" },
      },
      { path: "/analytics", name: RouteNames.Analytics, component: { template: "<div />" } },
      { path: "/settings", name: RouteNames.Settings, component: { template: "<div />" } },
    ],
  });
  await router.push(path);
  await router.isReady();
  return mount(AppSidebar, {
    global: {
      plugins: [createPinia(), router],
      stubs: { RouterLink: { template: "<a><slot /></a>", props: ["to"] } },
    },
  });
}

describe("AppSidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("pins 系统设置 to the bottom of the sidebar", async () => {
    const wrapper = await mountSidebar();
    const links = wrapper.findAll(".nav-link");
    expect(links.at(-1)!.text()).toContain("系统设置");
    expect(wrapper.find(".sidebar__footer .nav-link").text()).toContain("系统设置");
    expect(wrapper.find(".sidebar__primary").text()).not.toContain("系统设置");
  });

  it("persists desktop collapsed state in localStorage", async () => {
    const wrapper = await mountSidebar();
    const app = useAppStore();
    expect(wrapper.find(".sidebar").classes()).not.toContain("is-collapsed");
    expect(wrapper.find(".sidebar-collapse").exists()).toBe(true);
    await wrapper.find(".sidebar-collapse").trigger("click");
    await wrapper.vm.$nextTick();
    expect(app.sidebarCollapsed).toBe(true);
    expect(localStorage.getItem("novelAgentSidebarCollapsed")).toBe("1");
    expect(wrapper.find(".sidebar").classes()).toContain("is-collapsed");
    expect(wrapper.find(".sidebar-collapse").exists()).toBe(false);
    await wrapper.find(".brand-toggle").trigger("click");
    await wrapper.vm.$nextTick();
    expect(app.sidebarCollapsed).toBe(false);
    expect(wrapper.find(".sidebar").classes()).not.toContain("is-collapsed");
    expect(wrapper.find(".sidebar-collapse").exists()).toBe(true);
  });

  it("redirects unconfirmed project reader/memory clicks to workbench", async () => {
    const wrapper = await mountSidebar("/novels/p1/workbench");
    const projects = useProjectsStore();
    projects.items = [
      {
        id: "p1",
        title: "未确认",
        status: "DRAFT",
        confirmed: false,
        audience_channel: "男频",
        genre: "玄幻",
        chapter_count: 0,
        content_chars: 0,
        current_chapter: 0,
        created_at: "",
        updated_at: "",
      },
    ];
    projects.selectedProjectId = "p1";
    await wrapper.vm.$nextTick();

    const reader = wrapper
      .findAll("a")
      .find((node) => node.text().includes("作品阅读"));
    expect(reader).toBeTruthy();
    await reader!.trigger("click");
    expect(projects.notice).toContain("确认创作方案");
  });
});
