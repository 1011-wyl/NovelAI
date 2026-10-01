import { CHART_COLORS } from "../../features/analytics/labels.js";

export function renderDonutChart(container, model, runtime) {
  const {
    cleanupContainer,
    renderChartState,
    observeResize,
    showTooltip,
    hideTooltip,
    escapeHtml,
    formatCompact,
  } = runtime;

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
      return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${escapeHtml(item.label)}</span>`;
    }).join("");
    container.appendChild(legend);
  };

  observeResize(container, render);
  render();
}
