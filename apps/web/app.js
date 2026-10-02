const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const labels = {
  dashboard: "创作控制台",
  create: "创建小说",
  reader: "作品阅读",
  memory: "长期记忆",
  analytics: "仪表盘",
  settings: "系统设置",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]
  );
}

function notify(message, error = false) {
  const flash = $("#flash");
  flash.textContent = message;
  flash.className = `flash${error ? " error" : ""}`;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => flash.classList.add("hidden"), 5000);
}

function busy(show) {
  $("#busy").classList.toggle("hidden", !show);
}

const shellState = {
  health: null,
  lastEvents: [],
  characterArchive: [],
  selectedCharacterId: null,
};

let api = null;
let projectsState = null;
let projectsApi = null;
let projectsController = null;
let novelCreateView = null;
let storyBriefView = null;
let projectDashboardView = null;
let analyticsView = null;
let PROJECT_STORAGE_KEY = "novelAgentProject";

function switchView(view) {
  const previous = $$(".nav-item.active")[0]?.dataset.view;
  if (previous === "analytics" && view !== "analytics") analyticsView?.deactivate();
  if (previous === "create" && view !== "create") novelCreateView?.deactivate();
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((item) => item.classList.remove("active"));
  const target = $(`#${view}View`);
  if (!target) {
    console.error(`找不到视图：${view}View`);
    window.__novelBasicSwitchView?.(view);
    return;
  }
  target.classList.add("active");
  if ($("#pageTitle")) $("#pageTitle").textContent = labels[view] || view;
  if (view !== "reader") $("#readerView")?.classList.remove("show-chapter");
  $("#busy")?.classList.add("hidden");
  placeBookPicker(view === "reader" ? "reader" : "topbar");
  if (view === "analytics") analyticsView?.activate();
  if (view === "create") novelCreateView?.activate();
  if (view === "settings") loadSettings();
}
window.switchView = switchView;
window.placeBookPicker = placeBookPicker;

function placeBookPicker(target) {
  const picker = $("#bookPicker");
  const refreshButton = $("#refreshButton");
  const topActions = document.querySelector(".top-actions");
  const readerHost = $("#readerBookPickerHost");
  if (!picker || !topActions) return;
  closeBookPicker();
  if (target === "reader" && readerHost) {
    readerHost.appendChild(picker);
    if (refreshButton) readerHost.appendChild(refreshButton);
  } else {
    const select = $("#projectSelect");
    if (select && select.parentElement !== topActions) topActions.prepend(select);
    topActions.appendChild(picker);
    if (refreshButton) topActions.appendChild(refreshButton);
  }
}

function applySidebarCollapsed(collapsed) {
  const shell = $("#appShell");
  const toggle = $("#sidebarToggle");
  if (!shell || !toggle) return;
  shell.classList.toggle("sidebar-collapsed", collapsed);
  toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  toggle.setAttribute("aria-label", collapsed ? "展开侧栏" : "折叠侧栏");
  toggle.title = collapsed ? "展开侧栏" : "折叠侧栏";
  localStorage.setItem("novelAgentSidebarCollapsed", collapsed ? "1" : "0");
}

function setConnectionStatus(kind) {
  const dot = $("#connectionDot");
  if (!dot) return;
  dot.classList.remove("is-offline", "is-error");
  if (kind === "offline") dot.classList.add("is-offline");
  if (kind === "error") dot.classList.add("is-error");
}

function showReaderToc() {
  $("#readerView")?.classList.remove("show-chapter");
}

function selectedProjectId() {
  return projectsState?.selectedId || null;
}

function selectedDetail() {
  return projectsState?.detail || null;
}

async function refresh() {
  try {
    const [health, projectsPayload] = await Promise.all([
      api("/api/health"),
      projectsApi.listProjects(),
    ]);
    shellState.health = health;
    $("#runtimeMode").textContent = health.mode === "offline" ? "离线安全模式" : "在线模式";
    const enabledApis = Object.entries(health.apis)
      .filter(([, item]) => item.enabled)
      .map(([name]) => name.toUpperCase());
    $("#apiHint").textContent = enabledApis.length
      ? `${enabledApis.join(" · ")} 已启用`
      : "外部 API 未启用";
    setConnectionStatus(health.mode === "offline" ? "offline" : "online");
    projectsController.setProjectsAndSelect(projectsPayload.items);
    renderProjectSelect();
    await projectsController.loadSelected();
  } catch (error) {
    if (error.stale) return;
    $("#runtimeMode").textContent = "服务未连接";
    $("#apiHint").textContent = "请启动本地 API";
    setConnectionStatus("error");
    notify(error.message, true);
  }
}

