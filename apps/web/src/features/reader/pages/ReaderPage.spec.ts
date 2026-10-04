import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { computed, ref } from "vue";
import ReaderPage from "./ReaderPage.vue";
import { RouteNames } from "@/router/route-names";

const bootstrapProject = vi.fn().mockResolvedValue(undefined);
const sendAssistant = vi.fn();
const createSession = vi.fn();
const assistantInputRef = ref<HTMLTextAreaElement | null>(null);
const assistantOpen = ref(true);
const canUseAssistant = ref(true);
const submitForReview = ref(false);
const commitRevision = ref(true);
const workspaceError = ref<string | null>(null);
const currentFailure = ref<Record<string, unknown> | null>(null);
const chapterStatus = ref("READY");

vi.mock("../composables/useReaderWorkspace", () => ({
  QUICK_LABELS: {},
  useReaderWorkspace: () => ({
    rootRef: ref(null),
    titleRef: ref(null),
    contentRef: ref(null),
    messagesRef: ref(null),
    assistantInputRef,
    selectionBarRef: ref(null),
    confirmBtnRef: ref(null),
    cancelBtnRef: ref(null),
    chapterNumber: ref(1),
    filter: ref(""),
    mode: ref("editor"),
    messages: ref([]),
    saveState: ref("saved"),
    saveStatusLabel: computed(() => "已保存"),
    title: ref("第一章"),
    content: ref("正文内容"),
    assistantInput: ref(""),
    refChipText: ref(""),
    chaptersOpen: ref(false),
    assistantOpen,
    workspaceError,
    recoveryBannerRef: ref(null),
    capabilitiesMissing: computed(() => false),
    showChapter: ref(true),
    aiBusy: ref(false),
    dialog: ref({ kind: "closed" }),
    selectionMenu: ref({ visible: false, left: 0, top: 0, charCount: 0 }),
    chapterLabel: computed(() => "第 1 章"),
    wordCountLabel: computed(() => "4 字"),
    selectedCountLabel: computed(() => ""),
    discardDisabled: computed(() => false),
    commitDisabled: computed(() => !commitRevision.value),
    submitDisabled: computed(() => !submitForReview.value),
    acceptDisabled: computed(() => true),
    capabilities: computed(() => ({
      edit_draft: true,
      use_assistant: canUseAssistant.value,
      commit_revision: commitRevision.value,
      submit_for_review: submitForReview.value,
      replan: submitForReview.value,
      accept_with_warnings: false,
    })),
    canUseAssistant: computed(() => canUseAssistant.value),
    currentFailure,
    editorDisabled: computed(() => false),
    contentReadOnly: computed(() => false),
    filteredChapters: computed(() => [
      { number: 1, title: "第一章", status: chapterStatus.value, version: 1 },
    ]),
    chapterCountLabel: computed(() => "1 章"),
    changeByMessage: () => null,
    isChapterDirty: () => false,
    diffLines: computed(() => []),
    openChapter: vi.fn(),
    bootstrapProject,
    onEditorInput: vi.fn(),
    onSelectionChange: vi.fn(),
    onContentContextMenu: vi.fn(),
    hideSelectionMenu: vi.fn(),
    handleQuick: vi.fn(),
    flushSave: vi.fn(),
    createSession,
    sendAssistant,
    decideChange: vi.fn(),
    rollbackTo: vi.fn(),
    discardDraft: vi.fn(),
    showVersions: vi.fn(),
    restoreVersionAsDraft: vi.fn(),
    commitRevisionFlow: vi.fn(),
    submitFailedReviewFlow: vi.fn(),
    acceptWithWarningsFlow: vi.fn(),
    openChaptersOverlay: vi.fn(),
    openAssistantOverlay: vi.fn(),
    closeAssistantOverlay: vi.fn(),
    onAssistantKeydown: vi.fn(),
    closeDialog: vi.fn(),
    toggleChapters: vi.fn(),
    toggleAssistant: vi.fn(),
  }),
}));

vi.mock("@/features/workbench/store/workbench.store", () => ({
  useWorkbenchStore: () => ({
    detail: {
      project: { id: "p1", title: "测试", confirmed: true },
      chapters: [{ number: 1, title: "第一章", status: "READY", version: 1 }],
    },
    loading: false,
    loadDetail: vi.fn().mockResolvedValue(undefined),
  }),
}));

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/novels/:projectId/reader",
        name: RouteNames.Reader,
        component: ReaderPage,
      },
      {
        path: "/novels/:projectId/workbench",
        name: RouteNames.Workbench,
        component: { template: "<div />" },
      },
    ],
  });
  await router.push("/novels/p1/reader");
  await router.isReady();
  return mount(ReaderPage, {
    global: {
      plugins: [createPinia(), router],
      stubs: {
        ProjectShell: { template: "<div><slot /></div>" },
        BaseDialog: { template: '<div v-if="open"><slot /></div>', props: ["open", "title"] },
        LoadingBlock: { template: "<div />" },
      },
    },
    attachTo: document.body,
  });
}

describe("ReaderPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    assistantOpen.value = true;
    canUseAssistant.value = true;
    submitForReview.value = false;
    commitRevision.value = true;
    workspaceError.value = null;
    currentFailure.value = null;
    chapterStatus.value = "READY";
  });

  it("does not render workspace resizers and keeps assistant textarea non-resizable", async () => {
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.find(".workspace-resizer").exists()).toBe(false);
    expect(wrapper.find(".writing-workspace").exists()).toBe(true);
    wrapper.findAll("textarea").forEach((node) => {
      expect(node.attributes("style") || "").not.toContain("resize: both");
    });
    wrapper.unmount();
  });

  it("folds the desktop assistant column when closed", async () => {
    const wrapper = await mountPage();
    expect(wrapper.get("#readerView").classes()).not.toContain("assistant-closed");
    assistantOpen.value = false;
    await flushPromises();
    expect(wrapper.get("#readerView").classes()).toContain("assistant-closed");
    wrapper.unmount();
  });

  it("uses the same mode-chip style for workspace actions", async () => {
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.get('button[aria-label="新建会话"]').classes()).toContain("ws-mode");
    expect(wrapper.get('button[aria-label="关闭助手"]').classes()).toContain("ws-mode");
    expect(wrapper.get('button[aria-label="版本历史"]').classes()).toContain("ws-mode");
    expect(wrapper.get('button[aria-label="放弃草稿"]').classes()).toContain("ws-mode");
    expect(wrapper.get('button[aria-label="应用修订"]').classes()).toContain("ws-mode");
    wrapper.unmount();
  });

  it("disables assistant controls when capability is false", async () => {
    canUseAssistant.value = false;
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.get('button[aria-label="新建会话"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('button[aria-label="发送"]').attributes("disabled")).toBeDefined();
    await wrapper.get('button[aria-label="发送"]').trigger("click");
    expect(sendAssistant).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("shows resubmit instead of commit for FAILED chapters", async () => {
    submitForReview.value = true;
    commitRevision.value = false;
    chapterStatus.value = "FAILED";
    currentFailure.value = { chapter_number: 1, issues: [{ message: "字数偏短" }] };
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("重新送审");
    expect(wrapper.find('button[aria-label="应用修订"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("质量待修改");
    wrapper.unmount();
  });

  it("renders error summary with alert role", async () => {
    workspaceError.value = "工作区加载失败";
    const wrapper = await mountPage();
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("工作区加载失败");
    wrapper.unmount();
  });
});
