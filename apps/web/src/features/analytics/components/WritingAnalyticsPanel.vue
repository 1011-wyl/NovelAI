<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useAnalyticsStore } from "../stores/analytics.store";
import { formatNumber } from "../lib/format";
import {
  buildHeatmapDays,
  buildWritingCumulativeModel,
  buildWritingSourceModel,
  buildWritingTrendModel,
  buildWritingWeekdayModel,
  computeYearMetrics,
} from "../lib/selectors";
import AnalyticsChart from "./AnalyticsChart.vue";
import AnalyticsErrorState from "./AnalyticsErrorState.vue";
import AnalyticsMetricCard from "./AnalyticsMetricCard.vue";

const store = useAnalyticsStore();
const {
  selectedYear,
  availableYears,
  filters,
  filterOptions,
  writingHero,
  writingDetail,
  writingHeroStatus,
  writingDetailStatus,
  writingHeroError,
  writingDetailError,
} = storeToRefs(store);

const yearMetrics = computed(() =>
  computeYearMetrics(writingHero.value?.time_series, writingHero.value?.summary)
);

const heatmapModel = computed(() => ({
  year: selectedYear.value,
  days: buildHeatmapDays(writingHero.value?.time_series),
}));

const projectOptions = computed(() => filterOptions.value?.project_options || []);

const detailStatus = computed(() => writingDetailStatus.value);
const detailSeries = computed(() => writingDetail.value?.time_series || []);
</script>

<template>
  <div id="writingPanel" class="analytics-panel" role="tabpanel" aria-labelledby="tabWriting">
    <div class="writing-hero">
      <article class="analytics-card writing-heatmap-card">
        <div class="writing-heatmap-head">
          <div class="writing-year-list" role="listbox" aria-label="选择年份">
            <button
              v-for="year in availableYears"
              :key="year"
              type="button"
              class="writing-year-btn"
              role="option"
              :aria-selected="year === selectedYear"
              :data-year="year"
              @click="store.selectYear(year)"
            >
              {{ year }}
            </button>
          </div>
          <div class="writing-heatmap-copy">
            <p class="writing-hero-line">
              {{ selectedYear }} 年创作了 {{ formatNumber(yearMetrics.activeDays) }} 天
            </p>
            <AnalyticsErrorState
              v-if="writingHeroStatus === 'error'"
              :message="writingHeroError"
              @retry="store.loadWritingHero()"
            />
            <AnalyticsChart
              v-else
              type="heatmap"
              heatmap
              :model="heatmapModel"
              :status="writingHeroStatus === 'loading' ? 'loading' : 'success'"
              aria-label="年度创作热力日历"
              @retry="store.loadWritingHero()"
            />
            <p class="writing-hero-line muted">
              {{ selectedYear }} 年共创作 {{ formatNumber(yearMetrics.totalWords) }} 字
            </p>
            <div class="heatmap-legend" aria-hidden="true">
              <span>少</span>
              <span class="heatmap-legend-cell level-0" />
              <span class="heatmap-legend-cell level-1" />
              <span class="heatmap-legend-cell level-2" />
              <span class="heatmap-legend-cell level-3" />
              <span>多</span>
            </div>
          </div>
        </div>
      </article>
      <div class="writing-metric-grid">
        <AnalyticsMetricCard label="总创作天数" :value="formatNumber(yearMetrics.activeDays)" />
        <AnalyticsMetricCard label="连续创作天数" :value="formatNumber(yearMetrics.streakDays)" />
        <AnalyticsMetricCard label="总创作章节" :value="formatNumber(yearMetrics.chapters)" />
        <AnalyticsMetricCard label="总创作字数" :value="formatNumber(yearMetrics.totalWords)" />
      </div>
    </div>

    <article class="analytics-card analytics-filter-card">
      <div class="writing-filter-grid">
        <label>
          项目
          <select
            :value="filters.writingProjectId"
            data-testid="writing-project-filter"
            @change="
              store.updateWritingFilters({
                writingProjectId: ($event.target as HTMLSelectElement).value,
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
          开始日期
          <input
            type="date"
            :value="filters.writingStartDate"
            data-testid="writing-start-date"
            @change="
              store.updateWritingFilters({
                writingStartDate: ($event.target as HTMLInputElement).value,
              })
            "
          />
        </label>
        <label>
          结束日期
          <input
            type="date"
            :value="filters.writingEndDate"
            data-testid="writing-end-date"
            @change="
              store.updateWritingFilters({
                writingEndDate: ($event.target as HTMLInputElement).value,
              })
            "
          />
        </label>
        <button
          type="button"
          class="button ghost"
          data-testid="writing-filter-reset"
          @click="store.resetWritingFilters()"
        >
          重置
        </button>
      </div>
    </article>

    <AnalyticsErrorState
      v-if="detailStatus === 'error'"
      :message="writingDetailError"
      @retry="store.loadWritingDetail()"
    />
    <div v-else class="analytics-chart-grid writing-chart-grid">
      <article class="analytics-card analytics-chart-card">
        <h3>写作字数变化</h3>
        <AnalyticsChart
          type="bar"
          :model="buildWritingTrendModel(detailSeries)"
          :status="detailStatus"
          @retry="store.loadWritingDetail()"
        />
      </article>
      <article class="analytics-card analytics-chart-card">
        <h3>累计创作字数</h3>
        <AnalyticsChart
          type="line"
          :model="buildWritingCumulativeModel(detailSeries)"
          :status="detailStatus"
          @retry="store.loadWritingDetail()"
        />
      </article>
      <article class="analytics-card analytics-chart-card">
        <h3>来源贡献占比</h3>
        <AnalyticsChart
          type="donut"
          :model="buildWritingSourceModel(detailSeries)"
          :status="detailStatus"
          @retry="store.loadWritingDetail()"
        />
      </article>
      <article class="analytics-card analytics-chart-card">
        <h3>创作活跃日分布</h3>
        <AnalyticsChart
          type="bar"
          :model="buildWritingWeekdayModel(detailSeries)"
          :status="detailStatus"
          @retry="store.loadWritingDetail()"
        />
      </article>
    </div>
  </div>
</template>