function renderProjectSelect() {
  const select = $("#projectSelect");
  if (!select || !projectsState) return;
  const { projects, selectedId } = projectsState.getSnapshot();
  select.innerHTML = projects.length
    ? projects
        .map(
          (p) =>
            `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${escapeHtml(p.title)}</option>`
        )
        .join("")
    : '<option value="">尚无项目</option>';
  renderBookPicker();
}

function renderBookPicker() {
  const label = $("#bookPickerLabel");
  const grid = $("#bookPickerGrid");
  if (!label || !grid || !projectsState) return;
  const { projects, selectedId } = projectsState.getSnapshot();
  const selected = projects.find((p) => p.id === selectedId);
  label.textContent = selected?.title || (projects.length ? "选择小说" : "尚无项目");
  if (!projects.length) {
    grid.innerHTML = '<div class="book-picker-empty">暂无小说项目</div>';
    return;
  }
  const coverIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 5.5C4 4.67 4.67 4 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5v-13Z"/><path d="M20 5.5c0-.83-.67-1.5-1.5-1.5H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5v-13Z"/></svg>`;
  grid.innerHTML = projects
    .map(
      (project) => `
    <button type="button" class="book-picker-card" role="option" data-project-id="${escapeHtml(project.id)}" aria-selected="${project.id === selectedId ? "true" : "false"}">
      <span class="book-picker-cover">${coverIcon}</span>
      <span class="book-picker-title">${escapeHtml(project.title)}</span>
    </button>
  `
    )
    .join("");
  grid.querySelectorAll(".book-picker-card").forEach((card) => {
    card.addEventListener("click", async () => {
      const projectId = card.dataset.projectId;
      closeBookPicker();
      if (!projectId || projectId === projectsState.selectedId) return;
      const select = $("#projectSelect");
      if (select) select.value = projectId;
      await projectsController.selectProject(projectId);
      renderBookPicker();
    });
  });
}

function openBookPicker() {
  const menu = $("#bookPickerMenu");
  const trigger = $("#bookPickerTrigger");
  if (!menu || !trigger) return;
  renderBookPicker();
  menu.classList.remove("hidden");
  trigger.setAttribute("aria-expanded", "true");
}

function closeBookPicker() {
  const menu = $("#bookPickerMenu");
  const trigger = $("#bookPickerTrigger");
  if (menu) menu.classList.add("hidden");
  if (trigger) trigger.setAttribute("aria-expanded", "false");
}

function toggleBookPicker() {
  const menu = $("#bookPickerMenu");
  if (!menu) return;
  if (menu.classList.contains("hidden")) openBookPicker();
  else closeBookPicker();
}

function wireNavigation() {
  const rememberedCollapse = localStorage.getItem("novelAgentSidebarCollapsed") === "1";
  applySidebarCollapsed(rememberedCollapse);
  $("#sidebarToggle")?.addEventListener("click", () => {
    applySidebarCollapsed(!$("#appShell").classList.contains("sidebar-collapsed"));
  });
  $$("[data-view-jump]").forEach((item) =>
    item.addEventListener("click", () => switchView(item.dataset.viewJump))
  );
  $("#refreshButton")?.addEventListener("click", refresh);
  $("#rebuildCharactersButton")?.addEventListener("click", rebuildCharacterArchives);
  $("#characterBackButton")?.addEventListener("click", showCharacterList);
  $("#projectSelect")?.addEventListener("change", async (event) => {
    await projectsController.selectProject(event.target.value || null);
    renderBookPicker();
  });
  $("#bookPickerTrigger")?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleBookPicker();
  });
  document.addEventListener("click", (event) => {
    const picker = $("#bookPicker");
    if (!picker) return;
    if (!picker.contains(event.target)) closeBookPicker();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeBookPicker();
  });
  $("#settingsForm")?.addEventListener("submit", saveSettings);
}

