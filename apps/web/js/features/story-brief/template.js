export const BRIEF_CONTENT_PLACEHOLDER = "创建小说后显示方案、卖点和世界规则。";

export const BRIEF_WORKBENCH_TEMPLATE = `
<article id="briefWorkbench" class="panel brief-workbench hidden">
  <div class="panel-head"><div><p class="eyebrow">方案工作台</p><h3>方案修改与版本对比</h3></div><span class="badge">确认前可修改</span></div>
  <div class="workbench-grid">
    <form id="briefEditForm" class="brief-edit-form hidden">
      <label>正式书名<input name="selected_title" maxlength="80" required></label>
      <label>故事简介<textarea name="synopsis" rows="4" required></textarea></label>
      <div class="field-row"><label>目标读者<input name="target_readers" required></label><label>主角姓名<input name="protagonist_name" maxlength="20" required></label></div>
      <label>主角介绍<textarea name="protagonist_profile" rows="3"></textarea></label>
      <label>主要冲突<textarea name="main_conflict" rows="2" required></textarea></label>
      <label>读者契约<textarea name="reader_contract" rows="2" placeholder="这本书持续向读者交付什么核心情绪回报"></textarea></label>
      <label>核心期待<textarea name="core_expectation" rows="2" placeholder="开篇建立并需要持续推进的主要期待"></textarea></label>
      <label>核心卖点（每行一项）<textarea name="selling_points" rows="3"></textarea></label>
      <label>世界规则（每行一项）<textarea name="world_rules" rows="4"></textarea></label>
      <label>开篇三章（每行一章）<textarea name="opening_three_chapters" rows="3"></textarea></label>
      <label>文风规则（每行一项）<textarea name="style_guide" rows="3"></textarea></label>
      <div class="field-row"><label>预计章节数<input name="total_chapters" type="number" min="1" required></label><label>分卷数<input name="volume_count" type="number" min="1" required></label></div>
      <label>更新计划<input name="update_plan" required></label>
      <div class="form-actions"><button class="button primary" type="submit">保存为新版本</button><button id="cancelBriefEdit" class="button ghost" type="button">取消</button></div>
    </form>
    <div class="brief-regenerate-box">
      <label>告诉智能体哪里不满意<textarea id="briefFeedback" rows="4" placeholder="例如：书名更简洁；主角不要重生；开篇冲突更快。"></textarea></label>
      <fieldset><legend>只重做选中的模块；不选则整体优化</legend><div class="chips compact-chips" id="briefSections">
        <label class="chip"><input type="checkbox" value="title"><span>书名</span></label>
        <label class="chip"><input type="checkbox" value="story"><span>故事核心</span></label>
        <label class="chip"><input type="checkbox" value="protagonist"><span>主角</span></label>
        <label class="chip"><input type="checkbox" value="world"><span>世界规则</span></label>
        <label class="chip"><input type="checkbox" value="opening"><span>开篇三章</span></label>
        <label class="chip"><input type="checkbox" value="style"><span>文风</span></label>
        <label class="chip"><input type="checkbox" value="serialization"><span>连载计划</span></label>
      </div></fieldset>
      <button id="feedbackRegenerateButton" class="button secondary" type="button">按意见生成新版本</button>
      <p class="muted">每次修改都会保留旧版本。只有点击“确认创作方案”后才会锁定设定并开始写作。</p>
    </div>
  </div>
  <div class="version-compare">
    <div class="compare-controls"><label>左侧版本<select id="briefVersionLeft"></select></label><label>右侧版本<select id="briefVersionRight"></select></label><button id="restoreBriefVersion" class="button ghost" type="button">恢复左侧版本</button></div>
    <div class="compare-grid"><div id="briefCompareLeft" class="brief-snapshot empty">暂无版本</div><div id="briefCompareRight" class="brief-snapshot empty">暂无版本</div></div>
  </div>
</article>
`.trim();

export function renderBriefHtml(brief, request, escapeHtml) {
  const channel = request?.audience_channel || "男频";
  const genre = request?.genre || "";
  const experiences = (request?.experiences || []).map(escapeHtml).join(" / ") || "自动确定体验";
  return `<div class="brief-grid">
    <div class="brief-block"><h4>频道与题材</h4><p><b>${escapeHtml(channel)}</b><br>${escapeHtml(genre)} · ${experiences}</p></div>
    <div class="brief-block"><h4>核心卖点</h4><ul>${(brief.selling_points || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>
    <div class="brief-block"><h4>主角与主要冲突</h4><p><b>${escapeHtml(brief.protagonist)}</b><br>${escapeHtml(brief.main_conflict)}</p></div>
    <div class="brief-block"><h4>读者契约与核心期待</h4><p>${escapeHtml(brief.reader_contract || "等待方案生成")}</p><p><b>当前期待：</b>${escapeHtml(brief.core_expectation || "等待方案生成")}</p></div>
    <div class="brief-block"><h4>世界规则</h4><ul>${(brief.world_rules || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>
    <div class="brief-block"><h4>连载计划</h4><p>${escapeHtml(brief.update_plan)}<br>预计 ${brief.total_chapters} 章 / ${brief.volume_count} 卷</p></div>
  </div>`;
}

export function mountBriefWorkbench(dashboardRoot) {
  if (!dashboardRoot) return null;
  let workbench = dashboardRoot.querySelector("#briefWorkbench");
  if (workbench) return workbench;
  const hero = dashboardRoot.querySelector(".hero-card");
  const wrapper = document.createElement("div");
  wrapper.innerHTML = BRIEF_WORKBENCH_TEMPLATE;
  workbench = wrapper.firstElementChild;
  if (hero && hero.parentNode) {
    hero.insertAdjacentElement("afterend", workbench);
  } else {
    dashboardRoot.prepend(workbench);
  }
  return workbench;
}
