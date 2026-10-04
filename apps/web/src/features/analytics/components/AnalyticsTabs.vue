<script setup lang="ts">
import type { AnalyticsTab } from "../types/analytics.types";

const props = defineProps<{
  modelValue: AnalyticsTab;
}>();

const emit = defineEmits<{
  "update:modelValue": [AnalyticsTab];
}>();

const tabs: Array<{ id: AnalyticsTab; label: string; panel: string }> = [
  { id: "writing", label: "写作", panel: "writingPanel" },
  { id: "llm", label: "LLM 统计", panel: "llmPanel" },
  { id: "records", label: "调用记录", panel: "recordsPanel" },
];

function select(tab: AnalyticsTab) {
  emit("update:modelValue", tab);
}

function onKeydown(event: KeyboardEvent, index: number) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  const delta = event.key === "ArrowRight" ? 1 : -1;
  const next = (index + delta + tabs.length) % tabs.length;
  select(tabs[next].id);
  const btn = (event.currentTarget as HTMLElement)
    .parentElement?.querySelectorAll<HTMLButtonElement>(".analytics-tab")[next];
  btn?.focus();
}
</script>

<template>
  <div class="analytics-tabs" role="tablist" aria-label="仪表盘分类">
    <button
      v-for="(tab, index) in tabs"
      :id="`tab${tab.id[0].toUpperCase()}${tab.id.slice(1)}`"
      :key="tab.id"
      type="button"
      class="analytics-tab"
      role="tab"
      :aria-selected="props.modelValue === tab.id"
      :aria-controls="tab.panel"
      :tabindex="props.modelValue === tab.id ? 0 : -1"
      :data-tab="tab.id"
      :data-testid="`analytics-tab-${tab.id}`"
      @click="select(tab.id)"
      @keydown="onKeydown($event, index)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
