export function createChartRuntime({
  escapeHtml,
  formatCompact,
  formatSeconds,
  formatNumber,
  formatLocalDate,
}) {
  let tooltipEl = null;
  const chartCleanups = new WeakMap();
  const trackedContainers = new Set();

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
    trackedContainers.delete(container);
    hideTooltip();
    container.innerHTML = "";
  }

  function observeResize(container, render) {
    let frame = null;
    const run = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(render);
    };
    trackedContainers.add(container);
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
      wrap.innerHTML = `<span>${escapeHtml(error)}</span>`;
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

  function destroyChart(container) {
    cleanupContainer(container);
  }

  function destroyAll() {
    for (const container of [...trackedContainers]) {
      cleanupContainer(container);
    }
    trackedContainers.clear();
    hideTooltip();
  }

  return {
    escapeHtml,
    formatCompact,
    formatSeconds,
    formatNumber,
    formatLocalDate,
    showTooltip,
    hideTooltip,
    cleanupContainer,
    observeResize,
    renderChartState,
    destroyChart,
    destroyAll,
  };
}
