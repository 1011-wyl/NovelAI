export const NOVEL_CREATE_TEMPLATE = `
<form id="createForm" class="form-layout">
  <article class="panel form-main">
    <p class="eyebrow">新建小说</p>
    <h2>用标签确定方向</h2>
    <p class="muted">标签会转换成可执行规则，并在每章写作前后参与检查。</p>
    <fieldset><legend>读者频道</legend><div class="channel-switch">
      <label><input type="radio" name="audience_channel" value="男频" checked><span>男频</span><small>目标推进、升级反馈、世界探索</small></label>
      <label><input type="radio" name="audience_channel" value="女频"><span>女频</span><small>人物成长、情感因果、关系变化</small></label>
    </div></fieldset>
    <label>主类型
      <select id="genreSelect" name="genre" required></select>
    </label>
    <label>书名（可选）<input name="preferred_title" maxlength="80" placeholder="留空则由智能体生成多个候选书名"></label>
    <fieldset><legend>阅读体验（可多选）</legend><div class="chips" data-check-group="experiences"></div></fieldset>
    <fieldset><legend>核心元素（可多选）</legend><div class="chips" data-check-group="elements"></div></fieldset>
    <fieldset><legend>主角设定（可多选）</legend><div class="chips" data-check-group="protagonist_tags"></div></fieldset>
    <p id="tagCatalogNote" class="catalog-note"></p>
    <label>你的核心想法
      <textarea name="idea" required rows="5" placeholder="例如：主角是一名仓储管理员，没有无限空间，只能依靠职业经验和有限资源建立社区。"></textarea>
    </label>
  </article>
  <aside class="panel form-side">
    <p class="eyebrow">约束</p>
    <h3>约束与更新计划</h3>
    <label>必须包含 <input name="must_have" placeholder="逗号分隔"></label>
    <label>希望包含 <input name="nice_to_have" placeholder="逗号分隔"></label>
    <label>明确不要 <input name="exclude" placeholder="如：过度血腥, 悲剧结局"></label>
    <label>感情线
      <select id="romanceSelect" name="romance"></select>
    </label>
    <div class="field-row"><label>单章目标字数<input name="chapter_target_chars" type="number" min="800" max="8000" value="2200"></label><label>每日章节<input name="daily_chapters" type="number" min="1" max="20" value="2"></label></div>
    <label>储备安全线<input name="reserve_target" type="number" min="1" max="50" value="5"></label>
    <label class="toggle"><input name="require_plan_confirmation" type="checkbox" checked><span>生成方案后由我确认一次</span></label>
    <button class="button primary wide" type="submit">生成创作方案</button>
  </aside>
</form>
`.trim();

export function mountNovelCreateTemplate(host) {
  if (!host) return null;
  const existing = host.querySelector("#createForm");
  if (existing) return existing;
  host.innerHTML = NOVEL_CREATE_TEMPLATE;
  return host.querySelector("#createForm");
}
