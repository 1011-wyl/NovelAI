function heatLevel(value) {
  if (value <= 0) return 0;
  if (value < 500) return 1;
  if (value < 2000) return 2;
  if (value < 5000) return 3;
  return 4;
}

export function renderYearHeatmap(container, model, runtime) {
  const {
    cleanupContainer,
    formatLocalDate,
    formatNumber,
  } = runtime;

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
