<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useAnalyticsChartRuntime } from "../composables/useAnalyticsChart";
import { renderBarChart } from "../charts/bar-chart.js";
import { renderDonutChart } from "../charts/donut-chart.js";
import { renderLineChart } from "../charts/line-chart.js";
import { renderYearHeatmap } from "../charts/year-heatmap.js";
import type { LoadStatus } from "../types/analytics.types";

const props = withDefaults(
  defineProps<{
    type: "bar" | "line" | "donut" | "heatmap";
    model: unknown;
    status?: LoadStatus;
    error?: string;
    wide?: boolean;
    heatmap?: boolean;
    ariaLabel?: string;
  }>(),
  {
    status: "success",
    error: "",
    wide: false,
    heatmap: false,
    ariaLabel: "",
  }
);

const emit = defineEmits<{
  retry: [];
}>();

const hostRef = ref<HTMLElement | null>(null);
const runtime = useAnalyticsChartRuntime();

function paint() {
  const el = hostRef.value;
  if (!el) return;
  if (props.status === "loading") {
    runtime.value.renderChartState(el, { loading: true });
    return;
  }
  if (props.status === "error") {
    runtime.value.renderChartState(el, {
      error: props.error || "加载失败",
      onRetry: () => emit("retry"),
    });
    return;
  }
  if (props.status === "empty" || props.model == null) {
    runtime.value.renderChartState(el, { empty: true });
    return;
  }
  if (props.type === "bar") renderBarChart(el, props.model, runtime.value);
  else if (props.type === "line") renderLineChart(el, props.model, runtime.value);
  else if (props.type === "donut") renderDonutChart(el, props.model, runtime.value);
  else renderYearHeatmap(el, props.model, runtime.value);
}

onMounted(paint);
watch(() => [props.type, props.model, props.status, props.error], paint, { deep: true });
onBeforeUnmount(() => {
  if (hostRef.value) runtime.value.destroyChart(hostRef.value);
});
</script>

<template>
  <div
    ref="hostRef"
    class="chart-host"
    :class="{ 'chart-host-wide': wide, 'chart-host-heatmap': heatmap }"
    :aria-label="ariaLabel || undefined"
    data-testid="analytics-chart"
  />
</template>
