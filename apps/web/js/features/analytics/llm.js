import {
  buildModelTrend,
  buildTokenTrend,
  buildLlmModelCallsDonut,
  buildLlmModelTokensDonut,
  buildLlmProjectTokensDonut,
} from "./selectors.js";

export function createLlmController({
  state,
  api,
  charts,
  root,
  formatNumber,
  formatCompact,
  formatSeconds,
  isActive,
}) {
  const {
    runtime,
    renderLineChart,
    renderBarChart,
    renderDonutChart,
  } = charts;

  function $(selector) {
    return root.querySelector(selector);
  }

  function renderLlmTab() {
    const stats = state.llmStats;
    if (!stats) return;
    const summary = stats.summary || {};
    $("#llmCallsTotal").textContent = formatNumber(summary.calls_total || 0);
    $("#llmCallsSuccess").textContent = `完成 ${formatNumber(summary.success_total || 0)} 次`;
    $("#llmTokensTotal").textContent = formatCompact(summary.tokens_total || 0);
    $("#llmTokensSplit").textContent = `输入 ${formatCompact(summary.tokens_input_total || 0)} / 输出 ${formatCompact(summary.tokens_output_total || 0)}`;
    $("#llmAvgLatency").textContent = summary.avg_latency_ms == null ? "—" : formatSeconds(summary.avg_latency_ms);
    $("#llmAvgFirstToken").textContent = summary.avg_first_token_ms == null ? "—" : formatSeconds(summary.avg_first_token_ms);

    renderLineChart($("#chartLlmCallTrend"), buildModelTrend(stats, "calls"), runtime);
    renderDonutChart($("#chartLlmModelCalls"), buildLlmModelCallsDonut(stats.by_model), runtime);
    renderDonutChart($("#chartLlmModelTokens"), buildLlmModelTokensDonut(stats.by_model), runtime);
    renderBarChart($("#chartLlmTokenTrend"), buildTokenTrend(stats), runtime);
    renderLineChart($("#chartLlmLatencyTrend"), buildModelTrend(stats, "avg_latency_ms"), runtime);
    renderDonutChart($("#chartLlmProjectTokens"), buildLlmProjectTokensDonut(stats.by_project), runtime);
  }

  async function load() {
    [
      "#chartLlmCallTrend",
      "#chartLlmModelCalls",
      "#chartLlmModelTokens",
      "#chartLlmTokenTrend",
      "#chartLlmLatencyTrend",
      "#chartLlmProjectTokens",
    ].forEach((sel) => runtime.renderChartState($(sel), { loading: true }));
    try {
      const data = await api.loadLlmStats();
      if (!isActive() || state.activeTab !== "llm") return;
      state.llmStats = data;
      state.filterOptions = data.options;
      renderLlmTab();
    } catch (error) {
      if (error.stale) return;
      const retry = () => void load();
      [
        "#chartLlmCallTrend",
        "#chartLlmModelCalls",
        "#chartLlmModelTokens",
        "#chartLlmTokenTrend",
        "#chartLlmLatencyTrend",
        "#chartLlmProjectTokens",
      ].forEach((sel) => {
        runtime.renderChartState($(sel), { error: error.message || "加载失败", onRetry: retry });
      });
    }
  }

  function bind() {
    /* LLM tab has no filter UI bindings */
  }

  function refresh() {
    void load();
  }

  function destroy() {
    /* no owned listeners */
  }

  return {
    load,
    bind,
    refresh,
    destroy,
    renderLlmTab,
  };
}
