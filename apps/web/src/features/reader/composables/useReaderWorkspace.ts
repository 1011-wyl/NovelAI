import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
  type Ref,
} from "vue";
import type { ChapterRecord, ProjectDetail } from "@/api/contracts";
import { toUserError } from "@/stores/projects.store";
import { useAppStore } from "@/stores/app.store";
import {
  acceptWithWarnings,
  approveChange,
  commitRevision,
  createAssistantSession,
  discardEditDraft,
  getChapterWorkspace,
  listAssistantChanges,
  listAssistantMessages,
  rejectChange,
  restoreVersion,
  rollbackSession,
  saveEditDraft,
  sendAssistantMessage,
  submitFailedReview,
  type AssistantChangeSet,
  type AssistantMessage,
  type AssistantMode,
  type ChapterSelectionPayload,
  type ChapterVersionSnapshot,
  type ChapterWorkspace,
  type QuickAction,
} from "../api/reader.api";
import { countChapterChars, countNonWhitespaceChars } from "../utils/chapter-count";

export const STORAGE_KEYS = {
  assistantOpen: "novelAgentWsAssistantOpen",
  lastChapter: "novelAgentWsLastChapter",
} as const;

export const QUICK_LABELS: Record<QuickAction, string> = {
  polish: "润色",
  shorten: "精简",
  expand: "扩写",
  visualize: "增强画面",
  dialogue: "调整对白",
};

export type ChapterFilter = "all" | "READY" | "other";
export type SaveState = "clean" | "dirty" | "saving" | "saved" | "error" | "conflict";

export type SelectionRange = {
  start: number;
  end: number;
  text: string;
};

export type DiffLineView = {
  type: string;
  mark: string;
  text: string;
};

export type DialogState =
  | { kind: "closed" }
  | {
      kind: "confirm";
      title: string;
      paragraphs: string[];
      confirmLabel: string;
      cancelLabel: string | null;
      danger?: boolean;
      focusCancel?: boolean;
      resolve: (ok: boolean) => void;
    }
  | {
      kind: "versions";
      title: string;
      versions: ChapterVersionSnapshot[];
      resolve: (ok: boolean) => void;
    };

const SAVE_LABELS: Record<SaveState, string> = {
  clean: "已保存",
  dirty: "有未保存修改",
  saving: "保存中",
  saved: "已保存",
  error: "保存失败，点击重试",
  conflict: "正文已发生冲突",
};

