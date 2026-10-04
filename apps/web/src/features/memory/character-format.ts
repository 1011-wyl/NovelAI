import type { CharacterRecord } from "@/api/contracts";

export const CHARACTER_ROLE_LABELS: Record<string, string> = {
  protagonist: "主角",
  supporting: "配角",
  ally: "盟友",
  rival: "竞争者",
  antagonist: "反派",
  mentor: "导师",
  family: "亲属",
  love_interest: "感情角色",
};

const STATE_LABELS: Record<string, string> = {
  current_goal: "当前目标",
  last_result: "最近结果",
  goal: "长期目标",
  knowledge: "已知信息",
  trust: "信任度",
  location: "所在位置",
  condition: "身体状况",
  emotion: "情绪状态",
  inventory: "持有物资",
  relationship: "关系状态",
  relationships: "人物关系",
};

const STATE_ORDER = [
  "current_goal",
  "last_result",
  "goal",
  "knowledge",
  "location",
  "condition",
  "emotion",
  "inventory",
  "relationship",
  "trust",
];

export function characterStateLabel(key: string) {
  return STATE_LABELS[key] || key.replaceAll("_", " ");
}

export function formatCharacterValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map(formatCharacterValue).join("；") : "暂无记录";
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.length
      ? entries.map(([key, item]) => `${characterStateLabel(key)}：${formatCharacterValue(item)}`).join("；")
      : "暂无记录";
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (value === null || value === undefined || value === "") return "暂无记录";
  return String(value);
}

export function characterFactParts(fact: string, characterName: string): [string, string] | null {
  const text = String(fact || "").trim();
  if (!text || text === `主角姓名为${characterName}`) return null;
  if (text.startsWith("人物背景：")) return ["人物背景", text.slice(5)];
  if (text.startsWith("性格特征：")) return ["性格特征", text.slice(5)];
  if (text.startsWith("故事起点属于")) return ["故事起点", text.slice(6)];
  if (text.includes("无限资源") || text.includes("全知能力")) return ["能力边界", text];
  return ["固定设定", text];
}

export function characterFacts(item: CharacterRecord) {
  const maxFacts = item.role === "protagonist" ? 6 : 3;
  const raw = (item.immutable_facts || [])
    .map((fact) => characterFactParts(fact, item.name))
    .filter((item): item is [string, string] => Boolean(item));
  const facts: [string, string][] = [];
  for (const fact of raw) {
    if (facts.length >= maxFacts) break;
    if (fact[0] === "固定设定" && facts.some((existing) => existing[1] === fact[1])) continue;
    facts.push(fact);
  }
  return facts;
}

export function appearedChapter(item: CharacterRecord) {
  const state = item.current_state || {};
  return Number(state.last_seen_chapter ?? state.chapter ?? 0);
}

export function stateRows(item: CharacterRecord) {
  if (appearedChapter(item) <= 0) return [];
  const currentState = item.current_state || {};
  return Object.entries(currentState)
    .filter(([key]) => !["chapter", "last_seen_chapter", "importance"].includes(key))
    .filter(([, value]) => {
      if (value === null || value === undefined || value === "") return false;
      if (Array.isArray(value) && value.length === 0) return false;
      if (typeof value === "object" && Object.keys(value as object).length === 0) return false;
      return true;
    })
    .sort(([left], [right]) => {
      const leftIndex = STATE_ORDER.indexOf(left);
      const rightIndex = STATE_ORDER.indexOf(right);
      return (
        (leftIndex < 0 ? STATE_ORDER.length : leftIndex) -
        (rightIndex < 0 ? STATE_ORDER.length : rightIndex)
      );
    });
}
