export const ANALYTICS_TEMPLATE = `
          <div class="analytics-shell">
            <header class="analytics-header">
              <h1 id="analyticsTitle">仪表盘</h1>
            </header>
            <div class="analytics-tabs" role="tablist" aria-label="仪表盘分类">
              <button type="button" class="analytics-tab" role="tab" id="tabWriting" aria-selected="true" aria-controls="writingPanel" tabindex="0" data-tab="writing">写作</button>
              <button type="button" class="analytics-tab" role="tab" id="tabLlm" aria-selected="false" aria-controls="llmPanel" tabindex="-1" data-tab="llm">LLM 统计</button>
              <button type="button" class="analytics-tab" role="tab" id="tabRecords" aria-selected="false" aria-controls="recordsPanel" tabindex="-1" data-tab="records">调用记录</button>
            </div>

            <div id="writingPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabWriting">
              <div class="writing-hero">
                <article class="analytics-card writing-heatmap-card">
                  <div class="writing-heatmap-head">
                    <div class="writing-year-list" id="writingYearList" role="listbox" aria-label="选择年份"></div>
                    <div class="writing-heatmap-copy">
                      <p id="writingYearActiveDays" class="writing-hero-line">— 年创作了 0 天</p>
                      <div id="writingHeatmap" class="chart-host chart-host-heatmap" aria-label="年度创作热力日历"></div>
                      <p id="writingYearTotalWords" class="writing-hero-line muted">— 年共创作 0 字</p>
                      <div class="heatmap-legend" aria-hidden="true">
                        <span>少</span>
                        <span class="heatmap-legend-cell level-0"></span>
                        <span class="heatmap-legend-cell level-1"></span>
                        <span class="heatmap-legend-cell level-2"></span>
                        <span class="heatmap-legend-cell level-3"></span>
                        <span>多</span>
                      </div>
                    </div>
                  </div>
                </article>
                <div class="writing-metric-grid" id="writingYearMetrics">
                  <article class="analytics-metric-card"><span>总创作天数</span><strong id="metricActiveDays">0</strong></article>
                  <article class="analytics-metric-card"><span>连续创作天数</span><strong id="metricStreakDays">0</strong></article>
                  <article class="analytics-metric-card"><span>总创作章节</span><strong id="metricChapters">0</strong></article>
                  <article class="analytics-metric-card"><span>总创作字数</span><strong id="metricTotalWords">0</strong></article>
                </div>
              </div>
              <article class="analytics-card analytics-filter-card">
                <div class="writing-filter-grid">
                  <label>项目<select id="writingProjectFilter"><option value="">全部</option></select></label>
                  <label>开始日期<input id="writingStartDate" type="date"></label>
                  <label>结束日期<input id="writingEndDate" type="date"></label>
                  <button type="button" class="button ghost" id="writingFilterReset">重置</button>
                </div>
              </article>
              <div class="analytics-chart-grid writing-chart-grid">
                <article class="analytics-card analytics-chart-card"><h3>写作字数变化</h3><div id="chartWritingTrend" class="chart-host"></div></article>
                <article class="analytics-card analytics-chart-card"><h3>累计创作字数</h3><div id="chartWritingCumulative" class="chart-host"></div></article>
                <article class="analytics-card analytics-chart-card"><h3>来源贡献占比</h3><div id="chartWritingSource" class="chart-host"></div></article>
                <article class="analytics-card analytics-chart-card"><h3>创作活跃日分布</h3><div id="chartWritingWeekday" class="chart-host"></div></article>
              </div>
            </div>

            <div id="llmPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabLlm" hidden>
              <div class="llm-metric-grid" id="llmMetricCards">
                <article class="analytics-metric-card"><span>LLM 调用次数</span><strong id="llmCallsTotal">0</strong><small id="llmCallsSuccess">完成 0 次</small></article>
                <article class="analytics-metric-card"><span>Token 消耗</span><strong id="llmTokensTotal">0</strong><small id="llmTokensSplit">输入 0 / 输出 0</small></article>
                <article class="analytics-metric-card"><span>平均响应时间</span><strong id="llmAvgLatency">—</strong><small>秒</small></article>
                <article class="analytics-metric-card"><span>首字响应时间</span><strong id="llmAvgFirstToken">—</strong><small id="llmFirstTokenHint">当前模型调用为非流式</small></article>
              </div>
              <div class="analytics-chart-grid llm-chart-grid">
                <article class="analytics-card analytics-chart-card span-4"><h3>调用趋势</h3><div id="chartLlmCallTrend" class="chart-host chart-host-wide"></div></article>
                <article class="analytics-card analytics-chart-card span-2"><h3>模型调用次数分布</h3><div id="chartLlmModelCalls" class="chart-host"></div></article>
                <article class="analytics-card analytics-chart-card span-2"><h3>模型消耗分布</h3><div id="chartLlmModelTokens" class="chart-host"></div></article>
                <article class="analytics-card analytics-chart-card span-4"><h3>消耗趋势</h3><div id="chartLlmTokenTrend" class="chart-host chart-host-wide"></div></article>
                <article class="analytics-card analytics-chart-card span-4"><h3>响应时间趋势</h3><div id="chartLlmLatencyTrend" class="chart-host chart-host-wide"></div></article>
                <article class="analytics-card analytics-chart-card span-2"><h3>总消耗分布</h3><div id="chartLlmProjectTokens" class="chart-host"></div></article>
              </div>
            </div>

            <div id="recordsPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabRecords" hidden>
              <article class="analytics-card analytics-filter-card">
                <div class="records-filter-layout">
                  <div class="records-filter-row records-filter-row-primary">
                    <label>项目<select id="recordsProjectFilter"><option value="">全部</option></select></label>
                    <label>模型<select id="recordsModelFilter"><option value="">全部</option></select></label>
                    <label>提供商<select id="recordsProviderFilter"><option value="">全部</option></select></label>
                    <label>类型<select id="recordsCategoryFilter"><option value="">全部</option></select></label>
                    <label>状态<select id="recordsStatusFilter"><option value="">全部</option></select></label>
                  </div>
                  <div class="records-filter-row records-filter-row-secondary">
                    <label>开始日期<input id="recordsStartDate" type="date"></label>
                    <label>结束日期<input id="recordsEndDate" type="date"></label>
                    <label>搜索<input id="recordsSearch" type="search" placeholder="模型、操作、类型或错误信息" autocomplete="off"></label>
                    <button type="button" class="button ghost" id="recordsFilterReset">重置</button>
                  </div>
                </div>
              </article>
              <article class="analytics-card analytics-record-card" id="recordsTableCard">
                <div class="records-table-wrap">
                  <table class="records-table" id="recordsTable">
                    <thead>
                      <tr>
                        <th><button type="button" class="records-sort" data-sort="created_at">时间</button></th>
                        <th>项目</th>
                        <th>模型</th>
                        <th>操作</th>
                        <th><button type="button" class="records-sort" data-sort="latency_ms">用时</button></th>
                        <th><button type="button" class="records-sort" data-sort="first_token_ms">首字</button></th>
                        <th><button type="button" class="records-sort" data-sort="tokens_input">输入（缓存）</button></th>
                        <th><button type="button" class="records-sort" data-sort="tokens_output">输出</button></th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody id="recordsTableBody"></tbody>
                  </table>
                </div>
                <div class="records-pagination" id="recordsPagination">
                  <span id="recordsRangeText">第 0–0 条，共 0 条</span>
                  <div class="records-pagination-controls" id="recordsPaginationControls"></div>
                </div>
              </article>
            </div>
          </div>
`;

export function mountAnalyticsTemplate(host) {
  if (!host) return;
  if (host.querySelector(".analytics-shell")) return;
  host.innerHTML = ANALYTICS_TEMPLATE;
}