function renderChapters(chapters) {
  const rows = chapters.length
    ? chapters
        .slice()
        .reverse()
        .map((chapter) => chapterRow(chapter))
        .join("")
    : '<div class="empty">暂无章节</div>';
  $("#chapterQueue").innerHTML = rows;
  $$("#chapterQueue .chapter-row").forEach((row) =>
    row.addEventListener("click", () => {
      const chapter = chapters.find((item) => item.id === row.dataset.chapterId);
      switchView("reader");
      window.ReaderWorkspace?.openChapter(chapter);
    })
  );
  $$("#chapterQueue .chapter-rework-button").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const projectId = selectedProjectId();
      if (!projectId) return;
      const chapterNumber = parseInt(btn.dataset.chapterNumber, 10);
      const feedback = window.prompt(
        `打回第 ${chapterNumber} 章重做\n\n请输入修改意见（可选）：\n例如：主角对话太生硬，需要更自然；战斗场景太短，需要扩展。\n\n此操作将重置第 ${chapterNumber} 章及之后所有章节，不可撤销。`,
        ""
      );
      if (feedback === null) return;
      try {
        busy(true);
        await api(`/api/novels/${projectId}/chapters/${chapterNumber}/rework`, {
          method: "POST",
          body: JSON.stringify({ feedback: feedback.trim() }),
        });
        notify(
          feedback.trim()
            ? `第 ${chapterNumber} 章已打回重做，修改意见已记录。`
            : `第 ${chapterNumber} 章及后续章节已打回重做。`
        );
        await projectsController.loadSelected();
      } catch (error) {
        notify(error.message, true);
      } finally {
        busy(false);
      }
    });
  });
  window.ReaderWorkspace?.setProject(selectedDetail());
}

function chapterRow(chapter) {
  const statusClass =
    chapter.status === "READY"
      ? "status-ready"
      : chapter.status === "FAILED"
        ? "status-failed"
        : "";
  const reworkable = chapter.status !== "PLANNED";
  const reworkBtn = reworkable
    ? `<button class="chapter-rework-button text-button" data-chapter-number="${chapter.number}" title="打回重做">↩ 重做</button>`
    : "";
  return `<div class="chapter-row" data-chapter-id="${chapter.id}"><div><b>${escapeHtml(chapter.title)}</b><span>版本 ${chapter.version} · ${escapeHtml(chapter.summary || "等待生成")}</span></div><div class="chapter-row-actions"><span class="${statusClass}">${chapter.status}</span>${reworkBtn}</div></div>`;
}

const characterRoleLabels = {
  protagonist: "主角",
  supporting: "配角",
  ally: "盟友",
  rival: "竞争者",
  antagonist: "反派",
  mentor: "导师",
  family: "亲属",
  love_interest: "感情角色",
};
const characterStateLabels = {
  current_goal: "当前目标",
  last_result: "最近结果",
  goal: "长期目标",
  knowledge: "已知信息",
  trust: "信任度",
  location: "所在位置",
  condition: "身体状况",
  emotion: "情绪状态",
  inventory: "持有物资",
  relationship: "关系状态",
  relationships: "人物关系",
};
const characterStateOrder = [
  "current_goal",
  "last_result",
  "goal",
  "knowledge",
  "location",
  "condition",
  "emotion",
  "inventory",
  "relationship",
  "trust",
];

function characterStateLabel(key) {
  return characterStateLabels[key] || key.replaceAll("_", " ");
}

function formatCharacterValue(value) {
  if (Array.isArray(value)) return value.length ? value.map(formatCharacterValue).join("；") : "暂无记录";
  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length
      ? entries.map(([key, item]) => `${characterStateLabel(key)}：${formatCharacterValue(item)}`).join("；")
      : "暂无记录";
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (value === null || value === undefined || value === "") return "暂无记录";
  return String(value);
}

function characterFactParts(fact, characterName) {
  const text = String(fact || "").trim();
  if (!text || text === `主角姓名为${characterName}`) return null;
  if (text.startsWith("人物背景：")) return ["人物背景", text.slice(5)];
  if (text.startsWith("性格特征：")) return ["性格特征", text.slice(5)];
  if (text.startsWith("故事起点属于")) return ["故事起点", text.slice(6)];
  if (text.includes("无限资源") || text.includes("全知能力")) return ["能力边界", text];
  return ["固定设定", text];
}

