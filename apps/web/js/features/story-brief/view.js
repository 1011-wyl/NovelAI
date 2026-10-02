import { escapeHtml as defaultEscapeHtml } from "../../core/dom.js";
import { createStoryBriefApi } from "./api.js";
import { createBriefEditor } from "./editor.js";
import { createBriefVersions } from "./versions.js";
import {
  BRIEF_CONTENT_PLACEHOLDER,
  mountBriefWorkbench,
  renderBriefHtml,
} from "./template.js";

function isEditableDraft(detail) {
  const project = detail?.project;
  const chapters = detail?.chapters || [];
  return Boolean(project && project.status === "DRAFT" && !project.confirmed && chapters.length === 0);
}

export function createStoryBriefView({ api: request, notify, busy, escapeHtml, onRefresh } = {}) {
  const esc = escapeHtml || defaultEscapeHtml;
  const api = createStoryBriefApi(request);
  let host = null;
  let workbench = null;
  let briefContent = null;
  let editor = null;
  let versions = null;
  let currentDetail = null;
  let briefVersions = [];
  let mounted = false;
  let destroyed = false;
  let listenerAbort = null;
  let versionsGeneration = 0;

  function $(selector) {
    return (host || document).querySelector(selector);
  }

  function getProjectId() {
    return currentDetail?.project?.id || null;
  }

  function getDetail() {
    return currentDetail;
  }

  function getBriefVersions() {
    return briefVersions;
  }

  function setBriefVersions(items) {
    briefVersions = Array.isArray(items) ? items : [];
  }

  function renderBrief(brief, req) {
    if (!briefContent) return;
    if (!brief || !req) {
      briefContent.classList.add("empty");
      briefContent.innerHTML = BRIEF_CONTENT_PLACEHOLDER;
      return;
    }
    briefContent.classList.remove("empty");
    briefContent.innerHTML = renderBriefHtml(brief, req, esc);
  }

  function bindChildren() {
    if (listenerAbort) listenerAbort.abort();
    listenerAbort = new AbortController();
    const { signal } = listenerAbort;

    editor = createBriefEditor({
      root: host,
      api,
      getProjectId,
      getDetail,
      notify,
      busy,
      onSaved: () => onRefresh?.(),
      onRegenerated: () => onRefresh?.(),
    });
    versions = createBriefVersions({
      root: host,
      api,
      getProjectId,
      notify,
      busy,
      escapeHtml: esc,
      onRestored: () => onRefresh?.(),
      getBriefVersions,
      setBriefVersions,
    });
    editor.bindEvents(signal);
    versions.bindEvents(signal);
  }

  function mount(dashboardHost) {
    if (destroyed) return;
    host = dashboardHost;
    if (!host) return;
    workbench = mountBriefWorkbench(host);
    briefContent = host.querySelector("#briefContent") || document.querySelector("#briefContent");
    if (mounted) {
      bindChildren();
      return;
    }
    bindChildren();
    mounted = true;
  }

  async function setProjectDetail(detail) {
    if (destroyed || !mounted) return;
    versionsGeneration += 1;
    const generation = versionsGeneration;
    versions?.invalidate?.();
    currentDetail = detail || null;

    if (!detail?.project) {
      renderBrief(null, null);
      workbench?.classList.add("hidden");
      setBriefVersions([]);
      return;
    }

    const { project } = detail;
    renderBrief(project.brief, project.request);
    const editable = isEditableDraft(detail);
    workbench?.classList.toggle("hidden", !editable);
    $("#editBriefButton")?.classList.toggle("hidden", !editable);
    $("#regenerateBriefButton")?.classList.toggle("hidden", !editable);

    if (editable) {
      editor?.populateBriefEditor(project.brief);
      try {
        await versions?.loadVersions();
        if (generation !== versionsGeneration) return;
      } catch (error) {
        if (error.stale || generation !== versionsGeneration) return;
      }
    } else {
      setBriefVersions([]);
    }
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    versionsGeneration += 1;
    api.abortAll();
    versions?.invalidate?.();
    if (listenerAbort) {
      listenerAbort.abort();
      listenerAbort = null;
    }
    editor = null;
    versions = null;
    currentDetail = null;
    briefVersions = [];
    mounted = false;
    host = null;
    workbench = null;
    briefContent = null;
  }

  return {
    mount,
    setProjectDetail,
    destroy,
  };
}
