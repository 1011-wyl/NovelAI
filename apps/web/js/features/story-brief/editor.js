function splitLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function createBriefEditor({
  root,
  api,
  getProjectId,
  getDetail,
  notify,
  busy,
  onSaved,
  onRegenerated,
} = {}) {
  function $(selector) {
    return (root || document).querySelector(selector);
  }

  function populateBriefEditor(brief) {
    const form = $("#briefEditForm");
    if (!form || !brief) return;
    const set = (name, value) => {
      if (form.elements[name]) form.elements[name].value = value ?? "";
    };
    set("selected_title", brief.selected_title);
    set("synopsis", brief.synopsis);
    set("target_readers", brief.target_readers);
    set("protagonist_name", brief.protagonist_name || brief.protagonist);
    set("protagonist_profile", brief.protagonist_profile);
    set("main_conflict", brief.main_conflict);
    set("reader_contract", brief.reader_contract);
    set("core_expectation", brief.core_expectation);
    set("selling_points", (brief.selling_points || []).join("\n"));
    set("world_rules", (brief.world_rules || []).join("\n"));
    set("opening_three_chapters", (brief.opening_three_chapters || []).join("\n"));
    set("style_guide", (brief.style_guide || []).join("\n"));
    set("total_chapters", brief.total_chapters);
    set("volume_count", brief.volume_count);
    set("update_plan", brief.update_plan);
  }

  function buildBriefFromForm(formElement) {
    const detail = getDetail?.();
    const current = detail?.project?.brief;
    if (!current) return null;
    const form = new FormData(formElement);
    const title = String(form.get("selected_title")).trim();
    return {
      ...current,
      selected_title: title,
      title_candidates: [...new Set([title, ...(current.title_candidates || [])])].slice(0, 6),
      synopsis: String(form.get("synopsis")).trim(),
      target_readers: String(form.get("target_readers")).trim(),
      selling_points: splitLines(form.get("selling_points")),
      protagonist: String(form.get("protagonist_name")).trim(),
      protagonist_name: String(form.get("protagonist_name")).trim(),
      protagonist_profile: String(form.get("protagonist_profile")).trim(),
      main_conflict: String(form.get("main_conflict")).trim(),
      reader_contract: String(form.get("reader_contract")).trim(),
      core_expectation: String(form.get("core_expectation")).trim(),
      world_rules: splitLines(form.get("world_rules")),
      total_chapters: Number(form.get("total_chapters")),
      volume_count: Number(form.get("volume_count")),
      opening_three_chapters: splitLines(form.get("opening_three_chapters")),
      update_plan: String(form.get("update_plan")).trim(),
      style_guide: splitLines(form.get("style_guide")),
      character_profiles: current.character_profiles,
    };
  }

  async function saveBriefEdit(event) {
    event.preventDefault();
    const projectId = getProjectId?.();
    if (!projectId) return;
    const brief = buildBriefFromForm(event.target);
    if (!brief) return;
    try {
      busy?.(true);
      await api.updateBrief(projectId, brief);
      $("#briefEditForm")?.classList.add("hidden");
      notify?.("方案修改已保存为新版本。");
      onSaved?.();
    } catch (error) {
      if (error.stale) return;
      notify?.(error.message, true);
    } finally {
      busy?.(false);
    }
  }

  async function regenerateBrief(payload) {
    const projectId = getProjectId?.();
    if (!projectId) return;
    try {
      busy?.(true);
      await api.regenerateBrief(projectId, payload);
      const feedback = $("#briefFeedback");
      if (feedback) feedback.value = "";
      $("#briefSections")
        ?.querySelectorAll("input")
        .forEach((item) => {
          item.checked = false;
        });
      notify?.(
        payload.sections.length
          ? "选中的方案模块已重做并保存为新版本。"
          : "已生成新的创作方案版本。"
      );
      onRegenerated?.();
    } catch (error) {
      if (error.stale) return;
      notify?.(error.message, true);
    } finally {
      busy?.(false);
    }
  }

  async function regenerateBriefFromFeedback() {
    const feedback = ($("#briefFeedback")?.value || "").trim();
    const sections = [...($("#briefSections")?.querySelectorAll("input:checked") || [])].map(
      (item) => item.value
    );
    if (!feedback && !sections.length) {
      notify?.("请填写修改意见或选择需要重做的模块。", true);
      return;
    }
    await regenerateBrief({ feedback, sections });
  }

  function bindEvents(signal) {
    $("#editBriefButton")?.addEventListener(
      "click",
      () => $("#briefEditForm")?.classList.toggle("hidden"),
      { signal }
    );
    $("#cancelBriefEdit")?.addEventListener(
      "click",
      () => $("#briefEditForm")?.classList.add("hidden"),
      { signal }
    );
    $("#briefEditForm")?.addEventListener("submit", saveBriefEdit, { signal });
    $("#regenerateBriefButton")?.addEventListener(
      "click",
      () => regenerateBrief({ feedback: "", sections: [] }),
      { signal }
    );
    $("#feedbackRegenerateButton")?.addEventListener("click", regenerateBriefFromFeedback, {
      signal,
    });
  }

  return {
    populateBriefEditor,
    splitLines,
    bindEvents,
    saveBriefEdit,
    regenerateBrief,
    regenerateBriefFromFeedback,
  };
}
