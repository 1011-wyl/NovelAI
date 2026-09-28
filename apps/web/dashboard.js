(() => {
  "use strict";

  const CHART_COLORS = ["#315f46", "#6f9a7f", "#5b8def", "#c27c3a", "#8b5cf6", "#d14343"];
  const CATEGORY_LABELS = { agent: "智能体", memory: "记忆", session: "会话" };
  const OPERATION_LABELS = {
    create_brief: "生成方案",
    revise_brief: "修订方案",
    plan_chapter: "章节规划",
    plan_chapter_candidates: "候选规划",
    select_chapter_plan: "选定规划",
    write_chapter: "章节写作",
    deslop_chapter: "去 AI 味",
    extract_characters: "提取人物",
    review_continuity: "连贯审核",
    review_readability: "可读审核",
    revise_chapter: "章节修订",
    llm_call: "模型调用",
  };
  const STATUS_LABELS = { success: "成功", failed: "失败", error: "失败", cancelled: "已取消", running: "进行中" };

  let deps = {};
  let viewActive = false;
  let searchTimer = null;
  let tooltipEl = null;

  const state = {
    activeTab: "writing",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    selectedYear: new Date().getFullYear(),
    availableYears: [],
    writingHero: null,
    writingDetail: null,
    llmStats: null,
    records: null,
    filterOptions: null,
    filters: {
      writingProjectId: "",
      writingStartDate: "",
      writingEndDate: "",
      recordsProjectId: "",
      recordsModelId: "",
      recordsProvider: "",
      recordsCategory: "",
      recordsStatus: "",
      recordsStartDate: "",
      recordsEndDate: "",
      recordsSearch: "",
      recordsPage: 1,
      recordsPageSize: 20,
      recordsSortBy: "created_at",
      recordsSortOrder: "desc",
    },
  };

  const controllers = {
    writingHero: null,
    writingDetail: null,
    llm: null,
    records: null,
    options: null,
  };
  const requestIds = {
    writingHero: 0,
    writingDetail: 0,
    llm: 0,
    records: 0,
    options: 0,
  };

  const chartCleanups = new WeakMap();

  function $(selector) {
    return document.querySelector(selector);
  }

  function $$(selector) {
    return [...document.querySelectorAll(selector)];
  }

  function esc(value) {
    return deps.escapeHtml ? deps.escapeHtml(value) : String(value ?? "");
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("zh-CN").format(Math.round(Number(value) || 0));
  }

  function formatCompact(value) {
    const n = Number(value) || 0;
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}m`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return formatNumber(n);
  }

  function formatSeconds(ms) {
    if (ms === null || ms === undefined) return "—";
    return (Number(ms) / 1000).toFixed(2);
  }

  function formatDateTime(value) {
    if (!value) return "—";
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }

  function formatLocalDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function buildDefaultRange() {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 29);
    return { start: formatLocalDate(start), end: formatLocalDate(end) };
  }

  function toIsoBoundary(date, boundary) {
    if (!date) return undefined;
    return `${date}T${boundary === "start" ? "00:00:00" : "23:59:59"}`;
  }

  function abortKey(key) {
    if (controllers[key]) {
      controllers[key].abort();
      controllers[key] = null;
    }
  }

  function abortAll() {
    Object.keys(controllers).forEach(abortKey);
  }

  async function fetchJson(path, key) {
    abortKey(key);
    const controller = new AbortController();
    controllers[key] = controller;
    const id = ++requestIds[key];
    try {
      const payload = await deps.api(path, { signal: controller.signal });
      if (id !== requestIds[key]) {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      throw error;
    }
  }

  async function ensureFilterOptions() {
    if (state.filterOptions) return state.filterOptions;
    const data = await fetchJson("/api/dashboard/llm-api/stats", "options");
    state.filterOptions = data.options;
    return state.filterOptions;
  }

  function ensureTooltip() {
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.className = "chart-tooltip";
      tooltipEl.setAttribute("role", "tooltip");
      document.body.appendChild(tooltipEl);
    }
    return tooltipEl;
  }

  function showTooltip(text, x, y) {
    const el = ensureTooltip();
    el.textContent = text;
    el.style.left = `${x + 12}px`;
    el.style.top = `${y + 12}px`;
    el.classList.add("visible");
  }

  function hideTooltip() {
    tooltipEl?.classList.remove("visible");
  }

  function cleanupContainer(container) {
    const cleanup = chartCleanups.get(container);
    if (cleanup) cleanup();
    chartCleanups.delete(container);
    hideTooltip();
    container.innerHTML = "";
  }

  function observeResize(container, render) {
    let frame = null;
    const run = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(render);
    };
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(run);
      observer.observe(container);
      chartCleanups.set(container, () => observer.disconnect());
    } else {
      const onResize = () => run();
      window.addEventListener("resize", onResize);
      chartCleanups.set(container, () => window.removeEventListener("resize", onResize));
    }
  }

  function renderChartState(container, { loading = false, error = "", empty = false, onRetry = null } = {}) {
    cleanupContainer(container);
    const wrap = document.createElement("div");
    if (loading) {
      wrap.className = "chart-state";
      wrap.textContent = "正在加载…";
    } else if (error) {
      wrap.className = "chart-error";
      wrap.innerHTML = `<span>${esc(error)}</span>`;
      if (onRetry) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "button ghost";
        btn.textContent = "重试";
        btn.addEventListener("click", onRetry);
        wrap.appendChild(btn);
      }
    } else if (empty) {
      wrap.className = "chart-empty";
      wrap.textContent = "该指标暂无统计数据";
    }
    container.appendChild(wrap);
  }

  function monthDayLabel(dateStr) {
    if (!dateStr) return "";
    const parts = dateStr.split("-");
    return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : dateStr;
  }

  function chartHasPositiveValues(rows, keys) {
    return (rows || []).some((row) => (keys || []).some((key) => Number(row[key]) > 0));
  }

  function renderLineChart(container, model) {
    cleanupContainer(container);
    const series = model?.series || [];
    const allPoints = series.flatMap((s) => s.data || []);
    const hasValue = allPoints.some((p) => Number(p.y) > 0);
    if (!allPoints.length || !hasValue) {
      renderChartState(container, { empty: true });
      return;
    }

    const render = () => {
      const width = Math.max(container.clientWidth || 320, 280);
      const height = Math.max(container.clientHeight || 300, 300);
      const pad = { top: 16, right: 16, bottom: 36, left: 48 };
      const innerW = width - pad.left - pad.right;
      const innerH = height - pad.top - pad.bottom;
      const labels = [...new Set(allPoints.map((p) => p.x))].sort();
      const maxY = Math.max(...allPoints.map((p) => Number(p.y) || 0), 1);
      const xAt = (index) => pad.left + (labels.length <= 1 ? innerW / 2 : (index / (labels.length - 1)) * innerW);
      const yAt = (value) => pad.top + innerH - (Math.max(0, value) / maxY) * innerH;

      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("role", "img");

      const axis = document.createElementNS(svgNS, "g");
      axis.setAttribute("stroke", "var(--ui-border)");
      axis.innerHTML = `<line x1="${pad.left}" y1="${pad.top + innerH}" x2="${pad.left + innerW}" y2="${pad.top + innerH}" /><line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + innerH}" />`;
      svg.appendChild(axis);

      labels.forEach((label, index) => {
        if (index % Math.ceil(labels.length / 6) !== 0 && index !== labels.length - 1) return;
        const text = document.createElementNS(svgNS, "text");
        text.setAttribute("x", String(xAt(index)));
        text.setAttribute("y", String(height - 8));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("fill", "var(--ui-muted)");
        text.setAttribute("font-size", "11");
        text.textContent = monthDayLabel(label);
        svg.appendChild(text);
      });

      series.forEach((item, seriesIndex) => {
        const color = item.color || CHART_COLORS[seriesIndex % CHART_COLORS.length];
        const points = labels.map((label, index) => {
          const found = (item.data || []).find((p) => p.x === label);
          const y = found ? Number(found.y) || 0 : 0;
          return { x: xAt(index), y: yAt(y), rawY: y, label };
        });
        const pathData = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
        const path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", pathData);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", color);
        path.setAttribute("stroke-width", "2");
        svg.appendChild(path);

        if (model.enableArea) {
          const area = document.createElementNS(svgNS, "path");
          const areaData = `${pathData} L ${points[points.length - 1].x} ${pad.top + innerH} L ${points[0].x} ${pad.top + innerH} Z`;
          area.setAttribute("d", areaData);
          area.setAttribute("fill", color);
          area.setAttribute("opacity", "0.12");
          svg.insertBefore(area, path);
        }

        points.forEach((p) => {
          const dot = document.createElementNS(svgNS, "circle");
          dot.setAttribute("cx", String(p.x));
          dot.setAttribute("cy", String(p.y));
          dot.setAttribute("r", "3");
          dot.setAttribute("fill", color);
          dot.addEventListener("mouseenter", (event) => {
            const valueText = model.valueFormat === "seconds" ? `${formatSeconds(p.rawY * (model.rawMs ? 1 : 1000))} 秒` : formatCompact(p.rawY);
            showTooltip(`${item.label || ""} ${monthDayLabel(p.label)}：${valueText}`, event.clientX, event.clientY);
          });
          dot.addEventListener("mousemove", (event) => showTooltip(`${item.label || ""} ${monthDayLabel(p.label)}：${model.valueFormat === "seconds" ? `${formatSeconds(p.rawY * (model.rawMs ? 1 : 1000))} 秒` : formatCompact(p.rawY)}`, event.clientX, event.clientY));
          dot.addEventListener("mouseleave", hideTooltip);
          svg.appendChild(dot);
        });
      });

      container.innerHTML = "";
      container.appendChild(svg);

      if (model.legend !== false) {
        const legend = document.createElement("div");
        legend.className = "chart-legend";
        legend.innerHTML = series.map((item, index) => {
          const color = item.color || CHART_COLORS[index % CHART_COLORS.length];
          return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${esc(item.label || `系列 ${index + 1}`)}</span>`;
        }).join("");
        container.appendChild(legend);
      }
    };

    observeResize(container, render);
    render();
  }

  function renderBarChart(container, model) {
    cleanupContainer(container);
    const data = model?.data || [];
    const keys = model?.keys || [];
    if (!data.length || !keys.length || !chartHasPositiveValues(data, keys)) {
      renderChartState(container, { empty: true });
      return;
    }

    const render = () => {
      const width = Math.max(container.clientWidth || 320, 280);
      const height = Math.max(container.clientHeight || 300, 300);
      const pad = { top: 16, right: 16, bottom: 36, left: 48 };
      const innerW = width - pad.left - pad.right;
      const innerH = height - pad.top - pad.bottom;
      const maxY = Math.max(...data.flatMap((row) => keys.map((key) => Number(row[key]) || 0)), 1);
      const groupWidth = innerW / Math.max(data.length, 1);
      const barGap = Math.min(8, groupWidth * 0.15);
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

      const axis = document.createElementNS(svgNS, "g");
      axis.setAttribute("stroke", "var(--ui-border)");
      axis.innerHTML = `<line x1="${pad.left}" y1="${pad.top + innerH}" x2="${pad.left + innerW}" y2="${pad.top + innerH}" /><line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + innerH}" />`;
      svg.appendChild(axis);

      data.forEach((row, rowIndex) => {
        const groupX = pad.left + rowIndex * groupWidth + barGap / 2;
        let stackTop = pad.top + innerH;
        keys.forEach((key, keyIndex) => {
          const value = Number(row[key]) || 0;
          const barH = (value / maxY) * innerH;
          const barW = model.groupMode === "stacked" ? groupWidth - barGap : (groupWidth - barGap) / keys.length - 2;
          const x = model.groupMode === "stacked" ? groupX : groupX + keyIndex * (barW + 2);
          let y;
          if (model.groupMode === "stacked") {
            stackTop -= barH;
            y = stackTop;
          } else {
            y = pad.top + innerH - barH;
          }
          const rect = document.createElementNS(svgNS, "rect");
          rect.setAttribute("x", String(x));
          rect.setAttribute("y", String(y));
          rect.setAttribute("width", String(Math.max(barW, 2)));
          rect.setAttribute("height", String(Math.max(barH, value > 0 ? 2 : 0)));
          rect.setAttribute("fill", model.keyColors?.[key] || CHART_COLORS[keyIndex % CHART_COLORS.length]);
          rect.setAttribute("rx", "2");
          const label = model.keyLabels?.[key] || key;
          rect.addEventListener("mouseenter", (event) => showTooltip(`${row.label} · ${label}：${formatCompact(value)}`, event.clientX, event.clientY));
          rect.addEventListener("mousemove", (event) => showTooltip(`${row.label} · ${label}：${formatCompact(value)}`, event.clientX, event.clientY));
          rect.addEventListener("mouseleave", hideTooltip);
          svg.appendChild(rect);
        });

        if (rowIndex % Math.ceil(data.length / 6) === 0 || rowIndex === data.length - 1) {
          const text = document.createElementNS(svgNS, "text");
          text.setAttribute("x", String(groupX + (groupWidth - barGap) / 2));
          text.setAttribute("y", String(height - 8));
          text.setAttribute("text-anchor", "middle");
          text.setAttribute("fill", "var(--ui-muted)");
          text.setAttribute("font-size", "11");
          text.textContent = monthDayLabel(row.label);
          svg.appendChild(text);
        }
      });

      container.innerHTML = "";
      container.appendChild(svg);

      const legend = document.createElement("div");
      legend.className = "chart-legend";
      legend.innerHTML = keys.map((key, index) => {
        const color = model.keyColors?.[key] || CHART_COLORS[index % CHART_COLORS.length];
        return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${esc(model.keyLabels?.[key] || key)}</span>`;
      }).join("");
      container.appendChild(legend);
    };

    observeResize(container, render);
    render();
  }

  function renderDonutChart(container, model) {
    cleanupContainer(container);
    const data = (model?.data || []).filter((item) => Number(item.value) > 0);
    if (!data.length) {
      renderChartState(container, { empty: true });
      return;
    }

    const render = () => {
      const size = Math.min(Math.max(container.clientWidth || 280, 220), Math.min(container.clientHeight || 300, 280));
      const stroke = 28;
      const radius = (size - stroke) / 2;
      const cx = size / 2;
      const cy = size / 2;
      const total = data.reduce((sum, item) => sum + Number(item.value), 0);
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
      let angle = -Math.PI / 2;

      data.forEach((item, index) => {
        const value = Number(item.value) || 0;
        const slice = (value / total) * Math.PI * 2;
        const x1 = cx + radius * Math.cos(angle);
        const y1 = cy + radius * Math.sin(angle);
        angle += slice;
        const x2 = cx + radius * Math.cos(angle);
        const y2 = cy + radius * Math.sin(angle);
        const large = slice > Math.PI ? 1 : 0;
        const path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", `M ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2}`);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", item.color || CHART_COLORS[index % CHART_COLORS.length]);
        path.setAttribute("stroke-width", String(stroke));
        path.setAttribute("stroke-linecap", "butt");
        path.addEventListener("mouseenter", (event) => showTooltip(`${item.label}：${formatCompact(value)} (${((value / total) * 100).toFixed(1)}%)`, event.clientX, event.clientY));
        path.addEventListener("mousemove", (event) => showTooltip(`${item.label}：${formatCompact(value)} (${((value / total) * 100).toFixed(1)}%)`, event.clientX, event.clientY));
        path.addEventListener("mouseleave", hideTooltip);
        svg.appendChild(path);
      });

      const center = document.createElementNS(svgNS, "text");
      center.setAttribute("x", String(cx));
      center.setAttribute("y", String(cy + 4));
      center.setAttribute("text-anchor", "middle");
      center.setAttribute("fill", "var(--ui-text)");
      center.setAttribute("font-size", "16");
      center.setAttribute("font-weight", "700");
      center.textContent = formatCompact(total);
      svg.appendChild(center);

      container.innerHTML = "";
      container.appendChild(svg);

      const legend = document.createElement("div");
      legend.className = "chart-legend";
      legend.innerHTML = data.map((item, index) => {
        const color = item.color || CHART_COLORS[index % CHART_COLORS.length];
        return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${esc(item.label)}</span>`;
      }).join("");
      container.appendChild(legend);
    };

    observeResize(container, render);
    render();
  }

  function heatLevel(value) {
    if (value <= 0) return 0;
    if (value < 500) return 1;
    if (value < 2000) return 2;
    if (value < 5000) return 3;
    return 4;
  }

  function renderYearHeatmap(container, model) {
    cleanupContainer(container);
    const year = Number(model.year);
    const dayMap = new Map((model.days || []).map((item) => [item.date, item.value]));
    const start = new Date(year, 0, 1);
    const end = new Date(year, 11, 31);
    const cursor = new Date(start);
    cursor.setDate(cursor.getDate() - ((cursor.getDay() + 6) % 7)); // Monday-aligned

    const calendar = document.createElement("div");
    calendar.className = "heatmap-calendar";

    const weekdays = document.createElement("div");
    weekdays.className = "heatmap-weekday-labels";
    weekdays.innerHTML = "<span>一</span><span></span><span>三</span><span></span><span>五</span><span></span><span>日</span>";
    calendar.appendChild(weekdays);

    const main = document.createElement("div");
    main.className = "heatmap-calendar-main";
    const monthLabels = document.createElement("div");
    monthLabels.className = "heatmap-month-labels";
    const weeks = document.createElement("div");
    weeks.className = "heatmap-weeks";

    const monthSeen = new Set();
    for (let weekIndex = 0; weekIndex < 54; weekIndex += 1) {
      if (cursor > end && ((cursor.getDay() + 6) % 7) === 0) break;
      const week = document.createElement("div");
      week.className = "heatmap-week";
      let monthLabel = "";
      for (let i = 0; i < 7; i += 1) {
        const btn = document.createElement("button");
        btn.type = "button";
        const inYear = cursor.getFullYear() === year;
        if (!inYear) {
          btn.className = "heatmap-day is-empty";
          btn.tabIndex = -1;
          btn.setAttribute("aria-hidden", "true");
        } else {
          const date = formatLocalDate(cursor);
          const value = dayMap.get(date) || 0;
          btn.className = `heatmap-day level-${heatLevel(value)}`;
          btn.title = `${date}：${formatNumber(value)} 字`;
          btn.setAttribute("aria-label", `${date} 创作 ${formatNumber(value)} 字`);
          if (!monthSeen.has(cursor.getMonth()) && cursor.getDate() <= 7) {
            monthSeen.add(cursor.getMonth());
            monthLabel = `${cursor.getMonth() + 1}月`;
          }
        }
        week.appendChild(btn);
        cursor.setDate(cursor.getDate() + 1);
      }
      const label = document.createElement("span");
      label.textContent = monthLabel;
      monthLabels.appendChild(label);
      weeks.appendChild(week);
    }

    main.appendChild(monthLabels);
    main.appendChild(weeks);
    calendar.appendChild(main);

    const wrap = document.createElement("div");
    wrap.className = "heatmap-months";
    wrap.appendChild(calendar);
    container.appendChild(wrap);
  }

  function computeYearMetrics(timeSeries, summary) {
    const creativeDays = [];
    let totalWords = 0;
    (timeSeries || []).forEach((item) => {
      const creative = Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
      if (creative > 0) creativeDays.push(item.date);
      totalWords += creative;
    });
    creativeDays.sort();
    let streak = 0;
    let best = 0;
    let prev = null;
    creativeDays.forEach((date) => {
      if (!prev) {
        streak = 1;
      } else {
        const prevDate = new Date(`${prev}T00:00:00`);
        const curDate = new Date(`${date}T00:00:00`);
        const diff = (curDate - prevDate) / 86400000;
        streak = diff === 1 ? streak + 1 : 1;
      }
      best = Math.max(best, streak);
      prev = date;
    });
    return {
      activeDays: creativeDays.length,
      streakDays: best,
      chapters: summary?.creative_chapters || 0,
      totalWords,
    };
  }

  function deriveYears(timeSeries) {
    const years = new Set((timeSeries || []).map((item) => Number(item.date.slice(0, 4))));
    years.add(new Date().getFullYear());
    return [...years].sort((a, b) => b - a);
  }

  function getRecentDates(modelTimeSeries) {
    return [...new Set((modelTimeSeries || []).map((item) => item.date))].sort().slice(-7);
  }

  function getTopModels(byModel) {
    return [...(byModel || [])].sort((a, b) => b.calls - a.calls).slice(0, 5);
  }

  function buildModelTrend(stats, key) {
    const dates = getRecentDates(stats.model_time_series);
    const models = getTopModels(stats.by_model);
    const pointMap = new Map((stats.model_time_series || []).map((item) => [`${item.date}:${item.key}`, item]));
    return {
      series: models.map((model, index) => ({
        label: model.label || model.key,
        color: CHART_COLORS[index % CHART_COLORS.length],
        data: dates.map((date) => {
          const point = pointMap.get(`${date}:${model.key}`);
          const y = key === "avg_latency_ms" ? (point?.avg_latency_ms ?? 0) : (point?.calls ?? 0);
          return { x: date, y };
        }),
      })),
      enableArea: true,
      valueFormat: key === "avg_latency_ms" ? "seconds" : "compact",
      rawMs: key === "avg_latency_ms",
    };
  }

  function buildTokenTrend(stats) {
    const dates = getRecentDates(stats.model_time_series);
    const models = getTopModels(stats.by_model);
    const pointMap = new Map((stats.model_time_series || []).map((item) => [`${item.date}:${item.key}`, item]));
    const keys = models.map((model) => model.key);
    return {
      data: dates.map((date) => {
        const row = { label: date };
        models.forEach((model) => {
          row[model.key] = pointMap.get(`${date}:${model.key}`)?.tokens_total ?? 0;
        });
        return row;
      }),
      keys,
      keyLabels: Object.fromEntries(models.map((model) => [model.key, model.label || model.key])),
      groupMode: "stacked",
    };
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
    renderYearHeatmap($("#writingHeatmap"), { year, days });

    const yearList = $("#writingYearList");
    yearList.innerHTML = state.availableYears.map((y) => `<button type="button" class="writing-year-btn" role="option" aria-selected="${y === year}" data-year="${y}">${y}</button>`).join("");
    $$(".writing-year-btn").forEach((btn) => btn.addEventListener("click", () => {
      state.selectedYear = Number(btn.dataset.year);
      void loadWritingHero();
    }));
  }

  function renderWritingCharts() {
    const points = state.writingDetail?.time_series || [];
    const createdKey = "创作";
    const importedKey = "导入";
    renderBarChart($("#chartWritingTrend"), {
      data: points.map((item) => ({
        label: item.date,
        [createdKey]: Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0)),
        [importedKey]: Math.max(0, item.import_word_delta || 0),
      })),
      keys: [createdKey, importedKey],
      keyLabels: { [createdKey]: "创作", [importedKey]: "导入" },
      keyColors: { [createdKey]: "#315f46", [importedKey]: "#a9c4b3" },
      groupMode: "stacked",
    });

    let cumulative = 0;
    renderLineChart($("#chartWritingCumulative"), {
      series: [{
        label: "累计创作字数",
        color: "#315f46",
        data: points.map((item) => {
          cumulative += Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
          return { x: item.date, y: cumulative };
        }),
      }],
      enableArea: true,
    });

    const userTotal = points.reduce((sum, item) => sum + Math.max(0, item.user_word_delta || 0), 0);
    const agentTotal = points.reduce((sum, item) => sum + Math.max(0, item.agent_word_delta || 0), 0);
    const importTotal = points.reduce((sum, item) => sum + Math.max(0, item.import_word_delta || 0), 0);
    renderDonutChart($("#chartWritingSource"), {
      data: [
        { id: "user", label: "用户编辑", value: userTotal, color: "#5b8def" },
        { id: "agent", label: "Agent 创作", value: agentTotal, color: "#315f46" },
        { id: "import", label: "导入", value: importTotal, color: "#a9c4b3" },
      ],
    });

    const weekdayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
    const weekdayCounts = Array.from({ length: 7 }, () => 0);
    points.forEach((item) => {
      const creative = Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
      if (creative <= 0) return;
      const weekday = new Date(`${item.date}T00:00:00`).getDay();
      const index = weekday === 0 ? 6 : weekday - 1;
      weekdayCounts[index] += 1;
    });
    renderBarChart($("#chartWritingWeekday"), {
      data: weekdayLabels.map((label, index) => ({ label, 活跃天数: weekdayCounts[index] })),
      keys: ["活跃天数"],
      keyLabels: { 活跃天数: "活跃天数" },
      keyColors: { 活跃天数: "#6f9a7f" },
      groupMode: "grouped",
    });
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

    renderLineChart($("#chartLlmCallTrend"), buildModelTrend(stats, "calls"));
    renderDonutChart($("#chartLlmModelCalls"), {
      data: (stats.by_model || []).map((item, index) => ({
        id: item.key,
        label: item.label || item.key,
        value: item.calls,
        color: CHART_COLORS[index % CHART_COLORS.length],
      })),
    });
    renderDonutChart($("#chartLlmModelTokens"), {
      data: (stats.by_model || []).map((item, index) => ({
        id: item.key,
        label: item.label || item.key,
        value: item.tokens_total,
        color: CHART_COLORS[index % CHART_COLORS.length],
      })),
    });
    renderBarChart($("#chartLlmTokenTrend"), buildTokenTrend(stats));
    renderLineChart($("#chartLlmLatencyTrend"), buildModelTrend(stats, "avg_latency_ms"));
    renderDonutChart($("#chartLlmProjectTokens"), {
      data: (stats.by_project || []).map((item, index) => ({
        id: item.key,
        label: item.label || item.key,
        value: item.tokens_total,
        color: CHART_COLORS[index % CHART_COLORS.length],
      })),
    });
  }

  function fillSelect(select, options, allLabel = "全部") {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${allLabel}</option>${(options || []).map((item) => {
      if (typeof item === "string") return `<option value="${esc(item)}">${esc(item)}</option>`;
      return `<option value="${esc(item.value)}">${esc(item.label || item.value)}</option>`;
    }).join("")}`;
    if ([...select.options].some((opt) => opt.value === current)) select.value = current;
  }

  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value;
  }

  function operationLabel(record) {
    if (record.category === "agent") return OPERATION_LABELS[record.operation] || record.operation;
    return OPERATION_LABELS[record.operation] || record.operation;
  }

  function renderRecordsFilters(options) {
    fillSelect($("#recordsProjectFilter"), options?.project_options || []);
    fillSelect($("#recordsModelFilter"), (options?.model_options || []).map((item) => item.value));
    fillSelect($("#recordsProviderFilter"), options?.model_providers || []);
    fillSelect($("#recordsCategoryFilter"), (options?.categories || []).map((value) => ({ value, label: categoryLabel(value) })));
    fillSelect($("#recordsStatusFilter"), (options?.statuses || []).map((value) => ({ value, label: STATUS_LABELS[value] || value })));
  }

  function renderRecordsTable() {
    const payload = state.records;
    const card = $("#recordsTableCard");
    const tbody = $("#recordsTableBody");
    const items = payload?.records?.items || [];
    const total = payload?.records?.total || 0;
    const page = payload?.records?.page || 1;
    const pageSize = payload?.records?.page_size || 20;

    $$(".records-sort").forEach((btn) => {
      const active = btn.dataset.sort === state.filters.recordsSortBy;
      btn.dataset.active = String(active);
      btn.dataset.indicator = active ? (state.filters.recordsSortOrder === "asc" ? "↑" : "↓") : "";
    });

    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="9"><div class="records-empty">没有符合条件的调用记录</div></td></tr>`;
    } else {
      tbody.innerHTML = items.map((record) => {
        const cache = record.token_cache ? `（${formatNumber(record.token_cache)}）` : "";
        const statusClass = record.status === "success" ? "success" : "failed";
        const statusText = STATUS_LABELS[record.status] || record.status;
        return `<tr>
          <td>${esc(formatDateTime(record.created_at))}</td>
          <td class="project-cell" title="${esc(record.project_title || "未归属项目")}">${esc(record.project_title || "未归属项目")}</td>
          <td>${esc(record.model_id || "—")}</td>
          <td>${esc(`${categoryLabel(record.category)} / ${operationLabel(record)}`)}</td>
          <td>${esc(formatSeconds(record.latency_ms))}</td>
          <td>${esc(formatSeconds(record.first_token_ms))}</td>
          <td>${esc(`${formatNumber(record.tokens_input)}${cache}`)}</td>
          <td>${esc(formatNumber(record.tokens_output))}</td>
          <td><span class="status-badge ${statusClass}">${esc(statusText)}</span></td>
        </tr>`;
      }).join("");
    }

    const start = total ? (page - 1) * pageSize + 1 : 0;
    const end = total ? Math.min(page * pageSize, total) : 0;
    $("#recordsRangeText").textContent = `第 ${start}–${end} 条，共 ${formatNumber(total)} 条`;
    renderPagination(total, page, pageSize);
    card?.classList.remove("is-loading");
  }

  function renderPagination(total, page, pageSize) {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const controls = $("#recordsPaginationControls");
    const pages = [];
    const pushPage = (p) => pages.push(p);
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i += 1) pushPage(i);
    } else {
      pushPage(1);
      if (page > 3) pages.push("…");
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i += 1) pushPage(i);
      if (page < totalPages - 2) pages.push("…");
      pushPage(totalPages);
    }
    controls.innerHTML = `
      <button type="button" class="records-page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>上一页</button>
      ${pages.map((p) => (p === "…" ? `<span>…</span>` : `<button type="button" class="records-page-btn${p === page ? " active" : ""}" data-page="${p}">${p}</button>`)).join("")}
      <button type="button" class="records-page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页</button>`;
    $$("#recordsPaginationControls .records-page-btn").forEach((btn) => btn.addEventListener("click", () => {
      const next = Number(btn.dataset.page);
      if (!Number.isFinite(next) || next < 1 || next > totalPages) return;
      state.filters.recordsPage = next;
      void loadRecords();
    }));
  }

  async function loadWritingHero() {
    const year = state.selectedYear;
    const query = new URLSearchParams({
      timezone: state.timezone,
      start_at: `${year}-01-01T00:00:00`,
      end_at: `${year}-12-31T23:59:59`,
    });
    renderChartState($("#writingHeatmap"), { loading: true });
    try {
      const data = await fetchJson(`/api/dashboard/writing?${query}`, "writingHero");
      if (!viewActive || state.activeTab !== "writing") return;
      state.writingHero = data;
      state.availableYears = deriveYears(data.time_series);
      if (!state.availableYears.includes(state.selectedYear)) {
        state.selectedYear = state.availableYears[0];
      }
      renderWritingHero();
      try {
        const options = await ensureFilterOptions();
        fillSelect($("#writingProjectFilter"), options?.project_options || []);
      } catch {
        /* options are optional for hero view */
      }
    } catch (error) {
      if (error.stale) return;
      renderChartState($("#writingHeatmap"), { error: error.message || "加载失败", onRetry: () => void loadWritingHero() });
    }
  }

  async function loadWritingDetail() {
    const query = new URLSearchParams({ timezone: state.timezone });
    if (state.filters.writingProjectId) query.set("project_id", state.filters.writingProjectId);
    if (state.filters.writingStartDate) query.set("start_at", toIsoBoundary(state.filters.writingStartDate, "start"));
    if (state.filters.writingEndDate) query.set("end_at", toIsoBoundary(state.filters.writingEndDate, "end"));

    ["#chartWritingTrend", "#chartWritingCumulative", "#chartWritingSource", "#chartWritingWeekday"].forEach((sel) => renderChartState($(sel), { loading: true }));
    try {
      const data = await fetchJson(`/api/dashboard/writing?${query}`, "writingDetail");
      if (!viewActive || state.activeTab !== "writing") return;
      state.writingDetail = data;
      const options = state.filterOptions || (await ensureFilterOptions().catch(() => null));
      fillSelect($("#writingProjectFilter"), options?.project_options || []);
      renderWritingCharts();
    } catch (error) {
      if (error.stale) return;
      const retry = () => void loadWritingDetail();
      ["#chartWritingTrend", "#chartWritingCumulative", "#chartWritingSource", "#chartWritingWeekday"].forEach((sel) => renderChartState($(sel), { error: error.message || "加载失败", onRetry: retry }));
    }
  }

  async function loadLlmStats() {
    ["#chartLlmCallTrend", "#chartLlmModelCalls", "#chartLlmModelTokens", "#chartLlmTokenTrend", "#chartLlmLatencyTrend", "#chartLlmProjectTokens"].forEach((sel) => renderChartState($(sel), { loading: true }));
    try {
      const data = await fetchJson("/api/dashboard/llm-api/stats", "llm");
      if (!viewActive || state.activeTab !== "llm") return;
      state.llmStats = data;
      state.filterOptions = data.options;
      renderLlmTab();
    } catch (error) {
      if (error.stale) return;
      const retry = () => void loadLlmStats();
      ["#chartLlmCallTrend", "#chartLlmModelCalls", "#chartLlmModelTokens", "#chartLlmTokenTrend", "#chartLlmLatencyTrend", "#chartLlmProjectTokens"].forEach((sel) => renderChartState($(sel), { error: error.message || "加载失败", onRetry: retry }));
    }
  }

  function recordsQueryParams() {
    const f = state.filters;
    const query = new URLSearchParams({
      page: String(f.recordsPage),
      page_size: String(f.recordsPageSize),
      sort_by: f.recordsSortBy,
      sort_order: f.recordsSortOrder,
    });
    if (f.recordsProjectId) query.set("project_id", f.recordsProjectId);
    if (f.recordsModelId) query.set("model_id", f.recordsModelId);
    if (f.recordsProvider) query.set("model_provider", f.recordsProvider);
    if (f.recordsCategory) query.set("category", f.recordsCategory);
    if (f.recordsStatus) query.set("status", f.recordsStatus);
    if (f.recordsStartDate) query.set("start_at", toIsoBoundary(f.recordsStartDate, "start"));
    if (f.recordsEndDate) query.set("end_at", toIsoBoundary(f.recordsEndDate, "end"));
    if (f.recordsSearch.trim()) query.set("search", f.recordsSearch.trim());
    return query;
  }

  async function loadRecords() {
    $("#recordsTableCard")?.classList.add("is-loading");
    try {
      const data = await fetchJson(`/api/dashboard/llm-api/records?${recordsQueryParams()}`, "records");
      if (!viewActive || state.activeTab !== "records") return;
      state.records = data;
      renderRecordsFilters(data.options);
      renderRecordsTable();
    } catch (error) {
      if (error.stale) return;
      $("#recordsTableBody").innerHTML = `<tr><td colspan="9"><div class="records-empty">${esc(error.message || "加载失败")} <button type="button" class="button ghost" id="recordsRetryBtn">重试</button></div></td></tr>`;
      $("#recordsRetryBtn")?.addEventListener("click", () => void loadRecords());
      $("#recordsTableCard")?.classList.remove("is-loading");
    }
  }

  function syncWritingFilterInputs() {
    const project = $("#writingProjectFilter");
    const start = $("#writingStartDate");
    const end = $("#writingEndDate");
    if (project) project.value = state.filters.writingProjectId;
    if (start) start.value = state.filters.writingStartDate;
    if (end) end.value = state.filters.writingEndDate;
  }

  function syncRecordsFilterInputs() {
    const map = {
      recordsProjectFilter: "recordsProjectId",
      recordsModelFilter: "recordsModelId",
      recordsProviderFilter: "recordsProvider",
      recordsCategoryFilter: "recordsCategory",
      recordsStatusFilter: "recordsStatus",
      recordsStartDate: "recordsStartDate",
      recordsEndDate: "recordsEndDate",
      recordsSearch: "recordsSearch",
    };
    Object.entries(map).forEach(([id, key]) => {
      const el = $(`#${id}`);
      if (el) el.value = state.filters[key];
    });
  }

  function resetWritingFilters() {
    const range = buildDefaultRange();
    state.filters.writingProjectId = "";
    state.filters.writingStartDate = range.start;
    state.filters.writingEndDate = range.end;
    syncWritingFilterInputs();
    void loadWritingDetail();
  }

  function resetRecordsFilters() {
    state.filters.recordsProjectId = "";
    state.filters.recordsModelId = "";
    state.filters.recordsProvider = "";
    state.filters.recordsCategory = "";
    state.filters.recordsStatus = "";
    state.filters.recordsStartDate = "";
    state.filters.recordsEndDate = "";
    state.filters.recordsSearch = "";
    state.filters.recordsPage = 1;
    state.filters.recordsSortBy = "created_at";
    state.filters.recordsSortOrder = "desc";
    syncRecordsFilterInputs();
    void loadRecords();
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
    abortAll();
    if (tab === "writing") {
      void loadWritingHero();
      void loadWritingDetail();
    } else if (tab === "llm") {
      void loadLlmStats();
    } else {
      void loadRecords();
    }
  }

  function refreshCurrentTab() {
    if (!viewActive) return;
    switchTab(state.activeTab);
  }

  function bindEvents() {
    $$(".analytics-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
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
      });
    });

    $("#writingProjectFilter")?.addEventListener("change", (event) => {
      state.filters.writingProjectId = event.target.value;
      void loadWritingDetail();
    });
    $("#writingStartDate")?.addEventListener("change", (event) => {
      state.filters.writingStartDate = event.target.value;
      void loadWritingDetail();
    });
    $("#writingEndDate")?.addEventListener("change", (event) => {
      state.filters.writingEndDate = event.target.value;
      void loadWritingDetail();
    });
    $("#writingFilterReset")?.addEventListener("click", resetWritingFilters);

    const recordsFilterChange = (key, event) => {
      state.filters[key] = event.target.value;
      state.filters.recordsPage = 1;
      void loadRecords();
    };
    $("#recordsProjectFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsProjectId", e));
    $("#recordsModelFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsModelId", e));
    $("#recordsProviderFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsProvider", e));
    $("#recordsCategoryFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsCategory", e));
    $("#recordsStatusFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsStatus", e));
    $("#recordsStartDate")?.addEventListener("change", (e) => recordsFilterChange("recordsStartDate", e));
    $("#recordsEndDate")?.addEventListener("change", (e) => recordsFilterChange("recordsEndDate", e));
    $("#recordsSearch")?.addEventListener("input", (event) => {
      state.filters.recordsSearch = event.target.value;
      state.filters.recordsPage = 1;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => void loadRecords(), 300);
    });
    $("#recordsFilterReset")?.addEventListener("click", resetRecordsFilters);

    $$(".records-sort").forEach((btn) => btn.addEventListener("click", () => {
      const field = btn.dataset.sort;
      if (state.filters.recordsSortBy === field) {
        state.filters.recordsSortOrder = state.filters.recordsSortOrder === "asc" ? "desc" : "asc";
      } else {
        state.filters.recordsSortBy = field;
        state.filters.recordsSortOrder = "desc";
      }
      state.filters.recordsPage = 1;
      void loadRecords();
    }));
  }

  function init({ api, escapeHtml, notify }) {
    deps = { api, escapeHtml, notify };
    const range = buildDefaultRange();
    state.filters.writingStartDate = range.start;
    state.filters.writingEndDate = range.end;
    syncWritingFilterInputs();
    bindEvents();
  }

  function activate() {
    viewActive = true;
    refreshCurrentTab();
  }

  function deactivate() {
    viewActive = false;
    abortAll();
    clearTimeout(searchTimer);
  }

  function refresh() {
    refreshCurrentTab();
  }

  window.NovelDashboard = { init, activate, deactivate, refresh };
})();
