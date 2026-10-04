import type { LlmKeyedStat, LlmStatsResponse, WritingTimePoint, YearMetrics } from "../types/analytics.types";
import { CHART_COLORS } from "./labels";

export function computeYearMetrics(
  timeSeries: WritingTimePoint[] | null | undefined,
  summary: { creative_chapters?: number } | null | undefined
): YearMetrics {
  const creativeDays: string[] = [];
  let totalWords = 0;
  (timeSeries || []).forEach((item) => {
    const creative = Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
    if (creative > 0) creativeDays.push(item.date);
    totalWords += creative;
  });
  creativeDays.sort();
  let streak = 0;
  let best = 0;
  let prev: string | null = null;
  creativeDays.forEach((date) => {
    if (!prev) {
      streak = 1;
    } else {
      const prevDate = new Date(`${prev}T00:00:00`);
      const curDate = new Date(`${date}T00:00:00`);
      const diff = (curDate.getTime() - prevDate.getTime()) / 86400000;
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

export function deriveYears(timeSeries: WritingTimePoint[] | null | undefined): number[] {
  const years = new Set((timeSeries || []).map((item) => Number(item.date.slice(0, 4))));
  years.add(new Date().getFullYear());
  return [...years].sort((a, b) => b - a);
}

export function getRecentDates(modelTimeSeries: LlmStatsResponse["model_time_series"]): string[] {
  return [...new Set((modelTimeSeries || []).map((item) => item.date))].sort().slice(-7);
}

export function getTopModels(byModel: LlmKeyedStat[]): LlmKeyedStat[] {
  return [...(byModel || [])].sort((a, b) => b.calls - a.calls).slice(0, 5);
}

export function buildModelTrend(stats: LlmStatsResponse, key: "calls" | "avg_latency_ms") {
  const dates = getRecentDates(stats.model_time_series);
  const models = getTopModels(stats.by_model);
  const pointMap = new Map(
    (stats.model_time_series || []).map((item) => [`${item.date}:${item.key}`, item])
  );
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
    valueFormat: key === "avg_latency_ms" ? ("seconds" as const) : ("compact" as const),
    rawMs: key === "avg_latency_ms",
  };
}

export function buildTokenTrend(stats: LlmStatsResponse) {
  const dates = getRecentDates(stats.model_time_series);
  const models = getTopModels(stats.by_model);
  const pointMap = new Map(
    (stats.model_time_series || []).map((item) => [`${item.date}:${item.key}`, item])
  );
  const keys = models.map((model) => model.key);
  return {
    data: dates.map((date) => {
      const row: Record<string, string | number> = { label: date };
      models.forEach((model) => {
        row[model.key] = pointMap.get(`${date}:${model.key}`)?.tokens_total ?? 0;
      });
      return row;
    }),
    keys,
    keyLabels: Object.fromEntries(models.map((model) => [model.key, model.label || model.key])),
    groupMode: "stacked" as const,
  };
}

export function buildWritingTrendModel(timeSeries: WritingTimePoint[] | null | undefined) {
  const points = timeSeries || [];
  const createdKey = "创作";
  const importedKey = "导入";
  return {
    data: points.map((item) => ({
      label: item.date,
      [createdKey]: Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0)),
      [importedKey]: Math.max(0, item.import_word_delta || 0),
    })),
    keys: [createdKey, importedKey],
    keyLabels: { [createdKey]: "创作", [importedKey]: "导入" },
    keyColors: { [createdKey]: "#315f46", [importedKey]: "#a9c4b3" },
    groupMode: "stacked" as const,
  };
}

export function buildWritingCumulativeModel(timeSeries: WritingTimePoint[] | null | undefined) {
  const points = timeSeries || [];
  let cumulative = 0;
  return {
    series: [
      {
        label: "累计创作字数",
        color: "#315f46",
        data: points.map((item) => {
          cumulative += Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
          return { x: item.date, y: cumulative };
        }),
      },
    ],
    enableArea: true,
  };
}

export function buildWritingSourceModel(timeSeries: WritingTimePoint[] | null | undefined) {
  const points = timeSeries || [];
  const userTotal = points.reduce((sum, item) => sum + Math.max(0, item.user_word_delta || 0), 0);
  const agentTotal = points.reduce((sum, item) => sum + Math.max(0, item.agent_word_delta || 0), 0);
  const importTotal = points.reduce((sum, item) => sum + Math.max(0, item.import_word_delta || 0), 0);
  return {
    data: [
      { id: "user", label: "用户编辑", value: userTotal, color: "#5b8def" },
      { id: "agent", label: "Agent 创作", value: agentTotal, color: "#315f46" },
      { id: "import", label: "导入", value: importTotal, color: "#a9c4b3" },
    ],
  };
}

export function buildWritingWeekdayModel(timeSeries: WritingTimePoint[] | null | undefined) {
  const points = timeSeries || [];
  const weekdayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const weekdayCounts = Array.from({ length: 7 }, () => 0);
  points.forEach((item) => {
    const creative = Math.max(0, (item.user_word_delta || 0) + (item.agent_word_delta || 0));
    if (creative <= 0) return;
    const weekday = new Date(`${item.date}T00:00:00`).getDay();
    const index = weekday === 0 ? 6 : weekday - 1;
    weekdayCounts[index] += 1;
  });
  return {
    data: weekdayLabels.map((label, index) => ({ label, 活跃天数: weekdayCounts[index] })),
    keys: ["活跃天数"],
    keyLabels: { 活跃天数: "活跃天数" },
    keyColors: { 活跃天数: "#6f9a7f" },
    groupMode: "grouped" as const,
  };
}

export function buildLlmModelCallsDonut(byModel: LlmKeyedStat[]) {
  return {
    data: (byModel || []).map((item, index) => ({
      id: item.key,
      label: item.label || item.key,
      value: item.calls,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })),
  };
}

export function buildLlmModelTokensDonut(byModel: LlmKeyedStat[]) {
  return {
    data: (byModel || []).map((item, index) => ({
      id: item.key,
      label: item.label || item.key,
      value: item.tokens_total,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })),
  };
}

export function buildLlmProjectTokensDonut(byProject: LlmKeyedStat[]) {
  return {
    data: (byProject || []).map((item, index) => ({
      id: item.key,
      label: item.label || item.key,
      value: item.tokens_total,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })),
  };
}

export function buildHeatmapDays(timeSeries: WritingTimePoint[] | null | undefined) {
  return (timeSeries || []).map((item) => ({
    date: item.date,
    value: Math.max(
      0,
      (item.user_word_delta || 0) + (item.agent_word_delta || 0) + (item.import_word_delta || 0)
    ),
  }));
}

export function buildPaginationPages(totalPages: number, page: number): Array<number | "…"> {
  const pages: Array<number | "…"> = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i += 1) pages.push(i);
    return pages;
  }
  pages.push(1);
  if (page > 3) pages.push("…");
  for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i += 1) {
    pages.push(i);
  }
  if (page < totalPages - 2) pages.push("…");
  pages.push(totalPages);
  return pages;
}
