(() => {
  const STORAGE_KEYS = {
    left: "novelAgentWsLeft",
    right: "novelAgentWsRight",
    assistantOpen: "novelAgentWsAssistantOpen",
    lastChapter: "novelAgentWsLastChapter",
  };

  const QUICK_LABELS = {
    polish: "润色",
    shorten: "精简",
    expand: "扩写",
    visualize: "增强画面",
    dialogue: "调整对白",
  };

  const normalizeNewlines = (text) => String(text ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const toCodePointOffset = (text, utf16Offset) => Array.from(text.slice(0, utf16Offset)).length;
  const countChars = (text) => Array.from(normalizeNewlines(text)).length;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])
    );
  }

  const state = {
    api: null,
    notify: null,
    busy: null,
    projectId: null,
    projectDetail: null,
    chapterNumber: null,
    workspace: null,
    filter: "all",
    mode: "editor",
    sessionId: null,
    messages: [],
    changes: [],
    saveState: "clean",
    saveTimer: null,
    saving: false,
    saveAgain: false,
    selection: null,
    pendingRef: null,
    aiBusy: false,
    committing: false,
    destroyed: false,
  };

  let els = {};

  function init({ api, notify, busy }) {
    state.api = api;
    state.notify = notify;
    state.busy = busy;
    mountDom();
    if (!els.root) {
      console.warn("ReaderWorkspace: #readerView 不存在，跳过初始化");
      return;
    }
    bindEvents();
    restoreWidths();
    // If reader is already active (rare), ensure host exists for book picker.
    if (els.root.classList.contains("active") && typeof window.placeBookPicker === "function") {
      window.placeBookPicker("reader");
    }
  }

  function mountDom() {
    const root = document.getElementById("readerView");
    if (!root) {
      els = {};
      return;
    }
    root.className = "view writing-workspace";
    root.innerHTML = `
      <aside class="workspace-chapters" aria-label="章节列表">
        <div class="ws-panel-head ws-book-head">
          <div id="readerBookPickerHost" class="reader-book-picker-host"></div>
        </div>
        <div class="ws-chapter-filters" role="group" aria-label="章节筛选">
          <button type="button" class="ws-filter" data-filter="all" aria-pressed="true">全部</button>
          <button type="button" class="ws-filter" data-filter="READY" aria-pressed="false">READY</button>
          <button type="button" class="ws-filter" data-filter="other" aria-pressed="false">其他</button>
          <span id="wsChapterCount" class="ws-chapter-count">0 章</span>
        </div>
        <div id="wsChapterList" class="ws-chapter-list"><div class="empty">暂无章节</div></div>
      </aside>
      <div class="workspace-resizer" data-edge="left" role="separator" tabindex="0" aria-orientation="vertical" aria-label="调整章节栏宽度"></div>
      <main class="workspace-editor" aria-label="章节编辑区">
        <div class="ws-editor-toolbar">
          <button type="button" class="text-button ws-overlay-toggle" id="wsOpenChapters" aria-label="打开章节目录">目录</button>
          <strong id="wsChapterLabel">未选择章节</strong>
          <span id="wsSaveStatus" class="ws-status" role="status" aria-atomic="true">已保存</span>
          <span class="spacer"></span>
          <button type="button" class="text-button" id="wsVersionsBtn" aria-label="版本历史">版本</button>
          <button type="button" class="text-button" id="wsDiscardBtn" aria-label="放弃草稿">放弃草稿</button>
          <button type="button" class="primary-button" id="wsCommitBtn" aria-label="应用修订">应用修订</button>
          <button type="button" class="text-button ws-overlay-toggle" id="wsOpenAssistant" aria-label="打开 AI 助手">AI</button>
        </div>
        <div id="wsSelectionBar" class="ws-selection-bar" aria-live="polite"></div>
        <div class="ws-editor-body">
          <input id="wsTitleInput" type="text" maxlength="120" spellcheck="false" placeholder="章节标题" disabled />
          <textarea id="wsContentInput" spellcheck="false" placeholder="选择 READY 章节后开始阅读或修订。" disabled></textarea>
          <div class="ws-editor-footer">
            <span id="wsWordCount">0 字</span>
            <span id="wsSelectedCount"></span>
          </div>
        </div>
      </main>
      <div class="workspace-resizer" data-edge="right" role="separator" tabindex="0" aria-orientation="vertical" aria-label="调整 AI 栏宽度"></div>
      <aside class="workspace-assistant" aria-label="AI 修订助手">
        <div class="ws-panel-head">
          <div class="ws-assistant-modes" role="group" aria-label="助手模式">
            <button type="button" class="ws-mode" data-mode="advisor" aria-pressed="false">顾问</button>
            <button type="button" class="ws-mode" data-mode="coauthor" aria-pressed="false">共创</button>
            <button type="button" class="ws-mode" data-mode="editor" aria-pressed="true">编辑</button>
          </div>
          <div>
            <button type="button" class="text-button" id="wsNewSession" aria-label="新建会话">新建</button>
            <button type="button" class="text-button" id="wsCloseAssistant" aria-label="关闭助手">关闭</button>
          </div>
        </div>
        <div id="wsMessages" class="ws-messages"><div class="empty">向 AI 提问或请求改写。修改需批准后才会进入草稿。</div></div>
        <div class="ws-composer">
          <div id="wsRefChip" class="ws-ref-chip"></div>
          <textarea id="wsAssistantInput" placeholder="输入修订意见… Enter 发送，Shift+Enter 换行"></textarea>
          <div class="ws-composer-actions">
            <button type="button" class="primary-button" id="wsSendBtn">发送</button>
          </div>
        </div>
      </aside>
      <div id="wsDialogHost"></div>
    `;
    const q = (sel) => root.querySelector(sel);
    els = {
      root,
      chapterList: q("#wsChapterList"),
      chapterCount: q("#wsChapterCount"),
      title: q("#wsTitleInput"),
      content: q("#wsContentInput"),
      saveStatus: q("#wsSaveStatus"),
      chapterLabel: q("#wsChapterLabel"),
      wordCount: q("#wsWordCount"),
      selectedCount: q("#wsSelectedCount"),
      selectionBar: q("#wsSelectionBar"),
      messages: q("#wsMessages"),
      assistantInput: q("#wsAssistantInput"),
      refChip: q("#wsRefChip"),
      dialogHost: q("#wsDialogHost"),
      commitBtn: q("#wsCommitBtn"),
      discardBtn: q("#wsDiscardBtn"),
      versionsBtn: q("#wsVersionsBtn"),
      sendBtn: q("#wsSendBtn"),
    };
  }

  function $(selector) {
    if (!selector) return null;
    if (selector.startsWith("#") || selector.startsWith(".") || selector.includes(" ")) {
      return document.querySelector(selector);
    }
    return document.getElementById(selector);
  }

  function bindEvents() {
    if (!els.root) return;
    els.root.querySelectorAll(".ws-filter").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.filter = btn.dataset.filter;
        els.root.querySelectorAll(".ws-filter").forEach((b) =>
          b.setAttribute("aria-pressed", String(b === btn))
        );
        renderChapterList();
      });
    });
    els.root.querySelectorAll(".ws-mode").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.mode = btn.dataset.mode;
        els.root.querySelectorAll(".ws-mode").forEach((b) =>
          b.setAttribute("aria-pressed", String(b === btn))
        );
      });
    });
    els.title?.addEventListener("input", onEditorInput);
    els.content?.addEventListener("input", onEditorInput);
    els.content?.addEventListener("select", onSelectionChange);
    els.content?.addEventListener("keyup", onSelectionChange);
    els.content?.addEventListener("mouseup", onSelectionChange);
    els.commitBtn?.addEventListener("click", () => void commitRevision());
    els.discardBtn?.addEventListener("click", () => void discardDraft());
    els.versionsBtn?.addEventListener("click", () => void showVersions());
    els.sendBtn?.addEventListener("click", () => void sendAssistant());
    els.root.querySelector("#wsNewSession")?.addEventListener("click", () => void createSession());
    els.root.querySelector("#wsOpenChapters")?.addEventListener("click", () => els.root.classList.add("chapters-open"));
    els.root.querySelector("#wsOpenAssistant")?.addEventListener("click", () => {
      els.root.classList.add("assistant-open");
      localStorage.setItem(STORAGE_KEYS.assistantOpen, "1");
    });
    els.root.querySelector("#wsCloseAssistant")?.addEventListener("click", () => {
      els.root.classList.remove("assistant-open");
      localStorage.setItem(STORAGE_KEYS.assistantOpen, "0");
    });
    els.assistantInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void sendAssistant();
      }
    });
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        if (!els.root?.classList.contains("active")) return;
        event.preventDefault();
        void flushSave();
      }
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") void flushSave();
    });
    window.addEventListener("beforeunload", (event) => {
      if (state.saveState === "dirty" || state.saveState === "saving") {
        event.preventDefault();
        event.returnValue = "";
      }
    });
    bindResizers();
  }

  function bindResizers() {
    els.root.querySelectorAll(".workspace-resizer").forEach((handle) => {
      const edge = handle.dataset.edge;
      const onMove = (event) => {
        const rect = els.root.getBoundingClientRect();
        if (edge === "left") {
          const width = Math.min(340, Math.max(200, event.clientX - rect.left));
          els.root.style.setProperty("--ws-left", `${width}px`);
          localStorage.setItem(STORAGE_KEYS.left, String(width));
        } else {
          const width = Math.min(480, Math.max(320, rect.right - event.clientX));
          els.root.style.setProperty("--ws-right", `${width}px`);
          localStorage.setItem(STORAGE_KEYS.right, String(width));
        }
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
      });
      handle.addEventListener("keydown", (event) => {
        const delta = event.key === "ArrowLeft" ? -16 : event.key === "ArrowRight" ? 16 : 0;
        if (!delta) return;
        event.preventDefault();
        const prop = edge === "left" ? "--ws-left" : "--ws-right";
        const key = edge === "left" ? STORAGE_KEYS.left : STORAGE_KEYS.right;
        const current = parseInt(getComputedStyle(els.root).getPropertyValue(prop), 10) || (edge === "left" ? 240 : 360);
        const next =
          edge === "left"
            ? Math.min(340, Math.max(200, current + delta))
            : Math.min(480, Math.max(320, current - delta));
        els.root.style.setProperty(prop, `${next}px`);
        localStorage.setItem(key, String(next));
      });
    });
  }

  function restoreWidths() {
    const left = localStorage.getItem(STORAGE_KEYS.left);
    const right = localStorage.getItem(STORAGE_KEYS.right);
    if (left) els.root.style.setProperty("--ws-left", `${left}px`);
    if (right) els.root.style.setProperty("--ws-right", `${right}px`);
    if (localStorage.getItem(STORAGE_KEYS.assistantOpen) === "1") {
      els.root.classList.add("assistant-open");
    }
  }

  function setProject(detail) {
    if (!els.root) return;
    void flushSave();
    state.projectDetail = detail;
    state.projectId = detail?.project?.id || null;
    state.chapterNumber = null;
    state.workspace = null;
    state.sessionId = null;
    state.messages = [];
    state.changes = [];
    state.selection = null;
    state.pendingRef = null;
    renderChapterList();
    resetEditor();
    const last = Number(localStorage.getItem(`${STORAGE_KEYS.lastChapter}:${state.projectId}`) || 0);
    const chapters = detail?.chapters || [];
    const preferred = chapters.find((c) => c.number === last) || chapters.find((c) => c.status === "READY");
    if (preferred) void openChapter(preferred);
  }

  function resetEditor() {
    if (!els.chapterLabel) return;
    els.chapterLabel.textContent = "未选择章节";
    if (els.title) {
      els.title.value = "";
      els.title.disabled = true;
    }
    if (els.content) {
      els.content.value = "";
      els.content.disabled = true;
    }
    if (els.messages) {
      els.messages.innerHTML = '<div class="empty">向 AI 提问或请求改写。修改需批准后才会进入草稿。</div>';
    }
    setSaveStatus("clean");
    updateCounts();
  }

  async function openChapter(chapter) {
    if (!state.projectId || !chapter) return;
    const ok = await flushSave();
    if (!ok) {
      state.notify?.("当前草稿保存失败，请先处理后再切换章节。", true);
      return;
    }
    state.chapterNumber = chapter.number;
    localStorage.setItem(`${STORAGE_KEYS.lastChapter}:${state.projectId}`, String(chapter.number));
    els.root.classList.add("show-chapter");
    els.root.classList.remove("chapters-open");
    try {
      state.workspace = await state.api(
        `/api/novels/${state.projectId}/chapters/${chapter.number}/workspace`
      );
      applyWorkspace();
      await ensureSession();
      await refreshMessages();
    } catch (error) {
      state.notify?.(error.message, true);
    }
  }

  function applyWorkspace() {
    const ws = state.workspace;
    if (!ws) return;
    const draft = ws.draft;
    const chapter = ws.chapter;
    els.chapterLabel.textContent = `第 ${chapter.number} 章 · v${chapter.version}`;
    els.title.value = draft?.title || chapter.title || "";
    els.content.value = draft?.content || chapter.content || "";
    const editable = Boolean(ws.editable);
    els.title.readOnly = !editable;
    els.content.readOnly = !editable;
    els.title.disabled = false;
    els.content.disabled = false;
    els.commitBtn.disabled = !editable || !draft;
    els.discardBtn.disabled = !draft;
    setSaveStatus(draft ? "saved" : "clean");
    updateCounts();
    renderChapterList();
    if (!editable && ws.read_only_reason) {
      state.notify?.(ws.read_only_reason, true);
    }
  }

  function renderChapterList() {
    if (!els.chapterList || !els.chapterCount) return;
    const chapters = state.projectDetail?.chapters || [];
    els.chapterCount.textContent = `${chapters.length} 章`;
    const filtered = chapters.filter((chapter) => {
      if (state.filter === "READY") return chapter.status === "READY";
      if (state.filter === "other") return chapter.status !== "READY";
      return true;
    });
    if (!filtered.length) {
      els.chapterList.innerHTML = '<div class="empty">暂无章节</div>';
      return;
    }
    const draftNumbers = new Set();
    if (state.workspace?.draft && state.chapterNumber) draftNumbers.add(state.chapterNumber);
    els.chapterList.innerHTML = filtered
      .slice()
      .sort((a, b) => a.number - b.number)
      .map((chapter) => {
        const dirty = draftNumbers.has(chapter.number) || (chapter.number === state.chapterNumber && state.saveState !== "clean" && state.saveState !== "saved");
        return `<button type="button" class="ws-chapter-item" data-number="${chapter.number}" ${
          chapter.number === state.chapterNumber ? 'aria-current="page"' : ""
        }><b>${escapeHtml(chapter.title)}</b><span class="meta"><span>${chapter.status}</span><span>v${chapter.version}</span>${
          dirty ? '<span class="ws-dot" title="未提交"></span>' : ""
        }</span></button>`;
      })
      .join("");
    els.chapterList.querySelectorAll(".ws-chapter-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        const chapter = chapters.find((item) => item.number === Number(btn.dataset.number));
        void openChapter(chapter);
      });
    });
  }

  function onEditorInput() {
    if (!state.workspace?.editable) return;
    setSaveStatus("dirty");
    updateCounts();
    scheduleSave();
    renderChapterList();
  }

  function scheduleSave() {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => void flushSave(), 800);
  }

  function setSaveStatus(next) {
    state.saveState = next;
    if (!els.saveStatus) return;
    const labels = {
      clean: "已保存",
      dirty: "有未保存修改",
      saving: "保存中",
      saved: "已保存",
      error: "保存失败，点击重试",
      conflict: "正文已发生冲突",
    };
    els.saveStatus.textContent = labels[next] || next;
    els.saveStatus.className = `ws-status ${next === "error" || next === "conflict" ? next : ""}`;
    if (next === "error" || next === "conflict") {
      els.saveStatus.onclick = () => void flushSave();
    } else {
      els.saveStatus.onclick = null;
    }
  }

  async function flushSave() {
    clearTimeout(state.saveTimer);
    if (!state.projectId || !state.chapterNumber || !state.workspace?.editable) return true;
    if (state.saveState === "clean" || state.saveState === "saved") return true;
    if (state.saving) {
      state.saveAgain = true;
      return false;
    }
    const title = (els.title?.value || "").trim();
    const content = normalizeNewlines(els.content?.value || "");
    if (!title || !content.trim()) {
      state.notify?.("标题和正文不能为空。", true);
      return false;
    }
    state.saving = true;
    setSaveStatus("saving");
    const expected = state.workspace.draft?.content_hash || null;
    try {
      const draft = await state.api(
        `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/edit-draft`,
        {
          method: "PUT",
          body: JSON.stringify({
            base_version: state.workspace.chapter.version,
            title,
            content,
            expected_draft_hash: expected,
          }),
        }
      );
      state.workspace.draft = draft;
      if (els.commitBtn) els.commitBtn.disabled = false;
      if (els.discardBtn) els.discardBtn.disabled = false;
      setSaveStatus("saved");
      renderChapterList();
      return true;
    } catch (error) {
      const message = String(error.message || "");
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
      state.notify?.(message, true);
      return false;
    } finally {
      state.saving = false;
      if (state.saveAgain) {
        state.saveAgain = false;
        if (state.saveState === "dirty") void flushSave();
      }
    }
  }

  function updateCounts() {
    if (!els.wordCount) return;
    const total = countChars(els.content?.value || "");
    els.wordCount.textContent = `${total} 字`;
    if (els.selectedCount) {
      els.selectedCount.textContent = state.selection
        ? `已选 ${countChars(state.selection.text)} 字`
        : "";
    }
  }

  function onSelectionChange() {
    if (els.content.readOnly) {
      state.selection = null;
      renderSelectionBar();
      return;
    }
    const start16 = els.content.selectionStart || 0;
    const end16 = els.content.selectionEnd || 0;
    if (end16 <= start16) {
      state.selection = null;
      renderSelectionBar();
      updateCounts();
      return;
    }
    const value = normalizeNewlines(els.content.value);
    const start = toCodePointOffset(value, start16);
    const end = toCodePointOffset(value, end16);
    const text = Array.from(value).slice(start, end).join("");
    if (!text.trim()) {
      state.selection = null;
      renderSelectionBar();
      updateCounts();
      return;
    }
    state.selection = { start, end, text };
    renderSelectionBar();
    updateCounts();
  }

  function renderSelectionBar() {
    if (!state.selection) {
      els.selectionBar.classList.remove("visible");
      els.selectionBar.innerHTML = "";
      return;
    }
    const n = countChars(state.selection.text);
    els.selectionBar.classList.add("visible");
    els.selectionBar.innerHTML = `
      <span>已选择 ${n} 字</span>
      ${Object.entries(QUICK_LABELS)
        .map(([key, label]) => `<button type="button" class="text-button" data-quick="${key}">${label}</button>`)
        .join("")}
      <button type="button" class="text-button" data-quick="attach">加入对话</button>
    `;
    els.selectionBar.querySelectorAll("[data-quick]").forEach((btn) => {
      btn.addEventListener("click", () => void handleQuick(btn.dataset.quick));
    });
  }

  async function handleQuick(action) {
    if (!state.selection) return;
    const ok = await flushSave();
    if (!ok) return;
    const draftHash = state.workspace?.draft?.content_hash;
    if (!draftHash) {
      state.notify?.("请先保存草稿后再使用选区操作。", true);
      return;
    }
    const payloadSelection = {
      start: state.selection.start,
      end: state.selection.end,
      text: state.selection.text,
      chapter_version: state.workspace.chapter.version,
      draft_hash: draftHash,
    };
    if (action === "attach") {
      state.pendingRef = payloadSelection;
      els.refChip.textContent = `引用：${state.selection.text.slice(0, 48)}${state.selection.text.length > 48 ? "…" : ""}`;
      els.refChip.classList.add("visible");
      els.root.classList.add("assistant-open");
      els.assistantInput.focus();
      return;
    }
    state.mode = "editor";
    els.root.querySelectorAll(".ws-mode").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.mode === "editor"))
    );
    els.root.classList.add("assistant-open");
    await ensureSession();
    await sendAssistant({
      content: QUICK_LABELS[action] || action,
      mode: "editor",
      quick_action: action,
      selection: payloadSelection,
    });
  }

  async function ensureSession() {
    if (!state.projectId || !state.chapterNumber) return;
    if (state.sessionId) return;
    const sessions = state.workspace?.sessions || [];
    if (sessions.length) {
      state.sessionId = sessions[0].id;
      return;
    }
    const session = await state.api(
      `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/assistant/sessions`,
      { method: "POST", body: "{}" }
    );
    state.sessionId = session.id;
    state.workspace.sessions = [session, ...(state.workspace.sessions || [])];
  }

  async function createSession() {
    if (!state.projectId || !state.chapterNumber) return;
    try {
      const session = await state.api(
        `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/assistant/sessions`,
        { method: "POST", body: "{}" }
      );
      state.sessionId = session.id;
      state.messages = [];
      state.changes = [];
      renderMessages();
      state.notify?.("已新建 AI 会话。");
    } catch (error) {
      state.notify?.(error.message, true);
    }
  }

  async function refreshMessages() {
    if (!state.sessionId) return;
    const [messages, changes] = await Promise.all([
      state.api(`/api/assistant/sessions/${state.sessionId}/messages`),
      state.api(`/api/assistant/sessions/${state.sessionId}/changes`),
    ]);
    state.messages = messages.items || [];
    state.changes = changes.items || [];
    renderMessages();
  }

  function renderMessages() {
    if (!state.messages.length) {
      els.messages.innerHTML = '<div class="empty">向 AI 提问或请求改写。修改需批准后才会进入草稿。</div>';
      return;
    }
    const changeByMessage = new Map(
      state.changes.map((change) => [change.message_id, change])
    );
    els.messages.innerHTML = state.messages
      .map((msg) => {
        const change = changeByMessage.get(msg.id);
        let extra = "";
        if (msg.selection?.text) {
          extra += `<div class="ws-ref-chip visible">引用：${escapeHtml(msg.selection.text.slice(0, 80))}</div>`;
        }
        if (change) {
          extra += renderChangeCard(change);
        }
        const rollback =
          msg.role === "user"
            ? `<div><button type="button" class="text-button" data-rollback="${msg.id}">回滚到这里</button></div>`
            : "";
        return `<article class="ws-msg ${msg.role}" data-msg="${msg.id}">
          <div class="role">${msg.role === "user" ? "你" : "AI"} · ${escapeHtml(msg.mode)}</div>
          <div>${escapeHtml(msg.content)}</div>
          ${extra}${rollback}
        </article>`;
      })
      .join("");
    els.messages.querySelectorAll("[data-approve]").forEach((btn) =>
      btn.addEventListener("click", () => void decideChange(btn.dataset.approve, "approve"))
    );
    els.messages.querySelectorAll("[data-reject]").forEach((btn) =>
      btn.addEventListener("click", () => void decideChange(btn.dataset.reject, "reject"))
    );
    els.messages.querySelectorAll("[data-rollback]").forEach((btn) =>
      btn.addEventListener("click", () => void rollbackTo(btn.dataset.rollback))
    );
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function renderChangeCard(change) {
    const lines = [];
    for (const section of change.diff_json?.sections || []) {
      for (const line of section.lines || []) {
        const mark = line.type === "added" ? "+" : line.type === "removed" ? "-" : " ";
        lines.push(
          `<div class="ws-diff-line ${escapeHtml(line.type)}">${mark} ${escapeHtml(line.text)}</div>`
        );
      }
    }
    const actions =
      change.status === "PENDING"
        ? `<div class="ws-change-actions">
            <button type="button" class="primary-button" data-approve="${change.id}">批准写入草稿</button>
            <button type="button" class="text-button" data-reject="${change.id}">拒绝</button>
          </div>`
        : `<div class="meta">${escapeHtml(change.status)}</div>`;
    return `<div class="ws-change-card">
      <div>${escapeHtml(change.explanation || "待批准修改")}</div>
      <div class="ws-diff">${lines.join("") || "<div class='ws-diff-line context'>（无可见差异）</div>"}</div>
      ${actions}
    </div>`;
  }

  async function sendAssistant(override) {
    if (state.aiBusy || !state.projectId || !state.chapterNumber) return;
    const ok = await flushSave();
    if (!ok) return;
    await ensureSession();
    const content = override?.content ?? els.assistantInput.value.trim();
    if (!content) return;
    const body = {
      content,
      mode: override?.mode || state.mode,
      quick_action: override?.quick_action || null,
      selection: override?.selection || state.pendingRef || null,
    };
    state.aiBusy = true;
    els.sendBtn.disabled = true;
    els.content.readOnly = true;
    try {
      const result = await state.api(`/api/assistant/sessions/${state.sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!override) els.assistantInput.value = "";
      state.pendingRef = null;
      els.refChip.classList.remove("visible");
      state.messages.push(result.user_message, result.assistant_message);
      if (result.change_set) state.changes.push(result.change_set);
      renderMessages();
    } catch (error) {
      state.notify?.(error.message, true);
    } finally {
      state.aiBusy = false;
      els.sendBtn.disabled = false;
      els.content.readOnly = !state.workspace?.editable;
    }
  }

  async function decideChange(changeId, action) {
    try {
      if (action === "approve") {
        const result = await state.api(`/api/assistant/changes/${changeId}/approve`, {
          method: "POST",
          body: "{}",
        });
        state.workspace.draft = result.draft;
        els.title.value = result.draft.title;
        els.content.value = result.draft.content;
        els.commitBtn.disabled = false;
        els.discardBtn.disabled = false;
        setSaveStatus("saved");
        state.changes = state.changes.map((item) =>
          item.id === changeId ? result.change_set : item
        );
        state.notify?.("修改已写入工作草稿，尚未成为正式版本。");
      } else {
        const change = await state.api(`/api/assistant/changes/${changeId}/reject`, {
          method: "POST",
          body: "{}",
        });
        state.changes = state.changes.map((item) => (item.id === changeId ? change : item));
      }
      renderMessages();
      renderChapterList();
      updateCounts();
    } catch (error) {
      state.notify?.(error.message, true);
    }
  }

  async function rollbackTo(messageId) {
    const ok = await flushSave();
    if (!ok || !state.workspace?.draft) return;
    try {
      const draft = await state.api(`/api/assistant/sessions/${state.sessionId}/rollback`, {
        method: "POST",
        body: JSON.stringify({
          to_message_id: messageId,
          expected_draft_hash: state.workspace.draft.content_hash,
        }),
      });
      state.workspace.draft = draft;
      els.title.value = draft.title;
      els.content.value = draft.content;
      setSaveStatus("saved");
      await refreshMessages();
      state.notify?.("已回滚会话修改到指定消息。");
    } catch (error) {
      state.notify?.(error.message, true);
    }
  }

  async function discardDraft() {
    if (!state.workspace?.draft) return;
    if (!window.confirm("确定放弃未提交的工作草稿？")) return;
    try {
      await state.api(
        `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/edit-draft`,
        { method: "DELETE", body: "{}" }
      );
      state.workspace.draft = null;
      els.title.value = state.workspace.chapter.title;
      els.content.value = state.workspace.chapter.content || "";
      els.commitBtn.disabled = true;
      els.discardBtn.disabled = true;
      setSaveStatus("clean");
      renderChapterList();
      updateCounts();
      state.notify?.("已放弃工作草稿。");
    } catch (error) {
      state.notify?.(error.message, true);
    }
  }

  async function showVersions() {
    if (!state.workspace) return;
    const versions = (state.workspace.versions || []).filter(
      (item) => item.is_official || item.kind === "RESET_ARCHIVE"
    );
    const body = versions.length
      ? versions
          .map(
            (item) =>
              `<div style="display:flex;justify-content:space-between;gap:8px;margin:8px 0">
                <span>v${item.version} · ${escapeHtml(item.kind)} · ${escapeHtml(item.title || "")}</span>
                <button type="button" class="text-button" data-restore="${item.version}">恢复为草稿</button>
              </div>`
          )
          .join("")
      : "<p>暂无正式版本记录。</p>";
    const confirmed = await openDialog({
      title: "版本历史",
      body,
      confirmLabel: "关闭",
      cancelLabel: null,
      bind: (dialog) => {
        dialog.querySelectorAll("[data-restore]").forEach((btn) => {
          btn.addEventListener("click", async () => {
            try {
              const draft = await state.api(
                `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/versions/${btn.dataset.restore}/restore`,
                { method: "POST", body: "{}" }
              );
              state.workspace.draft = draft;
              els.title.value = draft.title;
              els.content.value = draft.content;
              els.commitBtn.disabled = false;
              els.discardBtn.disabled = false;
              setSaveStatus("saved");
              closeDialog();
              state.notify?.(`已将 v${btn.dataset.restore} 恢复为工作草稿。`);
            } catch (error) {
              state.notify?.(error.message, true);
            }
          });
        });
      },
    });
    void confirmed;
  }

  async function commitRevision() {
    if (state.committing) return;
    const ok = await flushSave();
    if (!ok || !state.workspace?.draft) return;
    const downstream = state.workspace.downstream || { count: 0 };
    let proceed = true;
    if (downstream.count > 0) {
      proceed = await openDialog({
        title: "提交并重置后续章节",
        body: `<p>将重置第 ${downstream.first_number}–${downstream.last_number} 章，共 ${downstream.count} 章。</p>
               <p>旧内容会保留在版本历史中，可恢复为工作草稿。当前章将写入新的正式版本。</p>`,
        confirmLabel: "提交并重置后续章节",
        cancelLabel: "取消",
        danger: true,
        focusCancel: true,
      });
    } else {
      proceed = await openDialog({
        title: "应用修订",
        body: `<p>来源：${escapeHtml(state.workspace.draft.source)}；将生成新正式版本 v${
          state.workspace.chapter.version + 1
        }。</p>`,
        confirmLabel: "确认提交",
        cancelLabel: "取消",
      });
    }
    if (!proceed) return;
    state.committing = true;
    els.commitBtn.disabled = true;
    els.title.readOnly = true;
    els.content.readOnly = true;
    setSaveStatus("saving");
    els.saveStatus.textContent = "分析记忆并提交修订";
    try {
      const result = await state.api(
        `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/revisions`,
        {
          method: "POST",
          body: JSON.stringify({
            base_version: state.workspace.chapter.version,
            expected_draft_hash: state.workspace.draft.content_hash,
          }),
        }
      );
      const resetCount = (result.reset_chapters || []).length;
      state.notify?.(
        `第 ${result.chapter.number} 章已更新为 v${result.chapter.version}${
          resetCount ? `，${resetCount} 个后续章节已安全重置` : ""
        }。`
      );
      if (state.projectDetail) {
        await reloadProjectDetail();
      }
      state.workspace = await state.api(
        `/api/novels/${state.projectId}/chapters/${state.chapterNumber}/workspace`
      );
      applyWorkspace();
    } catch (error) {
      state.notify?.(error.message, true);
      setSaveStatus("error");
    } finally {
      state.committing = false;
      els.title.readOnly = !state.workspace?.editable;
      els.content.readOnly = !state.workspace?.editable;
      els.commitBtn.disabled = !state.workspace?.draft;
    }
  }

  async function reloadProjectDetail() {
    try {
      const detail = await state.api(`/api/novels/${state.projectId}`);
      state.projectDetail = detail;
      renderChapterList();
    } catch (_) {
      /* ignore */
    }
  }

  function openDialog({ title, body, confirmLabel, cancelLabel, danger, focusCancel, bind }) {
    return new Promise((resolve) => {
      const host = els.dialogHost;
      host.innerHTML = `<div class="ws-dialog-backdrop" role="presentation">
        <div class="ws-dialog" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
          <h4>${escapeHtml(title)}</h4>
          <div class="ws-dialog-body">${body}</div>
          <div class="ws-dialog-actions">
            ${cancelLabel ? `<button type="button" class="text-button" data-cancel>${escapeHtml(cancelLabel)}</button>` : ""}
            <button type="button" class="${danger ? "danger-button" : "primary-button"}" data-confirm>${escapeHtml(
              confirmLabel
            )}</button>
          </div>
        </div>
      </div>`;
      const dialog = host.querySelector(".ws-dialog");
      const finish = (value) => {
        host.innerHTML = "";
        document.removeEventListener("keydown", onKey);
        resolve(value);
      };
      const onKey = (event) => {
        if (event.key === "Escape") finish(false);
      };
      document.addEventListener("keydown", onKey);
      dialog.querySelector("[data-cancel]")?.addEventListener("click", () => finish(false));
      dialog.querySelector("[data-confirm]")?.addEventListener("click", () => finish(true));
      bind?.(dialog);
      const focusEl = focusCancel
        ? dialog.querySelector("[data-cancel]")
        : dialog.querySelector("[data-confirm]");
      focusEl?.focus();
    });
  }

  function closeDialog() {
    els.dialogHost.innerHTML = "";
  }

  function destroy() {
    state.destroyed = true;
    clearTimeout(state.saveTimer);
  }

  window.ReaderWorkspace = {
    init,
    setProject,
    openChapter,
    destroy,
  };
})();
