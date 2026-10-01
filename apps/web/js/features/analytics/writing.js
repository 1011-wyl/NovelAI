import { toIsoBoundary, buildDefaultRange } from "../../core/date.js";
import {
  computeYearMetrics,
  deriveYears,
  buildWritingTrendModel,
  buildWritingCumulativeModel,
  buildWritingSourceModel,
  buildWritingWeekdayModel,
} from "./selectors.js";

export function createWritingController({
  state,
  api,
  charts,
  root,
  escapeHtml,
  formatNumber,
  isActive,
}) {
  const {
    runtime,
    renderLineChart,
    renderBarChart,
    renderDonutChart,
    renderYearHeatmap,
  } = charts;

  function $(selector) {
    return root.querySelector(selector);
  }

  function $$(selector) {
    return [...root.querySelectorAll(selector)];
  }

  function fillSelect(select, options, allLabel = "全部") {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${allLabel}</option>${(options || []).map((item) => {
      if (typeof item === "string") return `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`;
      return `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label || item.value)}</option>`;
    }).join("")}`;
    if ([...select.options].some((opt) => opt.value === current)) select.value = current;
  }

  function syncWritingFilterInputs() {
    const project = $("#writingProjectFilter");
    const start = $("#writingStartDate");
    const end = $("#writingEndDate");
    if (project) project.value = state.filters.writingProjectId;
    if (start) start.value = state.filters.writingStartDate;
    if (end) end.value = state.filters.writingEndDate;
  }

  function renderWritingHero() {
    const hero = state.writingHero;
    const year = state.selectedYear;
    const metrics = computeYearMetrics(hero?.time_series, hero?.summary);
    $("#metricActiveDays").textContent = formatNumber(metrics.activeDays);
    $("#metricStreakDays").textContent = formatNumber(metrics.streakDays);
    $("#metricChapters").textContent = formatNumber(metrics.chapters);
    $("#metricTotalWords").textContent = formatNumber(metrics.totalWords);
    $("#writingYearActiveDays").textContent = `${year} 年创作了 ${formatNumber(metrics.activeDays)} 天`;
    $("#writingYearTotalWords").textContent = `${year} 年共创作 ${formatNumber(metrics.totalWords)} 字`;

    const days = (hero?.time_series || []).map((item) => ({
      date: item.date,
      value: Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0) + (item.import_word_delta || 0)),
    }));
    renderYearHeatmap($("#writingHeatmap"), { year, days }, runtime);

    const yearList = $("#writingYearList");
    yearList.innerHTML = state.availableYears.map((y) => `<button type="button" class="writing-year-btn" role="option" aria-selected="${y === year}" data-year="${y}">${y}</button>`).join("");
    $$(".writing-year-btn").forEach((btn) => btn.addEventListener("click", () => {
      state.selectedYear = Number(btn.dataset.year);
      void loadHero();
    }));
  }

  function renderWritingCharts() {
    const points = state.writingDetail?.time_series || [];
    renderBarChart($("#chartWritingTrend"), buildWritingTrendModel(points), runtime);
    renderLineChart($("#chartWritingCumulative"), buildWritingCumulativeModel(points), runtime);
    renderDonutChart($("#chartWritingSource"), buildWritingSourceModel(points), runtime);
    renderBarChart($("#chartWritingWeekday"), buildWritingWeekdayModel(points), runtime);
  }

  async function loadHero() {
    const year = state.selectedYear;
    const query = new URLSearchParams({
      timezone: state.timezone,
      start_at: `${year}-01-01T00:00:00`,
      end_at: `${year}-12-31T23:59:59`,
    });
    runtime.renderChartState($("#writingHeatmap"), { loading: true });
    try {
      const data = await api.loadWriting(query, "writingHero");
      if (!isActive() || state.activeTab !== "writing") return;
      state.writingHero = data;
      state.availableYears = deriveYears(data.time_series);
      if (!state.availableYears.includes(state.selectedYear)) {
        state.selectedYear = state.availableYears[0];
      }
      renderWritingHero();
      try {
        const options = await api.ensureFilterOptions();
        state.filterOptions = options;
        fillSelect($("#writingProjectFilter"), options?.project_options || []);
      } catch {
        /* options are optional for hero view */
      }
    } catch (error) {
      if (error.stale) return;
      runtime.renderChartState($("#writingHeatmap"), {
        error: error.message || "加载失败",
        onRetry: () => void loadHero(),
      });
    }
  }

  async function loadDetail() {
    const query = new URLSearchParams({ timezone: state.timezone });
    if (state.filters.writingProjectId) query.set("project_id", state.filters.writingProjectId);
    if (state.filters.writingStartDate) query.set("start_at", toIsoBoundary(state.filters.writingStartDate, "start"));
    if (state.filters.writingEndDate) query.set("end_at", toIsoBoundary(state.filters.writingEndDate, "end"));

    ["#chartWritingTrend", "#chartWritingCumulative", "#chartWritingSource", "#chartWritingWeekday"].forEach((sel) => {
      runtime.renderChartState($(sel), { loading: true });
    });
    try {
      const data = await api.loadWriting(query, "writingDetail");
      if (!isActive() || state.activeTab !== "writing") return;
      state.writingDetail = data;
      const options = state.filterOptions || (await api.ensureFilterOptions().catch(() => null));
      if (options) state.filterOptions = options;
      fillSelect($("#writingProjectFilter"), options?.project_options || []);
      renderWritingCharts();
    } catch (error) {
      if (error.stale) return;
      const retry = () => void loadDetail();
      ["#chartWritingTrend", "#chartWritingCumulative", "#chartWritingSource", "#chartWritingWeekday"].forEach((sel) => {
        runtime.renderChartState($(sel), { error: error.message || "加载失败", onRetry: retry });
      });
    }
  }

  function resetFilters() {
    const range = buildDefaultRange();
    state.filters.writingProjectId = "";
    state.filters.writingStartDate = range.start;
    state.filters.writingEndDate = range.end;
    syncWritingFilterInputs();
    void loadDetail();
  }

  function bind(signal) {
    const opts = signal ? { signal } : undefined;
    $("#writingProjectFilter")?.addEventListener("change", (event) => {
      state.filters.writingProjectId = event.target.value;
      void loadDetail();
    }, opts);
    $("#writingStartDate")?.addEventListener("change", (event) => {
      state.filters.writingStartDate = event.target.value;
      void loadDetail();
    }, opts);
    $("#writingEndDate")?.addEventListener("change", (event) => {
      state.filters.writingEndDate = event.target.value;
      void loadDetail();
    }, opts);
    $("#writingFilterReset")?.addEventListener("click", resetFilters, opts);
    syncWritingFilterInputs();
  }

  function refresh() {
    void loadHero();
    void loadDetail();
  }

  function destroy() {
    /* listeners removed via AbortSignal from view */
  }

  return {
    loadHero,
    loadDetail,
    bind,
    refresh,
    resetFilters,
    syncWritingFilterInputs,
    destroy,
  };
}
