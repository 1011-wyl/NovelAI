import { formatLocalDate } from "../../core/date.js";
import { formatNumber, formatCompact, formatSeconds, formatDateTime } from "../../core/format.js";
import { escapeHtml as defaultEscapeHtml } from "../../core/dom.js";
import { createChartRuntime } from "../../ui/charts/runtime.js";
import { renderLineChart } from "../../ui/charts/line-chart.js";
import { renderBarChart } from "../../ui/charts/bar-chart.js";
import { renderDonutChart } from "../../ui/charts/donut-chart.js";
import { renderYearHeatmap } from "../../ui/charts/year-heatmap.js";
import { createAnalyticsApi } from "./api.js";
import { createAnalyticsState } from "./state.js";
import { mountAnalyticsTemplate } from "./template.js";
import { createWritingController } from "./writing.js";
import { createLlmController } from "./llm.js";
import { createRecordsController } from "./records.js";

export function createAnalyticsView({ api: request, notify, escapeHtml } = {}) {
  const esc = escapeHtml || defaultEscapeHtml;
  let host = null;
  let root = null;
  let state = null;
  let api = null;
  let charts = null;
  let writing = null;
  let llm = null;
  let records = null;
  let viewActive = false;
  let mounted = false;
  let destroyed = false;
  let listenerAbort = null;

  function isActive() {
    return viewActive && !destroyed;
  }

  function $$(selector) {
    return [...root.querySelectorAll(selector)];
  }

  function $(selector) {
    return root.querySelector(selector);
  }

  function switchTab(tab) {
    state.activeTab = tab;
    $$(".analytics-tab").forEach((btn) => {
      const selected = btn.dataset.tab === tab;
      btn.setAttribute("aria-selected", String(selected));
      btn.tabIndex = selected ? 0 : -1;
    });
    $("#writingPanel").hidden = tab !== "writing";
    $("#llmPanel").hidden = tab !== "llm";
    $("#recordsPanel").hidden = tab !== "records";
    if (!viewActive) return;
    api.abortAll();
    if (tab === "writing") {
      void writing.loadHero();
      void writing.loadDetail();
    } else if (tab === "llm") {
      void llm.load();
    } else {
      void records.loadRecords();
    }
  }

  function refreshCurrentTab() {
    if (!viewActive) return;
    switchTab(state.activeTab);
  }

  function bindEvents() {
    if (listenerAbort) listenerAbort.abort();
    listenerAbort = new AbortController();
    const { signal } = listenerAbort;

    $$(".analytics-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab), { signal });
      btn.addEventListener("keydown", (event) => {
        const tabs = $$(".analytics-tab");
        const index = tabs.indexOf(btn);
        if (event.key === "ArrowRight") {
          event.preventDefault();
          tabs[(index + 1) % tabs.length].focus();
          switchTab(tabs[(index + 1) % tabs.length].dataset.tab);
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          tabs[(index - 1 + tabs.length) % tabs.length].focus();
          switchTab(tabs[(index - 1 + tabs.length) % tabs.length].dataset.tab);
        }
      }, { signal });
    });

    writing.bind(signal);
    llm.bind(signal);
    records.bind(signal);
  }

  function mount(mountHost) {
    if (destroyed) return;
    host = mountHost;
    if (!host) return;
    mountAnalyticsTemplate(host);
    root = host;
    if (mounted) return;

    state = createAnalyticsState();
    api = createAnalyticsApi(request);
    const runtime = createChartRuntime({
      escapeHtml: esc,
      formatCompact,
      formatSeconds,
      formatNumber,
      formatLocalDate,
    });
    charts = {
      runtime,
      renderLineChart,
      renderBarChart,
      renderDonutChart,
      renderYearHeatmap,
    };

    const shared = {
      state,
      api,
      charts,
      root,
      escapeHtml: esc,
      notify,
      formatNumber,
      formatCompact,
      formatSeconds,
      formatDateTime,
      formatLocalDate,
      isActive,
    };

    writing = createWritingController(shared);
    llm = createLlmController(shared);
    records = createRecordsController(shared);

    bindEvents();
    mounted = true;
  }

  function activate() {
    if (destroyed || !mounted) return;
    viewActive = true;
    refreshCurrentTab();
  }

  function deactivate() {
    viewActive = false;
    api?.abortAll();
    records?.clearSearchTimer();
    charts?.runtime.destroyAll();
    charts?.runtime.hideTooltip();
  }

  function refresh() {
    if (destroyed || !mounted) return;
    api?.invalidateFilterOptions();
    refreshCurrentTab();
  }

  function destroy() {
    if (destroyed) return;
    viewActive = false;
    destroyed = true;
    api?.abortAll();
    records?.clearSearchTimer();
    records?.destroy();
    writing?.destroy();
    llm?.destroy();
    charts?.runtime.destroyAll();
    charts?.runtime.hideTooltip();
    if (listenerAbort) {
      listenerAbort.abort();
      listenerAbort = null;
    }
    mounted = false;
  }

  return {
    mount,
    activate,
    deactivate,
    refresh,
    destroy,
  };
}
