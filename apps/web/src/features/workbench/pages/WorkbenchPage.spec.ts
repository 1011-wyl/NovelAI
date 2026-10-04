import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { nextTick, ref } from "vue";
import WorkbenchPage from "./WorkbenchPage.vue";
import { RouteNames } from "@/router/route-names";
import type { ProjectDetail } from "@/api/contracts";

const latestSnapshot = ref<{
  id: string;
  rollback_allowed: boolean;
  blocked_reason?: string | null;
} | null>(null);
const loadLatest = vi.fn();
const repairReset = vi.fn();
const undoRepair = vi.fn();

vi.mock("@/features/workbench/store/opening-repair.store", () => ({
  useOpeningRepairStore: () => ({
    get latest() {
      return latestSnapshot.value;
    },
    loadError: null,
    get canRollback() {
      return Boolean(latestSnapshot.value?.rollback_allowed);
    },
    loadLatest,
    reset: repairReset,
    undo: undoRepair,
  }),
}));
const loading = ref(false);
const error = ref<string | null>(null);
const createdBanner = ref(true);
const detail = ref<ProjectDetail | null>(null);
const briefVersions = ref([]);
const pipelineEvents = ref([]);
const confirm = vi.fn();
const redoBrief = vi.fn();
const loadDetail = vi.fn();
const reset = vi.fn();
const acting = ref(false);

vi.mock("@/features/workbench/store/workbench.store", () => ({
  useWorkbenchStore: () => ({
    get detail() {
      return detail.value;
    },
    get project() {
      return detail.value?.project ?? null;
    },
    get chapters() {
      return detail.value?.chapters ?? [];
    },
    get loading() {
      return loading.value;
    },
    get error() {
      return error.value;
    },
    get acting() {
      return acting.value;
    },
    get createdBanner() {
      return createdBanner.value;
    },
    get editableDraft() {
      const current = detail.value;
      return Boolean(
        current &&
          current.project.status === "DRAFT" &&
          !current.project.confirmed &&
          current.chapters.length === 0
      );
    },
    get statusLabel() {
      return detail.value?.project.confirmed ? "自动连载可用" : "等待方案确认";
    },
    get todayCount() {
      return 0;
    },
    get readyCount() {
      return 0;
    },
    get healthLabel() {
      return "正常";
    },
    get chapterFailures() {
      return detail.value?.chapter_failures ?? [];
    },
    get generateLabel() {
      return (detail.value?.chapter_failures || []).some((item) => item.chapter_number === 1)
        ? "重新生成第 1 章"
        : "生成下一章";
    },
    inspectOpeningRepair: vi.fn(),
    confirmOpeningRepair: vi.fn(),
    undoOpeningRepair: vi.fn(),
    briefVersions,
    pipelineEvents,
    loadDetail,
    confirm,
    redoBrief,
    recover: vi.fn(),
    generate: vi.fn(),
    togglePause: vi.fn(),
    rework: vi.fn(),
    acceptWithWarnings: vi.fn(),
    saveBrief: vi.fn(),
    restoreVersion: vi.fn(),
    setCreatedBanner: vi.fn(),
    reset,
  }),
}));

vi.mock("@/features/story-brief/components/BriefWorkbench.vue", () => ({
  default: {
    name: "BriefWorkbench",
    props: ["brief", "versions", "acting"],
    template: '<div data-testid="brief-workbench">方案审阅</div>',
  },
}));

vi.mock("@/features/story-brief/components/BriefDisplay.vue", () => ({
  default: { name: "BriefDisplay", template: "<div />" },
}));

vi.mock("@/features/library/components/DeleteNovelDialog.vue", () => ({
  default: { name: "DeleteNovelDialog", template: "<div />" },
}));

