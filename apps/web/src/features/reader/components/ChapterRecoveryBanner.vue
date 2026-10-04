<script setup lang="ts">
import { computed, ref } from "vue";
import type { ChapterRecord } from "@/api/contracts";
import type { ChapterFailure } from "@/features/workbench/types/workbench.types";
import BaseButton from "@/components/base/BaseButton.vue";

const props = defineProps<{
  chapter: ChapterRecord | null;
  failure: ChapterFailure | null;
  currentLength?: number;
  canAccept?: boolean;
  acceptDisabled?: boolean;
}>();
const emit = defineEmits<{
  workbench: [];
  review: [];
  accept: [];
}>();

const root = ref<HTMLElement | null>(null);
const expanded = ref(false);

function formatScore(value: number | null | undefined) {
  if (value == null || Number.isNaN(Number(value))) return "";
  return Number(value).toFixed(1);
}

const issues = computed(() => (props.failure?.issues || []).slice(0, 2));
const scoreTrace = computed(() => {
  const trace = props.failure?.score_trace || [];
  return trace.length ? trace.map((item) => formatScore(item)).join(" → ") : "";
});
const attemptLabel = computed(() => {
  const current = props.failure?.review_attempt || 0;
  const max = props.failure?.max_review_attempts || 0;
  if (!current || !max) return "";
  return `第 ${current}/${max} 次质量检查`;
});
const passLine = computed(() => formatScore(props.failure?.pass_score_exclusive ?? 60));
const preflightOnly = computed(() => {
  const status = props.failure?.quality_status || "";
  return Boolean(props.failure?.preflight_only) || [
    "GENERATION_FAILED",
    "LENGTH_REPAIRING",
    "LENGTH_NEEDS_ATTENTION",
  ].includes(status);
});
const qualityScore = computed(() => preflightOnly.value ? "" : formatScore(props.failure?.score));
const selectedLabel = computed(() => {
  if (preflightOnly.value) return "";
  const score = formatScore(props.failure?.selected_score ?? props.failure?.score);
  const index = props.failure?.best_attempt_index || 0;
  if (!score) return "";
  return index ? `最终采用：${score} 分（第 ${index} 版）` : `最终采用：${score} 分`;
});
const lengthLabel = computed(() => {
  const actual = props.currentLength ?? props.failure?.actual_length;
  const min = props.failure?.accepted_length_min;
  const max = props.failure?.accepted_length_max;
  if (min && max) return `实际字数 ${actual || 0} / 目标范围 ${min}～${max}`;
  return "";
});
const headline = computed(() => {
  const status = props.failure?.quality_status || "";
  if (status === "PASSED") return "审核已通过";
  if (status === "LENGTH_REPAIRING" || status === "LENGTH_NEEDS_ATTENTION") return "字数不足";
  if (status === "GENERATION_FAILED") return "生成未完成";
  return "质量待修改";
});
const compactMeta = computed(() => {
  if (preflightOnly.value) {
    const actual = props.currentLength ?? props.failure?.actual_length ?? 0;
    const minimum = props.failure?.accepted_length_min || 0;
    if (minimum) return `当前 ${actual} / 至少 ${minimum} 字 · 尚未审核`;
    return "尚未进入质量审核";
  }
  if (qualityScore.value) return `${qualityScore.value} 分 · 通过条件 > ${passLine.value}`;
  return "请查看详情并处理";
});

defineExpose({
  focus: () => root.value?.focus(),
});
</script>

<template>
  <div
    v-if="chapter?.status === 'FAILED'"
    ref="root"
    class="recovery-banner"
    role="alert"
    aria-live="assertive"
    tabindex="-1"
  >
    <div class="banner-summary">
      <span class="banner-mark" aria-hidden="true" />
      <div class="banner-message">
        <strong>{{ headline }}</strong>
        <span>{{ compactMeta }}</span>
      </div>
      <button
        class="banner-toggle"
        type="button"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        {{ expanded ? "收起" : "详情" }}
      </button>
    </div>
    <div v-if="expanded" class="banner-details">
      <p v-if="attemptLabel">{{ attemptLabel }}</p>
      <p v-if="scoreTrace">分数轨迹 {{ scoreTrace }}</p>
      <p v-if="selectedLabel">{{ selectedLabel }}</p>
      <p v-if="lengthLabel">{{ lengthLabel }}</p>
      <p v-if="failure?.lowest_component">最低分项：{{ failure.lowest_component }}</p>
      <ul v-if="issues.length">
        <li v-for="(issue, index) in issues" :key="index">{{ issue.message || issue.category }}</li>
      </ul>
      <div class="banner-actions">
        <BaseButton variant="ghost" @click="emit('workbench')">返回工作台</BaseButton>
        <BaseButton variant="primary" @click="emit('review')">编辑草稿</BaseButton>
        <BaseButton
          v-if="canAccept"
          variant="ghost"
          :disabled="acceptDisabled"
          @click="emit('accept')"
        >
          接受当前版本
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recovery-banner {
  border: 1px solid var(--workspace-border);
  background: var(--workspace-surface);
  padding: 8px 12px;
  margin: 0 12px 6px;
  border-radius: 8px;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.banner-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
}
.banner-mark {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--workspace-danger);
}
.banner-message {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.banner-message strong {
  flex: 0 0 auto;
  font-size: 14px;
}
.banner-message span {
  min-width: 0;
  color: var(--workspace-muted);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.banner-toggle {
  min-width: 44px;
  min-height: 44px;
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.banner-details {
  padding: 10px 0 4px 18px;
  border-top: 1px solid var(--workspace-border);
}
.banner-details p {
  margin: 4px 0;
  color: var(--workspace-muted);
  font-size: 12px;
}
.banner-details ul {
  margin: 8px 0;
  padding-left: 18px;
}
.recovery-banner p,
.recovery-banner li,
.recovery-banner strong {
  white-space: normal;
}
.banner-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.banner-actions :deep(button) {
  flex: 0 1 auto;
}
@media (max-width: 640px) {
  .banner-message {
    display: grid;
    gap: 2px;
  }
}
</style>
