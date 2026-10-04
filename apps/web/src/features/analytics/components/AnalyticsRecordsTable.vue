<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useAnalyticsStore } from "../stores/analytics.store";
import { categoryLabel, operationLabel, STATUS_LABELS } from "../lib/labels";
import { formatDateTime, formatNumber, formatSeconds } from "../lib/format";
import { buildPaginationPages } from "../lib/selectors";
import type { RecordsSortBy } from "../types/analytics.types";
import AnalyticsEmptyState from "./AnalyticsEmptyState.vue";
import AnalyticsErrorState from "./AnalyticsErrorState.vue";

const store = useAnalyticsStore();
const { filters, records, recordsStatus, recordsError } = storeToRefs(store);

const items = computed(() => records.value?.records?.items || []);
const total = computed(() => records.value?.records?.total || 0);
const page = computed(() => records.value?.records?.page || filters.value.recordsPage);
const pageSize = computed(() => records.value?.records?.page_size || filters.value.recordsPageSize);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
const rangeText = computed(() => {
  const start = total.value ? (page.value - 1) * pageSize.value + 1 : 0;
  const end = total.value ? Math.min(page.value * pageSize.value, total.value) : 0;
  return `第 ${start}–${end} 条，共 ${formatNumber(total.value)} 条`;
});
const pages = computed(() => buildPaginationPages(totalPages.value, page.value));

const sortColumns: Array<{ key: RecordsSortBy; label: string }> = [
  { key: "created_at", label: "时间" },
  { key: "latency_ms", label: "用时" },
  { key: "first_token_ms", label: "首字" },
  { key: "tokens_input", label: "输入（缓存）" },
  { key: "tokens_output", label: "输出" },
];

function ariaSort(key: RecordsSortBy): "ascending" | "descending" | "none" {
  if (filters.value.recordsSortBy !== key) return "none";
  return filters.value.recordsSortOrder === "asc" ? "ascending" : "descending";
}

function sortIndicator(key: RecordsSortBy): string {
  if (filters.value.recordsSortBy !== key) return "";
  return filters.value.recordsSortOrder === "asc" ? "↑" : "↓";
}
</script>

<template>
  <article
    class="analytics-card analytics-record-card"
    :class="{ 'is-loading': recordsStatus === 'loading' }"
    data-testid="records-table-card"
  >
    <AnalyticsErrorState
      v-if="recordsStatus === 'error'"
      :message="recordsError"
      @retry="store.loadRecords()"
    />
    <template v-else>
      <div class="records-table-wrap">
        <table class="records-table">
          <thead>
            <tr>
              <th
                v-for="column in sortColumns.slice(0, 1)"
                :key="column.key"
                :aria-sort="ariaSort(column.key)"
              >
                <button
                  type="button"
                  class="records-sort"
                  :data-sort="column.key"
                  :data-active="String(filters.recordsSortBy === column.key)"
                  :aria-label="`按${column.label}排序`"
                  @click="store.toggleRecordsSort(column.key)"
                >
                  {{ column.label }}{{ sortIndicator(column.key) }}
                </button>
              </th>
              <th>项目</th>
              <th>模型</th>
              <th>操作</th>
              <th
                v-for="column in sortColumns.slice(1)"
                :key="column.key"
                :aria-sort="ariaSort(column.key)"
              >
                <button
                  type="button"
                  class="records-sort"
                  :data-sort="column.key"
                  :data-active="String(filters.recordsSortBy === column.key)"
                  :aria-label="`按${column.label}排序`"
                  @click="store.toggleRecordsSort(column.key)"
                >
                  {{ column.label }}{{ sortIndicator(column.key) }}
                </button>
              </th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="recordsStatus === 'empty' || (!items.length && recordsStatus !== 'loading')">
              <td colspan="9" class="records-empty-cell">
                <AnalyticsEmptyState message="没有符合条件的调用记录" />
              </td>
            </tr>
            <tr v-for="record in items" :key="record.id">
              <td data-label="时间">{{ formatDateTime(record.created_at) }}</td>
              <td
                class="project-cell"
                data-label="项目"
                :title="record.project_title || '未归属项目'"
              >
                {{ record.project_title || "未归属项目" }}
              </td>
              <td data-label="模型">{{ record.model_id || "—" }}</td>
              <td data-label="操作">{{ categoryLabel(record.category) }} / {{ operationLabel(record) }}</td>
              <td data-label="用时">{{ formatSeconds(record.latency_ms) }}</td>
              <td data-label="首字">{{ formatSeconds(record.first_token_ms) }}</td>
              <td data-label="输入（缓存）">
                {{ formatNumber(record.tokens_input)
                }}{{ record.token_cache ? `（${formatNumber(record.token_cache)}）` : "" }}
              </td>
              <td data-label="输出">{{ formatNumber(record.tokens_output) }}</td>
              <td data-label="状态">
                <span
                  class="status-badge"
                  :class="record.status === 'success' ? 'success' : 'failed'"
                >
                  {{ STATUS_LABELS[record.status] || record.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="records-pagination">
        <span>{{ rangeText }}</span>
        <div class="records-pagination-controls">
          <button
            type="button"
            class="records-page-btn"
            :disabled="page <= 1"
            @click="store.setRecordsPage(page - 1)"
          >
            上一页
          </button>
          <template v-for="(item, index) in pages" :key="`${item}-${index}`">
            <span v-if="item === '…'">…</span>
            <button
              v-else
              type="button"
              class="records-page-btn"
              :class="{ active: item === page }"
              :aria-current="item === page ? 'page' : undefined"
              @click="store.setRecordsPage(item)"
            >
              {{ item }}
            </button>
          </template>
          <button
            type="button"
            class="records-page-btn"
            :disabled="page >= totalPages"
            @click="store.setRecordsPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
  </article>
</template>