function normalizeNewlines(text: string) {
  return String(text ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function toCodePointOffset(text: string, utf16Offset: number) {
  return Array.from(text.slice(0, utf16Offset)).length;
}

export function useReaderWorkspace(options: {
  projectId: Ref<string>;
  projectDetail: Ref<ProjectDetail | null>;
  initialChapter: Ref<number | null>;
  onProjectReload?: () => Promise<void>;
}) {
  const app = useAppStore();

  const rootRef = ref<HTMLElement | null>(null);
  const titleRef = ref<HTMLInputElement | null>(null);
  const contentRef = ref<HTMLTextAreaElement | null>(null);
  const messagesRef = ref<HTMLElement | null>(null);
  const assistantInputRef = ref<HTMLTextAreaElement | null>(null);
  const selectionBarRef = ref<HTMLElement | null>(null);
  const confirmBtnRef = ref<HTMLButtonElement | null>(null);
  const cancelBtnRef = ref<HTMLButtonElement | null>(null);

  const chapterNumber = ref<number | null>(null);
  const workspace = shallowRef<ChapterWorkspace | null>(null);
  const filter = ref<ChapterFilter>("all");
  const mode = ref<AssistantMode>("editor");
  const sessionId = ref<string | null>(null);
  const messages = ref<AssistantMessage[]>([]);
  const changes = ref<AssistantChangeSet[]>([]);
  const saveState = ref<SaveState>("clean");
  const saveStatusOverride = ref<string | null>(null);
  const title = ref("");
  const content = ref("");
  const assistantInput = ref("");
  const selection = ref<SelectionRange | null>(null);
  const pendingRef = ref<ChapterSelectionPayload | null>(null);
  const refChipText = ref("");
  const chaptersOpen = ref(false);
  const assistantOpen = ref(true);
  const workspaceError = ref<string | null>(null);
  const recoveryBannerRef = ref<{ focus?: () => void } | null>(null);
  const focusedFailedKey = ref("");
  const showChapter = ref(false);
  const aiBusy = ref(false);
  const committing = ref(false);
  const dialog = ref<DialogState>({ kind: "closed" });
  const selectionMenu = ref<{
    visible: boolean;
    left: number;
    top: number;
    charCount: number;
  }>({ visible: false, left: 0, top: 0, charCount: 0 });

  let saveTimer: ReturnType<typeof setTimeout> | null = null;
  let saving = false;
  let saveAgain = false;
  let destroyed = false;

  const saveStatusLabel = computed(
    () => saveStatusOverride.value || SAVE_LABELS[saveState.value] || saveState.value
  );

  const chapterLabel = computed(() => {
    const chapter = workspace.value?.chapter;
    if (!chapter) return "未选择章节";
    return `第 ${chapter.number} 章 · v${chapter.version}`;
  });

  const chapterCharCount = computed(() => countChapterChars(content.value));
  const wordCountLabel = computed(() => `正文 ${chapterCharCount.value} 字`);
  const selectedCountLabel = computed(() =>
    selection.value ? `已选 ${countNonWhitespaceChars(selection.value.text)} 字` : ""
  );

  const DENIED_CAPABILITIES = {
    edit_draft: false,
    use_assistant: false,
    commit_revision: false,
    submit_for_review: false,
    replan: false,
    accept_with_warnings: false,
  };

  const capabilitiesMissing = computed(
    () => Boolean(workspace.value) && workspace.value?.capabilities == null
  );

  const capabilities = computed(() => {
    const fromApi = workspace.value?.capabilities;
    if (fromApi) return fromApi;
    return { ...DENIED_CAPABILITIES };
  });
  const canUseAssistant = computed(() => Boolean(capabilities.value.use_assistant));
  const currentFailure = computed(() => {
    const number = chapterNumber.value;
    if (!number) return null;
    return (
      options.projectDetail.value?.chapter_failures?.find(
        (item) => item.chapter_number === number
      ) ?? null
    );
  });
  const editable = computed(() => Boolean(capabilities.value.edit_draft));
  const hasDraft = computed(() => Boolean(workspace.value?.draft));
  const commitDisabled = computed(
    () => !capabilities.value.commit_revision || !hasDraft.value || committing.value
  );
  const submitDisabled = computed(
    () => !capabilities.value.submit_for_review || !hasDraft.value || committing.value
  );
  const acceptDisabled = computed(
    () => !capabilities.value.accept_with_warnings || committing.value || capabilitiesMissing.value
  );
  const discardDisabled = computed(() => !hasDraft.value);
  const editorDisabled = computed(() => !workspace.value || !capabilities.value.edit_draft);
  const contentReadOnly = computed(
    () => !editable.value || aiBusy.value || committing.value
  );

  const filteredChapters = computed(() => {
    const chapters = options.projectDetail.value?.chapters || [];
    return chapters
      .filter((chapter) => {
        if (filter.value === "READY") return chapter.status === "READY";
        if (filter.value === "other") return chapter.status !== "READY";
        return true;
      })
      .slice()
      .sort((a, b) => a.number - b.number);
  });

  const chapterCountLabel = computed(
    () => `${options.projectDetail.value?.chapters?.length || 0} 章`
  );

  const changeByMessage = computed(() => {
    const map = new Map<string, AssistantChangeSet>();
    for (const change of changes.value) {
      map.set(change.message_id, change);
    }
    return map;
  });

  function isChapterDirty(number: number) {
    if (workspace.value?.draft && chapterNumber.value === number) return true;
    if (
      number === chapterNumber.value &&
      saveState.value !== "clean" &&
      saveState.value !== "saved"
    ) {
      return true;
    }
    return false;
  }

  function diffLines(change: AssistantChangeSet): DiffLineView[] {
    const lines: DiffLineView[] = [];
    for (const section of change.diff_json?.sections || []) {
      for (const line of section.lines || []) {
        const mark = line.type === "added" ? "+" : line.type === "removed" ? "-" : " ";
        lines.push({ type: line.type, mark, text: line.text });
      }
    }
    return lines;
  }

  function setSaveStatus(next: SaveState, override?: string | null) {
    saveState.value = next;
    saveStatusOverride.value = override ?? null;
  }

  function notify(message: string, isError = false) {
    app.flash(message, isError);
  }

  function lastChapterKey(projectId: string) {
    return `${STORAGE_KEYS.lastChapter}:${projectId}`;
  }

  function restoreWorkspacePreferences() {
    const stored = localStorage.getItem(STORAGE_KEYS.assistantOpen);
    if (stored === "0") assistantOpen.value = false;
    if (stored === "1") assistantOpen.value = true;
  }

  function resetEditor() {
    chapterNumber.value = null;
    workspace.value = null;
    sessionId.value = null;
    messages.value = [];
    changes.value = [];
    selection.value = null;
    pendingRef.value = null;
    refChipText.value = "";
    title.value = "";
    content.value = "";
    showChapter.value = false;
    hideSelectionMenu();
    setSaveStatus("clean");
  }

  function applyWorkspace() {
    const ws = workspace.value;
    if (!ws) return;
    const draft = ws.draft;
    const chapter = ws.chapter;
    title.value = draft?.title || chapter.title || "";
    content.value = draft?.content || chapter.content || "";
    setSaveStatus(draft ? "saved" : "clean");
    if (capabilitiesMissing.value) {
      workspaceError.value = "服务器未返回工作区能力，请刷新或升级后端";
    }
    if (!ws.editable && ws.read_only_reason) {
      notify(ws.read_only_reason, true);
    }
    maybeFocusFailedBanner(false);
  }

  function maybeFocusFailedBanner(force: boolean) {
    const chapter = workspace.value?.chapter;
    if (!chapter || chapter.status !== "FAILED") {
      focusedFailedKey.value = "";
      return;
    }
    const key = `${chapter.id}:${chapter.version}`;
    if (!force && focusedFailedKey.value === key) return;
    focusedFailedKey.value = key;
    void nextTick(() => recoveryBannerRef.value?.focus?.());
  }

  async function openChapter(chapter: ChapterRecord | undefined | null) {
    if (!options.projectId.value || !chapter) return;
    const ok = await flushSave();
    if (!ok) {
      notify("当前草稿保存失败，请先处理后再切换章节。", true);
      return;
    }
    chapterNumber.value = chapter.number;
    localStorage.setItem(lastChapterKey(options.projectId.value), String(chapter.number));
    showChapter.value = true;
    chaptersOpen.value = false;
    workspaceError.value = null;
    try {
      workspace.value = await getChapterWorkspace(options.projectId.value, chapter.number);
      applyWorkspace();
      if (capabilities.value.use_assistant) {
        await ensureSession();
        await refreshMessages();
      }
    } catch (error) {
      workspaceError.value = toUserError(error);
      notify(toUserError(error), true);
    }
  }

  function pickPreferredChapter(detail: ProjectDetail, preferredNumber: number | null) {
    const chapters = detail.chapters || [];
    if (preferredNumber != null) {
      const fromQuery = chapters.find((c) => c.number === preferredNumber);
      if (fromQuery) return fromQuery;
    }
    const last = Number(localStorage.getItem(lastChapterKey(detail.project.id)) || 0);
    return (
      chapters.find((c) => c.number === last) ||
      chapters.find((c) => c.status === "FAILED") ||
      chapters.find((c) => c.status === "READY") ||
      chapters[0] ||
      null
    );
  }

  async function bootstrapProject(detail: ProjectDetail | null, preferredNumber: number | null) {
    await flushSave();
    resetEditor();
    if (!detail) return;
    const preferred = pickPreferredChapter(detail, preferredNumber);
    if (preferred) await openChapter(preferred);
  }

  function onEditorInput() {
    if (!capabilities.value.edit_draft) return;
    setSaveStatus("dirty");
    scheduleSave();
  }

  function scheduleSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => void flushSave(), 800);
  }

  async function flushSave(): Promise<boolean> {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    if (!options.projectId.value || !chapterNumber.value || !workspace.value?.editable) {
      return true;
    }
    if (saveState.value === "clean" || saveState.value === "saved") return true;
    if (saving) {
      saveAgain = true;
      return false;
    }
    const nextTitle = title.value.trim();
    const nextContent = normalizeNewlines(content.value);
    if (!nextTitle || !nextContent.trim()) {
      notify("标题和正文不能为空。", true);
      return false;
    }
    saving = true;
    setSaveStatus("saving");
    const expected = workspace.value.draft?.content_hash || null;
    try {
      const draft = await saveEditDraft(options.projectId.value, chapterNumber.value, {
        base_version: workspace.value.chapter.version,
        title: nextTitle,
        content: nextContent,
        expected_draft_hash: expected,
      });
      workspace.value = { ...workspace.value, draft };
      setSaveStatus("saved");
      return true;
    } catch (error) {
      const message = toUserError(error);
      if (
        message.includes("冲突") ||
        message.includes("EDIT_CONFLICT") ||
        message.includes("已变更") ||
        message.includes("已更新")
      ) {
        setSaveStatus("conflict");
      } else {
        setSaveStatus("error");
      }
      notify(message, true);
      return false;
    } finally {
      saving = false;
      if (saveAgain) {
        saveAgain = false;
        if (saveState.value === "dirty") void flushSave();
      }
    }
  }

  function captureSelection(): SelectionRange | null {
    const el = contentRef.value;
    if (!el || el.readOnly) return null;
    const start16 = el.selectionStart || 0;
    const end16 = el.selectionEnd || 0;
    if (end16 <= start16) return null;
    const value = normalizeNewlines(el.value);
    const start = toCodePointOffset(value, start16);
    const end = toCodePointOffset(value, end16);
    const text = Array.from(value).slice(start, end).join("");
    if (!text.trim()) return null;
    return { start, end, text };
  }

  function onSelectionChange() {
    selection.value = captureSelection();
    if (!selection.value) hideSelectionMenu();
  }

  function hideSelectionMenu() {
    selectionMenu.value = { visible: false, left: 0, top: 0, charCount: 0 };
  }

  function showSelectionMenu(clientX: number, clientY: number) {
    if (!selection.value) return;
    const n = countNonWhitespaceChars(selection.value.text);
    selectionMenu.value = {
      visible: true,
      left: clientX + 4,
      top: clientY + 4,
      charCount: n,
    };
    void nextTick(() => {
      const bar = selectionBarRef.value;
      if (!bar) return;
      const pad = 8;
      const rect = bar.getBoundingClientRect();
      let left = clientX + 4;
      let top = clientY + 4;
      if (left + rect.width > window.innerWidth - pad) {
        left = Math.max(pad, window.innerWidth - rect.width - pad);
      }
      if (top + rect.height > window.innerHeight - pad) {
        top = Math.max(pad, clientY - rect.height - 4);
      }
      if (left < pad) left = pad;
      if (top < pad) top = pad;
      selectionMenu.value = { ...selectionMenu.value, left, top };
    });
  }

  function onContentContextMenu(event: MouseEvent) {
    selection.value = captureSelection();
    if (!selection.value) {
      hideSelectionMenu();
      return;
    }
    event.preventDefault();
    showSelectionMenu(event.clientX, event.clientY);
  }

  function onDocumentPointerDown(event: PointerEvent) {
    if (!selectionMenu.value.visible) return;
    const bar = selectionBarRef.value;
    if (bar && bar.contains(event.target as Node)) return;
    hideSelectionMenu();
  }

  async function handleQuick(action: QuickAction | "attach") {
    if (!selection.value) return;
    const ok = await flushSave();
    if (!ok) return;
    const draftHash = workspace.value?.draft?.content_hash;
    if (!draftHash) {
      notify("请先保存草稿后再使用选区操作。", true);
      return;
    }
    const payloadSelection: ChapterSelectionPayload = {
      start: selection.value.start,
      end: selection.value.end,
      text: selection.value.text,
      chapter_version: workspace.value!.chapter.version,
      draft_hash: draftHash,
    };
    if (action === "attach") {
      pendingRef.value = payloadSelection;
      const text = selection.value.text;
      refChipText.value = `引用：${text.slice(0, 48)}${text.length > 48 ? "…" : ""}`;
      assistantOpen.value = true;
      localStorage.setItem(STORAGE_KEYS.assistantOpen, "1");
      void nextTick(() => assistantInputRef.value?.focus());
      return;
    }
    mode.value = "editor";
    assistantOpen.value = true;
    localStorage.setItem(STORAGE_KEYS.assistantOpen, "1");
    await ensureSession();
    await sendAssistant({
      content: QUICK_LABELS[action] || action,
      mode: "editor",
      quick_action: action,
      selection: payloadSelection,
    });
  }

  async function ensureSession() {
    if (!capabilities.value.use_assistant) return;
    if (!options.projectId.value || !chapterNumber.value) return;
    if (sessionId.value) return;
    const sessions = workspace.value?.sessions || [];
    if (sessions.length) {
      sessionId.value = sessions[0].id;
      return;
    }
    const session = await createAssistantSession(options.projectId.value, chapterNumber.value);
    sessionId.value = session.id;
    if (workspace.value) {
      workspace.value = {
        ...workspace.value,
        sessions: [session, ...(workspace.value.sessions || [])],
      };
    }
  }

  async function createSession() {
    if (!options.projectId.value || !chapterNumber.value) return;
    if (!capabilities.value.use_assistant) return;
    try {
      const session = await createAssistantSession(options.projectId.value, chapterNumber.value);
      sessionId.value = session.id;
      messages.value = [];
      changes.value = [];
      notify("已新建 AI 会话。");
    } catch (error) {
      notify(toUserError(error), true);
    }
  }

  async function refreshMessages() {
    if (!sessionId.value) return;
    const [msgRes, changeRes] = await Promise.all([
      listAssistantMessages(sessionId.value),
      listAssistantChanges(sessionId.value),
    ]);
    messages.value = msgRes.items || [];
    changes.value = changeRes.items || [];
    await nextTick();
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }

  async function sendAssistant(override?: {
    content: string;
    mode?: AssistantMode | string;
    quick_action?: QuickAction | null;
    selection?: ChapterSelectionPayload | null;
  }) {
    if (aiBusy.value || !options.projectId.value || !chapterNumber.value) return;
    if (!capabilities.value.use_assistant) return;
    const ok = await flushSave();
    if (!ok) return;
    await ensureSession();
    if (!sessionId.value) return;
    const bodyContent = override?.content ?? assistantInput.value.trim();
    if (!bodyContent) return;
    const body = {
      content: bodyContent,
      mode: override?.mode || mode.value,
      quick_action: override?.quick_action || null,
      selection: override?.selection || pendingRef.value || null,
    };
    aiBusy.value = true;
    try {
      const result = await sendAssistantMessage(sessionId.value, body);
      if (!override) assistantInput.value = "";
      pendingRef.value = null;
      refChipText.value = "";
      messages.value = [...messages.value, result.user_message, result.assistant_message];
      if (result.change_set) changes.value = [...changes.value, result.change_set];
      await nextTick();
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
      }
    } catch (error) {
      notify(toUserError(error), true);
    } finally {
      aiBusy.value = false;
    }
  }

  async function decideChange(changeId: string, action: "approve" | "reject") {
    try {
      if (action === "approve") {
        const result = await approveChange(changeId);
        if (workspace.value) {
          workspace.value = { ...workspace.value, draft: result.draft };
        }
        title.value = result.draft.title;
        content.value = result.draft.content;
        setSaveStatus("saved");
        changes.value = changes.value.map((item) =>
          item.id === changeId ? result.change_set : item
        );
        notify("修改已写入工作草稿，尚未成为正式版本。");
      } else {
        const change = await rejectChange(changeId);
        changes.value = changes.value.map((item) => (item.id === changeId ? change : item));
      }
    } catch (error) {
      notify(toUserError(error), true);
    }
  }

  async function rollbackTo(messageId: string) {
    const ok = await flushSave();
    if (!ok || !workspace.value?.draft || !sessionId.value) return;
    try {
      const draft = await rollbackSession(sessionId.value, {
        to_message_id: messageId,
        expected_draft_hash: workspace.value.draft.content_hash,
      });
      workspace.value = { ...workspace.value, draft };
      title.value = draft.title;
      content.value = draft.content;
      setSaveStatus("saved");
      await refreshMessages();
      notify("已回滚会话修改到指定消息。");
    } catch (error) {
      notify(toUserError(error), true);
    }
  }

  async function discardDraft() {
    if (!workspace.value?.draft || !options.projectId.value || !chapterNumber.value) return;
    if (!window.confirm("确定放弃未提交的工作草稿？")) return;
    try {
      await discardEditDraft(options.projectId.value, chapterNumber.value);
      workspace.value = { ...workspace.value, draft: null };
      title.value = workspace.value.chapter.title;
      content.value = workspace.value.chapter.content || "";
      setSaveStatus("clean");
      notify("已放弃工作草稿。");
    } catch (error) {
      notify(toUserError(error), true);
    }
  }

  function openConfirmDialog(config: {
    title: string;
    paragraphs: string[];
    confirmLabel: string;
    cancelLabel: string | null;
    danger?: boolean;
    focusCancel?: boolean;
  }): Promise<boolean> {
    return new Promise((resolve) => {
      dialog.value = {
        kind: "confirm",
        ...config,
        resolve,
      };
      void nextTick(() => {
        const focusEl = config.focusCancel ? cancelBtnRef.value : confirmBtnRef.value;
        focusEl?.focus();
      });
    });
  }

  function closeDialog(result = false) {
    const current = dialog.value;
    dialog.value = { kind: "closed" };
    if (current.kind !== "closed") current.resolve(result);
  }

  async function showVersions() {
    if (!workspace.value) return;
    const versions = (workspace.value.versions || []).filter(
      (item) => item.is_official || item.kind === "RESET_ARCHIVE"
    );
    await new Promise<boolean>((resolve) => {
      dialog.value = {
        kind: "versions",
        title: "版本历史",
        versions,
        resolve,
      };
    });
  }

  async function restoreVersionAsDraft(version: number) {
    if (!options.projectId.value || !chapterNumber.value) return;
    try {
      const draft = await restoreVersion(options.projectId.value, chapterNumber.value, version);
      if (workspace.value) {
        workspace.value = { ...workspace.value, draft };
      }
      title.value = draft.title;
      content.value = draft.content;
      setSaveStatus("saved");
      closeDialog(true);
      notify(`已将 v${version} 恢复为工作草稿。`);
    } catch (error) {
      notify(toUserError(error), true);
    }
  }

  async function commitRevisionFlow() {
    if (committing.value || !workspace.value || !options.projectId.value || !chapterNumber.value) {
      return;
    }
    const ok = await flushSave();
    if (!ok || !workspace.value.draft) return;
    const downstream = workspace.value.downstream || { count: 0 };
    let proceed = true;
    if (downstream.count > 0) {
      proceed = await openConfirmDialog({
        title: "提交并重置后续章节",
        paragraphs: [
          `将重置第 ${downstream.first_number}–${downstream.last_number} 章，共 ${downstream.count} 章。`,
          "旧内容会保留在版本历史中，可恢复为工作草稿。当前章将写入新的正式版本。",
        ],
        confirmLabel: "提交并重置后续章节",
        cancelLabel: "取消",
        danger: true,
        focusCancel: true,
      });
    } else {
      proceed = await openConfirmDialog({
        title: "应用修订",
        paragraphs: [
          `来源：${workspace.value.draft.source}；将生成新正式版本 v${workspace.value.chapter.version + 1}。`,
        ],
        confirmLabel: "确认提交",
        cancelLabel: "取消",
      });
    }
    if (!proceed) return;

    if (!capabilities.value.commit_revision) return;
    committing.value = true;
    setSaveStatus("saving", "分析记忆并提交修订");
    app.setBusy(true, "分析记忆并提交修订");
    try {
      const result = await commitRevision(options.projectId.value, chapterNumber.value, {
        base_version: workspace.value.chapter.version,
        expected_draft_hash: workspace.value.draft.content_hash,
      });
      const resetCount = (result.reset_chapters || []).length;
      notify(
        `第 ${result.chapter.number} 章已更新为 v${result.chapter.version}${
          resetCount ? `，${resetCount} 个后续章节已安全重置` : ""
        }。`
      );
      if (options.onProjectReload) {
        await options.onProjectReload();
      }
      workspace.value = await getChapterWorkspace(options.projectId.value, chapterNumber.value);
      applyWorkspace();
    } catch (error) {
      notify(toUserError(error), true);
      setSaveStatus("error");
    } finally {
      committing.value = false;
      app.setBusy(false);
    }
  }

  async function submitFailedReviewFlow() {
    if (committing.value || !workspace.value || !options.projectId.value || !chapterNumber.value) {
      return;
    }
    if (!capabilities.value.submit_for_review || !workspace.value.draft) return;
    const ok = await flushSave();
    if (!ok || !workspace.value.draft) return;
    const proceed = await openConfirmDialog({
      title: "重新送审",
      paragraphs: [
        "将把当前工作草稿送入完整质量门，不会自动改写你已编辑的正文。",
        "通过后成为正式章节；未通过则继续保持未通过审核。",
      ],
      confirmLabel: "确认送审",
      cancelLabel: "取消",
    });
    if (!proceed) return;
    committing.value = true;
    setSaveStatus("saving", "正在重新送审");
    app.setBusy(true, "正在重新送审");
    let focusRecoveryAfterSubmit = false;
    try {
      const result = await submitFailedReview(options.projectId.value, chapterNumber.value, {
        base_version: workspace.value.chapter.version,
        expected_draft_hash: workspace.value.draft.content_hash,
      });
      notify(result.message || (result.passed ? "已通过审核" : "仍未通过审核，草稿已保留"));
      if (options.onProjectReload) await options.onProjectReload();
      workspace.value = await getChapterWorkspace(options.projectId.value, chapterNumber.value);
      applyWorkspace();
      focusRecoveryAfterSubmit = !result.passed;
    } catch (error) {
      workspaceError.value = toUserError(error);
      notify(toUserError(error), true);
      setSaveStatus("error");
    } finally {
      committing.value = false;
      app.setBusy(false);
      if (focusRecoveryAfterSubmit) {
        await nextTick();
        await new Promise<void>((resolve) => {
          window.setTimeout(resolve, 50);
        });
        recoveryBannerRef.value?.focus?.();
        const banner = document.querySelector<HTMLElement>(".recovery-banner");
        if (document.activeElement !== banner) {
          banner?.focus();
        }
      }
    }
  }

  async function acceptWithWarningsFlow() {
    if (committing.value || !workspace.value || !options.projectId.value || !chapterNumber.value) {
      return;
    }
    if (capabilitiesMissing.value || !capabilities.value.accept_with_warnings) return;
    const ok = await flushSave();
    if (!ok) return;
    const draftHash =
      workspace.value.draft?.content_hash ||
      (await getChapterWorkspace(options.projectId.value, chapterNumber.value)).draft?.content_hash;
    if (!draftHash && !workspace.value.chapter.content) return;
    const issues = (currentFailure.value?.issues || [])
      .map((item) => item.message || item.category || "")
      .filter(Boolean)
      .slice(0, 5);
    const proceed = await openConfirmDialog({
      title: "接受当前版本并继续",
      paragraphs: [
        "仅在没有硬阻断时可用。接受后，当前草稿会成为正式章节，并写入记忆。",
        issues.length ? `仍未解决：${issues.join("；")}` : "仍有软质量问题未解决。",
        "之后仍可在阅读页继续修订。",
      ],
      confirmLabel: "确认接受并继续",
      cancelLabel: "取消",
    });
    if (!proceed) return;
    committing.value = true;
    setSaveStatus("saving", "正在接受当前版本");
    app.setBusy(true, "正在接受当前版本");
    try {
      let expectedHash = workspace.value.draft?.content_hash;
      let baseVersion = workspace.value.chapter.version;
      if (!expectedHash) {
        const refreshed = await getChapterWorkspace(options.projectId.value, chapterNumber.value);
        workspace.value = refreshed;
        applyWorkspace();
        expectedHash = refreshed.draft?.content_hash;
        baseVersion = refreshed.chapter.version;
      }
      if (!expectedHash) {
        throw new Error("缺少可接受的草稿哈希");
      }
      const result = await acceptWithWarnings(options.projectId.value, chapterNumber.value, {
        confirm: true,
        base_version: baseVersion,
        expected_draft_hash: expectedHash,
      });
      notify(result.passed ? "已接受当前版本并继续" : "接受失败");
      if (options.onProjectReload) await options.onProjectReload();
      workspace.value = await getChapterWorkspace(options.projectId.value, chapterNumber.value);
      applyWorkspace();
    } catch (error) {
      workspaceError.value = toUserError(error);
      notify(toUserError(error), true);
      setSaveStatus("error");
      await nextTick();
      recoveryBannerRef.value?.focus?.();
    } finally {
      committing.value = false;
      app.setBusy(false);
    }
  }

  function openChaptersOverlay() {
    chaptersOpen.value = true;
  }

  function openAssistantOverlay() {
    assistantOpen.value = true;
    localStorage.setItem(STORAGE_KEYS.assistantOpen, "1");
  }

  function closeAssistantOverlay() {
    assistantOpen.value = false;
    localStorage.setItem(STORAGE_KEYS.assistantOpen, "0");
  }

  function onAssistantKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendAssistant();
    }
  }

  function onGlobalKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      if (dialog.value.kind !== "closed") {
        closeDialog(false);
        return;
      }
      hideSelectionMenu();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      if (!rootRef.value) return;
      event.preventDefault();
      void flushSave();
    }
  }

  function onVisibilityChange() {
    if (document.visibilityState === "hidden") void flushSave();
  }

  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (saveState.value === "dirty" || saveState.value === "saving") {
      event.preventDefault();
      event.returnValue = "";
    }
  }

  watch(
    () => [options.projectId.value, options.projectDetail.value?.project.id] as const,
    async ([projectId, detailId]) => {
      if (!projectId || destroyed) return;
      if (options.projectDetail.value && detailId === projectId) {
        await bootstrapProject(options.projectDetail.value, options.initialChapter.value);
      }
    }
  );

  watch(
    () => options.initialChapter.value,
    async (chapter) => {
      if (chapter == null || !options.projectDetail.value) return;
      if (chapterNumber.value === chapter) return;
      const found = options.projectDetail.value.chapters.find((c) => c.number === chapter);
      if (found) await openChapter(found);
    }
  );

  onMounted(() => {
    restoreWorkspacePreferences();
    document.addEventListener("pointerdown", onDocumentPointerDown, true);
    document.addEventListener("keydown", onGlobalKeydown);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("beforeunload", onBeforeUnload);
  });

  onUnmounted(() => {
    destroyed = true;
    if (saveTimer) clearTimeout(saveTimer);
    void flushSave();
    document.removeEventListener("pointerdown", onDocumentPointerDown, true);
    document.removeEventListener("keydown", onGlobalKeydown);
    document.removeEventListener("visibilitychange", onVisibilityChange);
    window.removeEventListener("beforeunload", onBeforeUnload);
  });

  return {
    rootRef,
    titleRef,
    contentRef,
    messagesRef,
    assistantInputRef,
    selectionBarRef,
    confirmBtnRef,
    cancelBtnRef,
    chapterNumber,
    workspace,
    filter,
    mode,
    messages,
    changes,
    saveState,
    saveStatusLabel,
    title,
    content,
    assistantInput,
    selection,
    pendingRef,
    refChipText,
    chaptersOpen,
    assistantOpen,
    workspaceError,
    recoveryBannerRef,
    capabilitiesMissing,
    showChapter,
    aiBusy,
    committing,
    dialog,
    selectionMenu,
    chapterLabel,
    chapterCharCount,
    wordCountLabel,
    selectedCountLabel,
    editable,
    hasDraft,
    capabilities,
    canUseAssistant,
    currentFailure,
    commitDisabled,
    submitDisabled,
    acceptDisabled,
    discardDisabled,
    editorDisabled,
    contentReadOnly,
    filteredChapters,
    chapterCountLabel,
    changeByMessage,
    QUICK_LABELS,
    isChapterDirty,
    diffLines,
    openChapter,
    bootstrapProject,
    onEditorInput,
    onSelectionChange,
    onContentContextMenu,
    hideSelectionMenu,
    handleQuick,
    flushSave,
    setSaveStatus,
    createSession,
    sendAssistant,
    decideChange,
    rollbackTo,
    discardDraft,
    showVersions,
    restoreVersionAsDraft,
    commitRevisionFlow,
    submitFailedReviewFlow,
    acceptWithWarningsFlow,
    openChaptersOverlay,
    openAssistantOverlay,
    closeAssistantOverlay,
    onAssistantKeydown,
    closeDialog,
    openConfirmDialog,
  };
}