function renderCharacterCard(item) {
  const currentState = item.current_state || {};
  const progressChapter = Number(currentState.last_seen_chapter ?? currentState.chapter ?? 0);
  const hasAppeared = progressChapter > 0;
  const progressText = hasAppeared ? `更新至第 ${progressChapter} 章` : "尚未正式出场";
  const roleText = characterRoleLabels[item.role] || "人物";
  const importanceText =
    currentState.importance === "core" || item.role === "protagonist" ? "核心人物" : "重要人物";
  const maxFacts = item.role === "protagonist" ? 6 : 3;
  const rawFacts = (item.immutable_facts || [])
    .map((fact) => characterFactParts(fact, item.name))
    .filter(Boolean);
  const facts = [];
  for (const f of rawFacts) {
    if (facts.length >= maxFacts) break;
    if (f[0] === "固定设定" && facts.some((existing) => existing[1] === f[1])) continue;
    facts.push(f);
  }
  const stateRows = hasAppeared
    ? Object.entries(currentState)
        .filter(([key]) => !["chapter", "last_seen_chapter", "importance"].includes(key))
        .filter(([, value]) => {
          if (value === null || value === undefined || value === "") return false;
          if (Array.isArray(value) && value.length === 0) return false;
          if (typeof value === "object" && Object.keys(value).length === 0) return false;
          return true;
        })
        .sort(([left], [right]) => {
          const leftIndex = characterStateOrder.indexOf(left);
          const rightIndex = characterStateOrder.indexOf(right);
          return (
            (leftIndex < 0 ? characterStateOrder.length : leftIndex) -
            (rightIndex < 0 ? characterStateOrder.length : rightIndex)
          );
        })
    : [];
  const factsHtml = facts.length
    ? facts
        .map(
          ([label, value]) =>
            `<div class="character-field"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`
        )
        .join("")
    : "";
  const stateHtml = stateRows.length
    ? stateRows
        .map(
          ([key, value]) =>
            `<div class="character-field"><dt>${escapeHtml(characterStateLabel(key))}</dt><dd>${escapeHtml(formatCharacterValue(value))}</dd></div>`
        )
        .join("")
    : "";

  return `<article class="character-card">
    <div class="character-head"><div><h4>${escapeHtml(item.name)}</h4><span>${escapeHtml(roleText)}</span><span class="importance-badge">${escapeHtml(importanceText)}</span></div><div class="character-progress">${escapeHtml(progressText)}<small>记忆版本 v${Number(item.version || 1)}</small></div></div>
    ${factsHtml ? `<details class="character-section" open><summary><h5>人物档案</h5></summary><dl>${factsHtml}</dl></details>` : ""}
    ${hasAppeared && stateHtml ? `<details class="character-section"><summary><h5>当前进展（${stateRows.length} 项）</h5></summary><dl>${stateHtml}</dl></details>` : ""}
    ${!hasAppeared ? `<p class="character-empty">尚未在正文中正式出场，档案数据来自创作方案。</p>` : ""}
  </article>`;
}

function characterListItem(item, selected) {
  const currentState = item.current_state || {};
  const progressChapter = Number(currentState.last_seen_chapter ?? currentState.chapter ?? 0);
  const progressText = progressChapter > 0 ? `最近第 ${progressChapter} 章` : "尚未正式出场";
  const roleText = characterRoleLabels[item.role] || "人物";
  const importanceText =
    currentState.importance === "core" || item.role === "protagonist" ? "核心" : "重要";
  const initial = Array.from(String(item.name || "人"))[0] || "人";
  return `<button class="character-list-item${selected ? " selected" : ""}" type="button" data-character-id="${escapeHtml(item.id)}" aria-pressed="${selected}">
    <span class="character-avatar">${escapeHtml(initial)}</span>
    <span class="character-list-copy"><b>${escapeHtml(item.name)}</b><small>${escapeHtml(roleText)} · ${escapeHtml(importanceText)}人物</small><em>${escapeHtml(progressText)}</em></span>
    <span class="character-chevron">›</span>
  </button>`;
}

