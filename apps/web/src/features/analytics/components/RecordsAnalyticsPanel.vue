<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useAnalyticsStore } from "../stores/analytics.store";
import { categoryLabel, STATUS_LABELS } from "../lib/labels";
import AnalyticsRecordsTable from "./AnalyticsRecordsTable.vue";

const store = useAnalyticsStore();
const { filters, filterOptions } = storeToRefs(store);

const projectOptions = computed(() => filterOptions.value?.project_options || []);
const modelOptions = computed(() => filterOptions.value?.model_options || []);
const providers = computed(() => filterOptions.value?.model_providers || []);
const categories = computed(() => filterOptions.value?.categories || []);
const statuses = computed(() => filterOptions.value?.statuses || []);
</script>

<template>
  <div id="recordsPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabRecords">
    <article class="analytics-card analytics-filter-card">
      <div class="records-filter-layout">
        <div class="records-filter-row records-filter-row-primary">
          <label>
            项目
            <select
              :value="filters.recordsProjectId"
              data-testid="records-project-filter"
              @change="
                store.updateRecordsFilters({
                  recordsProjectId: ($event.target as HTMLSelectElement).value,
                })
              "
            >
              <option value="">全部</option>
              <option
                v-for="option in projectOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label || option.value }}
              </option>
            </select>
          </label>
          <label>
            模型
            <select
              :value="filters.recordsModelId"
              data-testid="records-model-filter"
              @change="
                store.updateRecordsFilters({
                  recordsModelId: ($event.target as HTMLSelectElement).value,
                })
              "
            >
              <option value="">全部</option>
              <option
                v-for="option in modelOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label || option.value }}
              </option>
            </select>
          </label>
          <label>
            提供商
            <select
              :value="filters.recordsProvider"
              @change="
                store.updateRecordsFilters({
                  recordsProvider: ($event.target as HTMLSelectElement).value,
                })
              "
            >
              <option value="">全部</option>
              <option v-for="provider in providers" :key="provider" :value="provider">
                {{ provider }}
              </option>
            </select>
          </label>
          <label>
            类型
            <select
              :value="filters.recordsCategory"
              @change="
                store.updateRecordsFilters({
                  recordsCategory: ($event.target as HTMLSelectElement).value,
                })
              "
            >
              <option value="">全部</option>
              <option v-for="category in categories" :key="category" :value="category">
                {{ categoryLabel(category) }}
              </option>
            </select>
          </label>
          <label>
            状态
            <select
              :value="filters.recordsStatus"
              data-testid="records-status-filter"
              @change="
                store.updateRecordsFilters({
                  recordsStatus: ($event.target as HTMLSelectElement).value,
                })
              "
            >
              <option value="">全部</option>
              <option v-for="status in statuses" :key="status" :value="status">
                {{ STATUS_LABELS[status] || status }}
              </option>
            </select>
          </label>
        </div>
        <div class="records-filter-row records-filter-row-secondary">
          <label>
            开始日期
            <input
              type="date"
              :value="filters.recordsStartDate"
              @change="
                store.updateRecordsFilters({
                  recordsStartDate: ($event.target as HTMLInputElement).value,
                })
              "
            />
          </label>
          <label>
            结束日期
            <input
              type="date"
              :value="filters.recordsEndDate"
              @change="
                store.updateRecordsFilters({
                  recordsEndDate: ($event.target as HTMLInputElement).value,
                })
              "
            />
          </label>
          <label>
            搜索
            <input
              type="search"
              :value="filters.recordsSearch"
              placeholder="模型、操作、类型或错误信息"
              autocomplete="off"
              data-testid="records-search"
              @input="store.scheduleRecordsSearch(($event.target as HTMLInputElement).value)"
            />
          </label>
          <button
            type="button"
            class="button ghost"
            data-testid="records-filter-reset"
            @click="store.resetRecordsFilters()"
          >
            重置
          </button>
        </div>
      </div>
    </article>
    <AnalyticsRecordsTable />
  </div>
</template>
