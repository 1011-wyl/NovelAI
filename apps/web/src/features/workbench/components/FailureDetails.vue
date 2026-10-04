<script setup lang="ts">
import { computed } from "vue";
import type { ChapterFailure } from "../types/workbench.types";

const props = defineProps<{ failure: ChapterFailure }>();

const COMPONENT_LABELS: Record<string, string> = {
  "structural.length": "篇幅",
  "structural.constraints": "约束",
  "structural.character": "人物出现",
  "structural.repetition": "重复度",
  "readability.opening_hook": "开篇钩子",
  "readability.scene_causality": "场景因果",
  "readability.conflict_escalation": "冲突升级",
  "readability.character_agency": "人物能动性",
  "readability.dialogue_voice": "对话声口",
  "readability.showing_specificity": "具体描写",
  "readability.reader_payoff": "读者回报",
  "readability.ending_hook": "结尾钩子",
  "prose.template_density": "文风模板",
  "continuity.semantic": "连续性",
};

function formatScore(value: number | null | undefined) {
  if (value == null || Number.isNaN(Number(value))) return "";
  return Number(value).toFixed(1);
}

const lowestLabel = computed(() => {
  const key = props.failure.lowest_component;
  if (!key) return null;
  return COMPONENT_LABELS[key] || key;
});

const scoreTrace = computed(() => {
  const trace = props.failure.score_trace || [];
  return trace.length ? trace.map((item) => formatScore(item)).join(" → ") : "";
});

const attemptLabel = computed(() => {
  const current = props.failure.review_attempt || 0;
  const max = props.failure.max_review_attempts || 0;
  if (!current || !max) return "";
  return `第 ${current}/${max} 次质量检查`;
});

const passLine = computed(() => formatScore(props.failure.pass_score_exclusive ?? 60));
const preflightOnly = computed(() => {
  const status = props.failure.quality_status || "";
  return Boolean(props.failure.preflight_only) || [
    "GENERATION_FAILED",
    "LENGTH_REPAIRING",
    "LENGTH_NEEDS_ATTENTION",
  ].includes(status);
});
const qualityScore = computed(() => preflightOnly.value ? "" : formatScore(props.failure.score));
const selectedScore = computed(() =>
  preflightOnly.value ? "" : formatScore(props.failure.selected_score ?? props.failure.score)
);
const passed = computed(() => (props.failure.quality_status || "") === "PASSED");
const lengthStatus = computed(() => {
  const status = props.failure.quality_status || "";
  if (status === "LENGTH_REPAIRING" || status === "LENGTH_NEEDS_ATTENTION") return status;
  return "";
});
const lengthLabel = computed(() => {
  const actual = props.failure.actual_length;
  const min = props.failure.accepted_length_min;
  const max = props.failure.accepted_length_max;
  if (!actual && !min) return "";
  if (min && max) return `实际字数 ${actual || 0} / 目标范围 ${min}～${max}`;
  return actual ? `实际字数 ${actual}` : "";
});
const selectedLabel = computed(() => {
  const score = selectedScore.value;
  const index = props.failure.best_attempt_index || 0;
  if (!score) return "";
  return index ? `最终采用：${score} 分（第 ${index} 版）` : `最终采用：${score} 分`;
});
</script>

<template>
  <div class="failure-details">
    <p>
      <strong>{{ passed ? "质量审核已通过" : lengthStatus ? "字数尚未达标" : "未通过审核" }}</strong>
    </p>
    <p v-if="preflightOnly">综合质量分：未审核</p>
    <p v-else-if="qualityScore">综合质量分 {{ qualityScore }} / 通过条件 &gt; {{ passLine }}</p>
    <p v-if="attemptLabel">{{ attemptLabel }}</p>
    <p v-if="lowestLabel" class="muted">最低分项 {{ lowestLabel }}</p>
    <p v-if="scoreTrace" class="muted">分数轨迹 {{ scoreTrace }}</p>
    <p v-if="selectedLabel" class="muted">{{ selectedLabel }}</p>
    <p v-if="lengthLabel" class="muted">{{ lengthLabel }}</p>
    <p v-if="failure.revision_count != null" class="muted">
      已自动修订 {{ failure.revision_count }} 次
      <span v-if="failure.length_repair_count">，字数补写 {{ failure.length_repair_count }} 次</span>
    </p>
    <p v-if="failure.reviewed_at" class="muted">{{ failure.reviewed_at }}</p>
    <ul>
      <li v-for="(issue, index) in (failure.issues || []).slice(0, 3)" :key="index">
        {{ issue.message || issue.category }}
      </li>
    </ul>
  </div>
</template>