function selectCharacter(characterId, openDetail = false) {
  const selected = shellState.characterArchive.find((item) => item.id === characterId);
  if (!selected) return;
  shellState.selectedCharacterId = selected.id;
  $$("#characterList .character-list-item").forEach((button) => {
    const active = button.dataset.characterId === selected.id;
    button.classList.toggle("selected", active);
    button.setAttribute("aria-pressed", String(active));
  });
  $("#characterDetail").innerHTML = renderCharacterCard(selected);
  if (openDetail) $("#characterBrowser").classList.add("show-detail");
}

function renderCharacterArchive(characters) {
  shellState.characterArchive = characters;
  $("#characterCount").textContent = `${characters.length} 人`;
  if (!characters.length) {
    shellState.selectedCharacterId = null;
    $("#characterList").innerHTML = '<div class="empty">暂无重要人物</div>';
    $("#characterDetail").innerHTML = '<div class="empty">暂无人物档案</div>';
    $("#characterBrowser").classList.remove("show-detail");
    return;
  }
  const selected =
    characters.find((item) => item.id === shellState.selectedCharacterId) ||
    characters.find((item) => item.role === "protagonist") ||
    characters[0];
  shellState.selectedCharacterId = selected.id;
  $("#characterList").innerHTML = characters
    .map((item) => characterListItem(item, item.id === selected.id))
    .join("");
  $$("#characterList .character-list-item").forEach((button) =>
    button.addEventListener("click", () => selectCharacter(button.dataset.characterId, true))
  );
  $("#characterBrowser").classList.remove("show-detail");
  selectCharacter(selected.id);
}

function showCharacterList() {
  $("#characterBrowser").classList.remove("show-detail");
  const selected = $(
    `#characterList .character-list-item[data-character-id="${shellState.selectedCharacterId}"]`
  );
  selected?.focus();
}