function draftDetail(confirmed = false): ProjectDetail {
  return {
    project: {
      id: "p1",
      title: "测试小说",
      status: confirmed ? "ACTIVE" : "DRAFT",
      confirmed,
      created_at: "2026-10-01T00:00:00",
      updated_at: "2026-10-01T00:00:00",
      current_chapter: 0,
      request: {
        audience_channel: "男频",
        genre: "玄幻",
        preferred_title: null,
        experiences: [],
        elements: [],
        protagonist_tags: [],
        romance: null,
        idea: "一个测试想法",
        must_have: [],
        nice_to_have: [],
        exclude: [],
        chapter_target_chars: 2200,
        daily_chapters: 2,
        reserve_target: 5,
        require_plan_confirmation: true,
      },
      brief: {
        selected_title: "测试小说",
        synopsis: "简介",
        target_readers: "",
        protagonist: "主角",
        protagonist_name: "主角",
        protagonist_profile: "",
        supporting_cast: [],
        main_conflict: "",
        reader_contract: "",
        core_expectation: "",
        selling_points: [],
        world_rules: [],
        opening_three_chapters: [],
        style_guide: [],
        total_chapters: 100,
        volume_count: 1,
        update_plan: "",
        title_candidates: [],
      },
    },
    chapters: [],
    reserve_count: 0,
    latest_events: [],
  };
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/novels", name: RouteNames.Library, component: { template: "<div />" } },
      {
        path: "/novels/:projectId/workbench",
        name: RouteNames.Workbench,
        component: WorkbenchPage,
      },
      {
        path: "/novels/:projectId/reader",
        name: RouteNames.Reader,
        component: { template: "<div />" },
      },
    ],
  });
  await router.push("/novels/p1/workbench");
  await router.isReady();
  const pinia = createPinia();
  setActivePinia(pinia);
  return mount(WorkbenchPage, {
    global: {
      plugins: [pinia, router],
      stubs: {
        ProjectShell: { template: "<div><slot /></div>" },
        BaseDialog: { template: "<div><slot /></div>", props: ["open", "title"] },
        RouterLink: { template: "<a><slot /></a>", props: ["to"] },
      },
    },
  });
}

describe("WorkbenchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    detail.value = draftDetail(false);
    loading.value = false;
    error.value = null;
    createdBanner.value = true;
    acting.value = false;
    latestSnapshot.value = null;
  });

  it("shows only plan review UI before confirmation", async () => {
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("确认创作方案");
    expect(wrapper.text()).toContain("方案审阅");
    expect(wrapper.text()).not.toContain("今日完成");
    expect(wrapper.text()).not.toContain("章节生产流程");
    expect(wrapper.text()).not.toContain("生成下一章");
  });

  it("shows production UI immediately after confirm succeeds", async () => {
    const wrapper = await mountPage();
    expect(wrapper.text()).toContain("确认创作方案");
    detail.value = draftDetail(true);
    createdBanner.value = false;
    await nextTick();
    await flushPromises();
    expect(wrapper.text()).toContain("今日完成");
    expect(wrapper.text()).toContain("章节生产流程");
    expect(wrapper.text()).toContain("生成下一章");
    expect(wrapper.text()).not.toContain("确认创作方案");
  });

  it("shows rollback from latest snapshot after refresh and clears after undo", async () => {
    detail.value = draftDetail(true);
    createdBanner.value = false;
    latestSnapshot.value = { id: "repair_1", rollback_allowed: true };
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("回退开篇修复");
    latestSnapshot.value = null;
    await nextTick();
    expect(wrapper.text()).not.toContain("回退开篇修复");
  });

  it("keeps chapter reserve rows compact and hides verbose failure details", async () => {
    const active = draftDetail(true);
    active.chapters = [
      {
        id: "c2",
        project_id: "p1",
        number: 2,
        title: "完美的缺陷",
        status: "FAILED",
        version: 3,
        content: "草稿",
        created_at: "2026-10-04T00:00:00",
        updated_at: "2026-10-04T00:00:00",
      },
    ];
    active.chapter_failures = [
      {
        chapter_number: 2,
        score: null,
        selected_score: null,
        preflight_only: true,
        quality_status: "LENGTH_NEEDS_ATTENTION",
        actual_length: 1363,
        accepted_length_min: 1980,
        accepted_length_max: 2420,
      },
    ];
    detail.value = active;
    createdBanner.value = false;

    const wrapper = await mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("字数不足");
    expect(wrapper.text()).toContain("当前 1363 字，至少需要 1980 字");
    expect(wrapper.text()).toContain("处理");
    expect(wrapper.find(".failure-details").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("最终采用：0.0 分");
  });
});

