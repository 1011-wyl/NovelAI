import { CHART_COLORS } from "../../features/analytics/labels.js";

function monthDayLabel(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : dateStr;
}

function chartHasPositiveValues(rows, keys) {
  return (rows || []).some((row) => (keys || []).some((key) => Number(row[key]) > 0));
}

export function renderBarChart(container, model, runtime) {
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
      return `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${escapeHtml(model.keyLabels?.[key] || key)}</span>`;
    }).join("");
    container.appendChild(legend);
  };

  observeResize(container, render);
  render();
}