function renderMemory(characters, facts, timeline, researchSources, semanticCount) {
  renderCharacterArchive(characters);
  const categoryGroups = {};
  facts.forEach((f) => {
    (categoryGroups[f.category] ||= []).push(f);
  });
  const factHtml = Object.entries(categoryGroups)
    .map(([cat, items]) => {
      const body = items
        .map((f) => `<p>${escapeHtml(f.statement)} ${f.locked ? "🔒" : ""}</p>`)
        .join("");
      return `<details class="fact-group"><summary>${escapeHtml(cat)} (${items.length})</summary><div class="fact-group-body">${body}</div></details>`;
    })
    .join("");
  $("#worldContent").innerHTML = facts.length ? factHtml : '<div class="empty">暂无规则</div>';
  const maxTimeline = 15;
  const visibleTimeline = timeline.slice(-maxTimeline);
  const hiddenCount = timeline.length - maxTimeline;
  const timelineHtml = visibleTimeline
    .map(
      (item) =>
        `<div class="timeline-item"><b>第 ${item.chapter_number} 章</b><p>${escapeHtml(item.event)}</p></div>`
    )
    .join("");
  const expandHtml =
    hiddenCount > 0
      ? `<button class="text-button" id="expandTimeline" style="margin-top:8px;font-size:11px">展开全部 ${timeline.length} 条</button>
       <div id="hiddenTimeline" class="hidden">${timeline
         .slice(0, -maxTimeline)
         .map(
           (item) =>
             `<div class="timeline-item"><b>第 ${item.chapter_number} 章</b><p>${escapeHtml(item.event)}</p></div>`
         )
         .join("")}</div>`
      : "";
  $("#timelineContent").innerHTML = timeline.length
    ? timelineHtml + expandHtml
    : '<div class="empty">暂无正式事件</div>';
  if (hiddenCount > 0) {
    $("#expandTimeline").addEventListener("click", () => {
      $("#hiddenTimeline").classList.toggle("hidden");
      $("#expandTimeline").textContent = $("#hiddenTimeline").classList.contains("hidden")
        ? `展开全部 ${timeline.length} 条`
        : "收起";
    });
  }
  $("#semanticCount").textContent = `${semanticCount} 条语义索引`;
  const maxResearch = 5;
  const visibleResearch = researchSources.slice(0, maxResearch);
  const hiddenResearch = researchSources.length - maxResearch;
  const researchHtml = visibleResearch
    .map(
      (item) =>
        `<div class="research-card"><div><b>${escapeHtml(item.title || item.domain || "网页来源")}</b><span>${item.verified ? "已获得交叉来源" : "单一来源"} · 可信度 ${Number(item.reliability || 0).toFixed(2)}</span></div><p>${escapeHtml(item.excerpt || "")}</p>${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">打开来源 ↗</a>` : ""}</div>`
    )
    .join("");
  const researchExpand =
    hiddenResearch > 0
      ? `<button class="text-button" id="expandResearch" style="margin-top:8px;font-size:11px">展开全部 ${researchSources.length} 条</button>
       <div id="hiddenResearch" class="hidden">${researchSources
         .slice(maxResearch)
         .map(
           (item) =>
             `<div class="research-card"><div><b>${escapeHtml(item.title || item.domain || "网页来源")}</b><span>${item.verified ? "已获得交叉来源" : "单一来源"} · 可信度 ${Number(item.reliability || 0).toFixed(2)}</span></div><p>${escapeHtml(item.excerpt || "")}</p>${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">打开来源 ↗</a>` : ""}</div>`
         )
         .join("")}</div>`
      : "";
  $("#researchContent").innerHTML = researchSources.length
    ? researchHtml + researchExpand
    : '<div class="empty">尚未触发现实知识调研</div>';
  if (hiddenResearch > 0) {
    $("#expandResearch").addEventListener("click", () => {
      $("#hiddenResearch").classList.toggle("hidden");
      $("#expandResearch").textContent = $("#hiddenResearch").classList.contains("hidden")
        ? `展开全部 ${researchSources.length} 条`
        : "收起";
    });
  }
}

async function rebuildCharacterArchives() {
  const projectId = selectedProjectId();
  if (!projectId) return notify("请先选择小说项目", true);
  if (
    !window.confirm(
      "将扫描这本书的全部 READY 章节，只保留核心人物和重要人物；在线模式下会调用大模型。是否继续？"
    )
  )
    return;
  busy(true);
  try {
    const result = await api(`/api/novels/${projectId}/characters/rebuild`, {
      method: "POST",
      body: "{}",
    });
    await projectsController.loadSelected();
    const failed = result.failures?.length ? `，${result.failures.length} 章提取失败` : "";
    const removed = result.removed_nonimportant
      ? `，清理 ${result.removed_nonimportant} 个非重要人物档案`
      : "";
    notify(
      `重要人物档案重建完成：扫描 ${result.processed_chapters} 章，共 ${result.character_count} 人${removed}${failed}`
    );
  } catch (error) {
    notify(error.message, true);
  } finally {
    busy(false);
  }
}

function renderPipeline(events) {
  shellState.lastEvents = events;
  $("#pipeline").innerHTML = events.length
    ? events
        .map(
          (event, index) =>
            `<div class="pipeline-event"><span class="node-dot">${index + 1}</span><div><b>${escapeHtml(event.node)}</b><p>${escapeHtml(event.message)}</p></div><time>${event.progress}%</time></div>`
        )
        .join("")
    : '<div class="pipeline-empty">生成章节后，这里会显示每个工作流节点。</div>';
}

async function generateChapter() {
  const projectId = selectedProjectId();
  if (!projectId) return;
  try {
    busy(true);
    const payload = await api(`/api/novels/${projectId}/runs`, {
      method: "POST",
      body: JSON.stringify({ count: 1 }),
    });
    const result = payload.items[0];
    renderPipeline(result.events);
    if (result.chapter.status === "READY") {
      notify(`${result.chapter.title} 已通过审核并进入 READY 储备。`);
    } else {
      notify(
        `${result.chapter.title} 暂未通过质量门槛，已保留草稿；可再次生成进行定向重写。`,
        true
      );
    }
    await refresh();
  } catch (error) {
    notify(error.message, true);
  } finally {
    busy(false);
  }
}

function renderSettingsRuntime(runtime) {
  const body = $("#settingsRuntimeBody");
  if (!body) return;
  if (!runtime) {
    body.innerHTML = '<p class="muted">暂时无法读取运行能力状态。</p>';
    return;
  }
  const rows = [
    ["大模型 (LLM)", runtime.llm],
    ["联网搜索", runtime.search],
    ["向量嵌入", runtime.embedding],
    ["发布适配", runtime.publisher],
    ["Story Skills", runtime.story_skills],
    ["OH Story 写作技能", runtime.oh_story],
  ];
  body.innerHTML = rows
    .map(([title, item]) => {
      if (!item) return "";
      const enabled = Boolean(item.enabled);
      const configured = Boolean(item.configured);
      const statusClass = enabled ? "ok" : configured ? "warn" : "off";
      const statusText = enabled ? "已启用" : configured ? "已配置未启用" : "未配置";
      const detail = [item.provider, item.model].filter(Boolean).join(" · ");
      return `<div class="runtime-status-item"><div><b>${escapeHtml(title)}</b>${detail ? `<div class="muted">${escapeHtml(detail)}</div>` : ""}</div><span class="${statusClass}">${statusText}</span></div>`;
    })
    .join("");
}

async function loadSettings() {
  try {
    const settings = await api("/api/settings");
    renderSettingsRuntime(settings.runtime);
    const form = $("#settingsForm");
    for (const [key, value] of Object.entries(settings.preferences)) {
      const input = form.elements[key];
      if (!input) continue;
      if (input.type === "checkbox") input.checked = Boolean(value);
      else input.value = value;
    }
  } catch (error) {
    notify(error.message, true);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    daily_chapters: Number(form.get("daily_chapters")),
    reserve_target: Number(form.get("reserve_target")),
    budget_limit: Number(form.get("budget_limit")),
    debug_mode: form.has("debug_mode"),
  };
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
    notify("本地偏好已保存。");
  } catch (error) {
    notify(error.message, true);
  }
}

