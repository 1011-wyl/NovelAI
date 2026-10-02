import { escapeHtml as defaultEscapeHtml } from "../../core/dom.js";
import { createProjectsApi } from "../projects/api.js";
import { mountDashboardHero } from "./template.js";

const STATUS_LABELS = {
  DRAFT: "等待方案确认",
  ACTIVE: "自动连载可用",
  PAUSED: "已暂停",
  HUMAN_REQUIRED: "需要人工处理",
  ARCHIVED: "已归档",
};

const ACTION_MESSAGES = {
  confirm: "创作方案已确认，智能体可以开始连载。",
  pause: "项目已暂停。",
  resume: "项目已恢复。",
  recover: "已修复主角姓名数据，项目可以重新生成。",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

export function createProjectDashboardView({
  api: request,
  notify,
  busy,
  escapeHtml,
  getState,
  selectClear,
  refresh,
  storyBrief,
  onAfterDetail,
  onGenerate,
  onDeleted,
  onActionComplete,
} = {}) {
  const esc = escapeHtml || defaultEscapeHtml;
  const api = createProjectsApi(request);
  let host = null;
  let hero = null;
  let mounted = false;
  let destroyed = false;
  let listenerAbort = null;

  function $(selector) {
    return (host || document).querySelector(selector);
  }

  function currentDetail() {
    return getState?.()?.detail || null;
  }

  function currentProjectId() {
    return getState?.()?.selectedId || currentDetail()?.project?.id || null;
  }

  function renderEmpty() {
    const title = $("#projectTitle");
    const synopsis = $("#projectSynopsis");
    const status = $("#projectStatus");
    if (title) title.textContent = "让一个想法，变成持续生长的故事";
    if (synopsis) {
      synopsis.textContent =
        "选择标签并补充一句创意，系统会建立故事骨架，随后按章节规划、写作、审核和储备。";
    }
    if (status) status.textContent = "等待创建";
    $("#generateButton") && ($("#generateButton").disabled = true);
    $("#confirmButton")?.classList.add("hidden");
    $("#editBriefButton")?.classList.add("hidden");
    $("#regenerateBriefButton")?.classList.add("hidden");
    $("#deleteDraftButton")?.classList.add("hidden");
    $("#briefWorkbench")?.classList.add("hidden");
    $("#recoverButton")?.classList.add("hidden");
    $("#pauseButton")?.classList.add("hidden");
    ["todayCount", "reserveCount", "chapterCount"].forEach((id) => {
      const el = $(`#${id}`);
      if (el) el.textContent = "0";
    });
    const health = $("#healthScore");
    if (health) health.textContent = "--";
    storyBrief?.setProjectDetail?.(null);
  }

  function renderDetail(detail) {
    if (!detail?.project) {
      renderEmpty();
      return;
    }
    const {
      project,
      chapters,
      characters,
      world_facts: worldFacts,
      timeline,
      research_sources: researchSources,
      semantic_document_count: semanticCount,
      reserve_count: reserveCount,
    } = detail;

    const title = $("#projectTitle");
    const synopsis = $("#projectSynopsis");
    const status = $("#projectStatus");
    if (title) title.textContent = project.title;
    if (synopsis) synopsis.textContent = project.brief.synopsis;
    if (status) status.textContent = statusLabel(project.status);

    const reserveEl = $("#reserveCount");
    if (reserveEl) reserveEl.textContent = reserveCount;
    const reserveTarget = $("#reserveTarget");
    if (reserveTarget) reserveTarget.textContent = `目标 ${project.request.reserve_target}`;
    const chapterCount = $("#chapterCount");
    if (chapterCount) {
      chapterCount.textContent = chapters.filter((c) =>
        ["READY", "SCHEDULED", "PUBLISHED"].includes(c.status)
      ).length;
    }
    const todayCount = $("#todayCount");
    if (todayCount) {
      todayCount.textContent = chapters.filter(
        (c) =>
          c.created_at.slice(0, 10) === new Date().toISOString().slice(0, 10) && c.status === "READY"
      ).length;
    }
    const healthScore = $("#healthScore");
    if (healthScore) {
      healthScore.textContent = chapters.some((c) => c.status === "FAILED") ? "需处理" : "正常";
    }

    const canGenerate = project.confirmed && project.status === "ACTIVE";
    const generateButton = $("#generateButton");
    if (generateButton) generateButton.disabled = !canGenerate;
    $("#confirmButton")?.classList.toggle("hidden", project.confirmed);

    const editableDraft = project.status === "DRAFT" && !project.confirmed && chapters.length === 0;
    $("#editBriefButton")?.classList.toggle("hidden", !editableDraft);
    $("#regenerateBriefButton")?.classList.toggle("hidden", !editableDraft);
    $("#briefWorkbench")?.classList.toggle("hidden", !editableDraft);

    const deleteButton = $("#deleteDraftButton");
    if (deleteButton) {
      deleteButton.classList.remove("hidden");
      deleteButton.textContent =
        project.status === "DRAFT" && !project.confirmed && chapters.length === 0
          ? "删除草稿"
          : "删除作品";
    }

    $("#recoverButton")?.classList.toggle("hidden", project.status !== "HUMAN_REQUIRED");
    $("#pauseButton")?.classList.toggle("hidden", !project.confirmed);
    const pauseButton = $("#pauseButton");
    if (pauseButton) pauseButton.textContent = project.status === "PAUSED" ? "继续" : "暂停";

    storyBrief?.setProjectDetail?.(detail);
    onAfterDetail?.(detail, {
      chapters,
      characters,
      worldFacts,
      timeline,
      researchSources: researchSources || [],
      semanticCount: semanticCount || 0,
    });
  }

  async function projectAction(action) {
    const projectId = currentProjectId();
    if (!projectId) return;
    try {
      busy?.(true);
      if (action === "confirm") await api.confirm(projectId);
      else if (action === "pause") await api.pause(projectId);
      else if (action === "resume") await api.resume(projectId);
      else if (action === "recover") await api.recover(projectId);
      notify?.(ACTION_MESSAGES[action]);
      if (onActionComplete) await onActionComplete(action);
      else if (refresh) await refresh();
    } catch (error) {
      if (error.stale) return;
      notify?.(error.message, true);
    } finally {
      busy?.(false);
    }
  }

  async function deleteProject() {
    const detail = currentDetail();
    const projectId = currentProjectId();
    if (!projectId || !detail) return;
    const { project, chapters } = detail;
    const totalChapters = chapters.length;
    const readyCount = chapters.filter((c) =>
      ["READY", "SCHEDULED", "PUBLISHED"].includes(c.status)
    ).length;
    const editableDraft = project.status === "DRAFT" && !project.confirmed && totalChapters === 0;
    let message;
    if (editableDraft) {
      message = "确定删除这个未确认的草稿项目吗？此操作不能撤销。";
    } else if (totalChapters > 0) {
      message = `确定删除作品「${project.title}」吗？\n\n该项目共有 ${totalChapters} 章（其中 ${readyCount} 章已完成），所有人物档案、时间线、世界规则和章节数据都将被永久删除。\n\n此操作不可撤销！`;
    } else {
      message = `确定删除作品「${project.title}」吗？此操作将永久删除该项目及所有关联数据，不可撤销。`;
    }
    if (editableDraft) {
      if (!window.confirm(message)) return;
    } else {
      const entered = window.prompt(`${message}\n\n请输入完整书名“${project.title}”确认删除：`, "");
      if (entered === null) return;
      if (entered.trim() !== project.title) {
        notify?.("书名不匹配，已取消删除。", true);
        return;
      }
    }
    try {
      busy?.(true);
      await api.deleteProject(projectId, project.title);
      selectClear?.();
      notify?.("作品已删除。");
      if (onDeleted) await onDeleted();
      else if (refresh) await refresh();
    } catch (error) {
      if (error.stale) return;
      notify?.(error.message, true);
    } finally {
      busy?.(false);
    }
  }

  function bindActions() {
    if (listenerAbort) listenerAbort.abort();
    listenerAbort = new AbortController();
    const { signal } = listenerAbort;

    $("#confirmButton")?.addEventListener("click", () => projectAction("confirm"), { signal });
    $("#recoverButton")?.addEventListener("click", () => projectAction("recover"), { signal });
    $("#pauseButton")?.addEventListener(
      "click",
      () => {
        const action = currentDetail()?.project?.status === "PAUSED" ? "resume" : "pause";
        projectAction(action);
      },
      { signal }
    );
    $("#deleteDraftButton")?.addEventListener("click", deleteProject, { signal });
    $("#generateButton")?.addEventListener(
      "click",
      () => {
        onGenerate?.();
      },
      { signal }
    );
  }

  function mount(dashboardHost) {
    if (destroyed) return;
    host = dashboardHost;
    if (!host) return;
    hero = mountDashboardHero(host);
    if (mounted) {
      bindActions();
      return;
    }
    bindActions();
    mounted = true;
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    api.abortAll();
    if (listenerAbort) {
      listenerAbort.abort();
      listenerAbort = null;
    }
    mounted = false;
    host = null;
    hero = null;
  }

  return {
    mount,
    renderEmpty,
    renderDetail,
    destroy,
    statusLabel,
  };
}
