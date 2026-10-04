export const CHART_COLORS = ["#315f46", "#6f9a7f", "#5b8def", "#c27c3a", "#8b5cf6", "#d14343"];

export const CATEGORY_LABELS: Record<string, string> = {
  agent: "智能体",
  memory: "记忆",
  session: "会话",
};

export const OPERATION_LABELS: Record<string, string> = {
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

export const STATUS_LABELS: Record<string, string> = {
  success: "成功",
  failed: "失败",
  error: "失败",
  cancelled: "已取消",
  running: "进行中",
};

export function categoryLabel(value: string): string {
  return CATEGORY_LABELS[value] || value;
}

export function operationLabel(record: { category: string; operation: string }): string {
  return OPERATION_LABELS[record.operation] || record.operation;
}
