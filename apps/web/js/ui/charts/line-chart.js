import { CHART_COLORS } from "../../features/analytics/labels.js";

function monthDayLabel(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : dateStr;
}

export function renderLineChart(container, model, runtime) {
  const {
    cleanupContainer,
    renderChartState,
    observeResize,
    showTooltip,
    hideTooltip,
    escapeHtml,
    formatCompact,
    formatSeconds,
  } = runtime;

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
        const valueText = () => (model.valueFormat === "seconds"
          ? `${formatSeconds(p.rawY * (model.rawMs ? 1 : 1000))} 秒`
          : formatCompact(p.rawY));
        dot.addEventListener("mouseenter", (event) => {
          showTooltip(`${item.label || ""} ${monthDayLabel(p.label)}：${valueText()}`, event.clientX, event.clientY);
        });
        dot.addEventListener("mousemove", (event) => {
          showTooltip(`${item.label || ""} ${monthDayLabel(p.label)}：${valueText()}`, event.clientX, event.clientY);
        });
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
        return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${escapeHtml(item.label || `系列 ${index + 1}`)}</span>`;
      }).join("");
      container.appendChild(legend);
    }
  };

  observeResize(container, render);
  render();
}
