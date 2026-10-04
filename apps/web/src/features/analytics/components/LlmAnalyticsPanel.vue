<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useAnalyticsStore } from "../stores/analytics.store";
import { formatCompact, formatNumber, formatSeconds } from "../lib/format";
import {
  buildLlmModelCallsDonut,
  buildLlmModelTokensDonut,
  buildLlmProjectTokensDonut,
  buildModelTrend,
  buildTokenTrend,
} from "../lib/selectors";
import AnalyticsChart from "./AnalyticsChart.vue";
import AnalyticsErrorState from "./AnalyticsErrorState.vue";
import AnalyticsMetricCard from "./AnalyticsMetricCard.vue";

const store = useAnalyticsStore();
const { llmStats, llmStatus, llmError } = storeToRefs(store);

const summary = computed(() => llmStats.value?.summary);
const chartStatus = computed(() => llmStatus.value);
</script>

<template>
  <div id="llmPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabLlm">
    <AnalyticsErrorState
      v-if="llmStatus === 'error'"
      :message="llmError"
      @retry="store.loadLlm()"
    />
    <template v-else>
      <div class="llm-metric-grid">
        <AnalyticsMetricCard
          label="LLM 调用次数"
          :value="formatNumber(summary?.calls_total || 0)"
          :hint="`完成 ${formatNumber(summary?.success_total || 0)} 次`"
        />
        <AnalyticsMetricCard
          label="Token 消耗"
          :value="formatCompact(summary?.tokens_total || 0)"
          :hint="`输入 ${formatCompact(summary?.tokens_input_total || 0)} / 输出 ${formatCompact(summary?.tokens_output_total || 0)}`"
        />
        <AnalyticsMetricCard
          label="平均响应时间"
          :value="summary?.avg_latency_ms == null ? '—' : formatSeconds(summary.avg_latency_ms)"
          hint="秒"
        />
        <AnalyticsMetricCard
          label="首字响应时间"
          :value="summary?.avg_first_token_ms == null ? '—' : formatSeconds(summary.avg_first_token_ms)"
          hint="当前模型调用为非流式"
        />
      </div>
      <div class="analytics-chart-grid llm-chart-grid">
        <article class="analytics-card analytics-chart-card span-4">
          <h3>调用趋势</h3>
          <AnalyticsChart
            type="line"
            wide
            :model="llmStats ? buildModelTrend(llmStats, 'calls') : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
        <article class="analytics-card analytics-chart-card span-2">
          <h3>模型调用次数分布</h3>
          <AnalyticsChart
            type="donut"
            :model="llmStats ? buildLlmModelCallsDonut(llmStats.by_model) : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
        <article class="analytics-card analytics-chart-card span-2">
          <h3>模型消耗分布</h3>
          <AnalyticsChart
            type="donut"
            :model="llmStats ? buildLlmModelTokensDonut(llmStats.by_model) : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
        <article class="analytics-card analytics-chart-card span-4">
          <h3>消耗趋势</h3>
          <AnalyticsChart
            type="bar"
            wide
            :model="llmStats ? buildTokenTrend(llmStats) : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
        <article class="analytics-card analytics-chart-card span-4">
          <h3>响应时间趋势</h3>
          <AnalyticsChart
            type="line"
            wide
            :model="llmStats ? buildModelTrend(llmStats, 'avg_latency_ms') : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
        <article class="analytics-card analytics-chart-card span-2">
          <h3>总消耗分布</h3>
          <AnalyticsChart
            type="donut"
            :model="llmStats ? buildLlmProjectTokensDonut(llmStats.by_project) : null"
            :status="chartStatus"
            @retry="store.loadLlm()"
          />
        </article>
      </div>
    </template>
  </div>
</template>