async function boot() {
  wireNavigation();
  await novelCreateView.loadTags();
  await refresh();
}

async function startApp() {
  try {
    const [{ api: request }, projectsMod, novelCreateMod, storyBriefMod, dashboardMod, analyticsMod] =
      await Promise.all([
        import("/js/core/api-client.js"),
        import("/js/features/projects/index.js"),
        import("/js/features/novel-create/index.js"),
        import("/js/features/story-brief/index.js"),
        import("/js/features/project-dashboard/index.js"),
        import("/js/features/analytics/index.js"),
      ]);

    api = request;
    PROJECT_STORAGE_KEY = projectsMod.PROJECT_STORAGE_KEY;
    projectsState = projectsMod.createProjectsState();
    projectsApi = projectsMod.createProjectsApi(api);
    projectsController = projectsMod.createProjectsController({
      state: projectsState,
      api: projectsApi,
      notify,
      onDetailLoaded: (detail) => {
        projectDashboardView?.renderDetail(detail);
        const events = detail.latest_events || [];
        if (events.length) renderPipeline(events);
      },
      onEmpty: () => {
        projectDashboardView?.renderEmpty();
        window.ReaderWorkspace?.setProject(null);
      },
    });

    storyBriefView = storyBriefMod.createStoryBriefView({
      api,
      notify,
      busy,
      escapeHtml,
      onRefresh: refresh,
    });
    storyBriefView.mount($("#dashboardView"));

    projectDashboardView = dashboardMod.createProjectDashboardView({
      api,
      notify,
      busy,
      escapeHtml,
      getState: () => projectsState.getSnapshot(),
      selectClear: () => projectsController.clearSelection(),
      refresh,
      storyBrief: storyBriefView,
      onAfterDetail: (detail, parts) => {
        renderChapters(parts.chapters);
        renderMemory(
          parts.characters,
          parts.worldFacts,
          parts.timeline,
          parts.researchSources,
          parts.semanticCount
        );
      },
      onGenerate: generateChapter,
      onDeleted: refresh,
      onActionComplete: refresh,
    });
    projectDashboardView.mount($("#dashboardView"));

    novelCreateView = novelCreateMod.createNovelCreateView({
      api,
      notify,
      busy,
      escapeHtml,
      onCreated: async (project) => {
        localStorage.setItem(PROJECT_STORAGE_KEY, project.id);
        projectsState.select(project.id);
        await refresh();
        switchView("dashboard");
      },
    });
    novelCreateView.mount($("#createView"));

    analyticsView = analyticsMod.createAnalyticsView({ api, notify, escapeHtml });
    analyticsView.mount($("#analyticsView"));
  } catch (error) {
    console.error("功能模块初始化失败", error);
  }

  try {
    window.ReaderWorkspace?.init({ api, notify, busy });
  } catch (error) {
    console.error("阅读工作台初始化失败", error);
  }

  void boot().catch((error) => console.error("应用启动失败", error));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startApp);
} else {
  startApp();
}
