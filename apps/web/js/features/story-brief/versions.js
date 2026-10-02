const VERSION_SOURCE_MAP = {
  initial: "初始方案",
  migration: "历史方案",
  manual_edit: "手工修改",
  regenerate: "整体重做",
  partial_regenerate: "局部重做",
  feedback_regenerate: "按意见重做",
  restore: "恢复旧版",
};

export function versionSource(source) {
  return VERSION_SOURCE_MAP[source] || source;
}

export function createBriefVersions({
  root,
  api,
  getProjectId,
  notify,
  busy,
  escapeHtml,
  onRestored,
  getBriefVersions,
  setBriefVersions,
} = {}) {
  let loadGeneration = 0;

  function $(selector) {
    return (root || document).querySelector(selector);
  }

  function renderComparison() {
    const versions = getBriefVersions?.() || [];
    const render = (target, version) => {
      const el = $(target);
      if (!el) return;
      const item = versions.find((entry) => entry.version === Number(version));
      if (!item) {
        el.innerHTML = "暂无版本";
        return;
      }
      const brief = item.brief;
      el.innerHTML = `<h4>v${item.version} · ${escapeHtml(versionSource(item.source))}</h4><p><strong>书名：</strong>${escapeHtml(brief.selected_title)}</p><p><strong>主角：</strong>${escapeHtml(brief.protagonist_name || brief.protagonist)}</p><p><strong>简介：</strong>${escapeHtml(brief.synopsis)}</p><p><strong>主要冲突：</strong>${escapeHtml(brief.main_conflict)}</p><p><strong>世界规则：</strong>${(brief.world_rules || []).map(escapeHtml).join("；")}</p>${item.feedback ? `<p><strong>修改意见：</strong>${escapeHtml(item.feedback)}</p>` : ""}`;
    };
    render("#briefCompareLeft", $("#briefVersionLeft")?.value);
    render("#briefCompareRight", $("#briefVersionRight")?.value);
  }

  async function loadVersions() {
    const projectId = getProjectId?.();
    if (!projectId) {
      setBriefVersions?.([]);
      return [];
    }
    const generation = ++loadGeneration;
    try {
      const payload = await api.listVersions(projectId);
      if (generation !== loadGeneration || getProjectId?.() !== projectId) {
        return null;
      }
      const items = payload.items || [];
      setBriefVersions?.(items);
      const options = items
        .map(
          (item) =>
            `<option value="${item.version}">v${item.version} · ${escapeHtml(versionSource(item.source))}</option>`
        )
        .join("");
      const left = $("#briefVersionLeft");
      const right = $("#briefVersionRight");
      if (left) left.innerHTML = options;
      if (right) right.innerHTML = options;
      if (items.length > 1 && left) left.value = items[1].version;
      if (items.length && right) right.value = items[0].version;
      renderComparison();
      return items;
    } catch (error) {
      if (error.stale || generation !== loadGeneration) return null;
      notify?.(error.message, true);
      throw error;
    }
  }

  async function restore() {
    const projectId = getProjectId?.();
    if (!projectId) return;
    const version = Number($("#briefVersionLeft")?.value);
    if (!version) return;
    try {
      busy?.(true);
      await api.restoreBrief(projectId, version);
      notify?.(`已恢复 v${version}，并保存为新的当前版本。`);
      onRestored?.();
    } catch (error) {
      if (error.stale) return;
      notify?.(error.message, true);
    } finally {
      busy?.(false);
    }
  }

  function bindEvents(signal) {
    $("#briefVersionLeft")?.addEventListener("change", renderComparison, { signal });
    $("#briefVersionRight")?.addEventListener("change", renderComparison, { signal });
    $("#restoreBriefVersion")?.addEventListener("click", restore, { signal });
  }

  function invalidate() {
    loadGeneration += 1;
    api?.abort?.("versions");
  }

  return {
    versionSource,
    loadVersions,
    renderComparison,
    restore,
    bindEvents,
    invalidate,
  };
}
