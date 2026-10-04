import { defineStore } from "pinia";
import { ApiError } from "@/api/api-error";
import {
  abortAnalyticsRequests,
  fetchFilterOptions,
  fetchLlmRecords,
  fetchLlmStats,
  fetchWritingDashboard,
} from "../api/analytics.api";
import { buildDefaultRange, toIsoBoundary } from "../lib/date";
import { deriveYears } from "../lib/selectors";
import type {
  AnalyticsFilterOptions,
  AnalyticsFilters,
  AnalyticsTab,
  LlmRecordsResponse,
  LlmStatsResponse,
  LoadStatus,
  RecordsSortBy,
  WritingDashboardResponse,
} from "../types/analytics.types";

function defaultFilters(): AnalyticsFilters {
  const range = buildDefaultRange();
  return {
    writingProjectId: "",
    writingStartDate: range.start,
    writingEndDate: range.end,
    recordsProjectId: "",
    recordsModelId: "",
    recordsProvider: "",
    recordsCategory: "",
    recordsStatus: "",
    recordsStartDate: "",
    recordsEndDate: "",
    recordsSearch: "",
    recordsPage: 1,
    recordsPageSize: 20,
    recordsSortBy: "created_at",
    recordsSortOrder: "desc",
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === "aborted") return "";
    return error.message;
  }
  if (error instanceof Error) return error.message || "加载失败";
  return "加载失败";
}

export const useAnalyticsStore = defineStore("analytics", {
  state: () => ({
    activeTab: "writing" as AnalyticsTab,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    selectedYear: new Date().getFullYear(),
    availableYears: [] as number[],
    filters: defaultFilters(),
    filterOptions: null as AnalyticsFilterOptions | null,
    writingHero: null as WritingDashboardResponse | null,
    writingDetail: null as WritingDashboardResponse | null,
    llmStats: null as LlmStatsResponse | null,
    records: null as LlmRecordsResponse | null,
    writingHeroStatus: "idle" as LoadStatus,
    writingDetailStatus: "idle" as LoadStatus,
    llmStatus: "idle" as LoadStatus,
    recordsStatus: "idle" as LoadStatus,
    writingHeroError: "",
    writingDetailError: "",
    llmError: "",
    recordsError: "",
    searchTimer: null as ReturnType<typeof setTimeout> | null,
  }),
  actions: {
    setTab(tab: AnalyticsTab) {
      if (this.activeTab === tab) return;
      abortAnalyticsRequests();
      this.activeTab = tab;
      void this.loadActiveTab();
    },

    async loadActiveTab() {
      if (this.activeTab === "writing") {
        await Promise.all([this.loadWritingHero(), this.loadWritingDetail()]);
      } else if (this.activeTab === "llm") {
        await this.loadLlm();
      } else {
        await this.loadRecords();
      }
    },

    async ensureFilterOptions() {
      if (this.filterOptions) return this.filterOptions;
      try {
        this.filterOptions = await fetchFilterOptions();
      } catch (error) {
        if (error instanceof ApiError && error.kind === "aborted") return null;
        throw error;
      }
      return this.filterOptions;
    },

    async loadWritingHero() {
      this.writingHeroStatus = "loading";
      this.writingHeroError = "";
      const year = this.selectedYear;
      try {
        const data = await fetchWritingDashboard(
          {
            timezone: this.timezone,
            start_at: `${year}-01-01T00:00:00`,
            end_at: `${year}-12-31T23:59:59`,
          },
          "hero"
        );
        if (this.activeTab !== "writing") return;
        this.writingHero = data;
        this.availableYears = deriveYears(data.time_series);
        if (!this.availableYears.includes(this.selectedYear) && this.availableYears.length) {
          this.selectedYear = this.availableYears[0];
        }
        this.writingHeroStatus = "success";
      } catch (error) {
        const message = errorMessage(error);
        if (!message) return;
        if (this.activeTab !== "writing") return;
        this.writingHeroError = message;
        this.writingHeroStatus = "error";
      }
    },

    async loadWritingDetail() {
      this.writingDetailStatus = "loading";
      this.writingDetailError = "";
      try {
        await this.ensureFilterOptions();
        const data = await fetchWritingDashboard(
          {
            timezone: this.timezone,
            start_at: toIsoBoundary(this.filters.writingStartDate, "start") || "",
            end_at: toIsoBoundary(this.filters.writingEndDate, "end") || "",
            project_id: this.filters.writingProjectId || undefined,
          },
          "detail"
        );
        if (this.activeTab !== "writing") return;
        this.writingDetail = data;
        const empty = !(data.time_series || []).some(
          (item) =>
            item.user_word_delta > 0 || item.agent_word_delta > 0 || item.import_word_delta > 0
        );
        this.writingDetailStatus = empty ? "empty" : "success";
      } catch (error) {
        const message = errorMessage(error);
        if (!message) return;
        if (this.activeTab !== "writing") return;
        this.writingDetailError = message;
        this.writingDetailStatus = "error";
      }
    },

    async loadLlm() {
      this.llmStatus = "loading";
      this.llmError = "";
      try {
        const data = await fetchLlmStats();
        if (this.activeTab !== "llm") return;
        this.llmStats = data;
        this.filterOptions = data.options;
        this.llmStatus = data.summary?.calls_total ? "success" : "empty";
      } catch (error) {
        const message = errorMessage(error);
        if (!message) return;
        if (this.activeTab !== "llm") return;
        this.llmError = message;
        this.llmStatus = "error";
      }
    },

    async loadRecords() {
      this.recordsStatus = "loading";
      this.recordsError = "";
      const f = this.filters;
      try {
        const data = await fetchLlmRecords({
          page: f.recordsPage,
          page_size: f.recordsPageSize,
          sort_by: f.recordsSortBy,
          sort_order: f.recordsSortOrder,
          project_id: f.recordsProjectId || undefined,
          model_id: f.recordsModelId || undefined,
          model_provider: f.recordsProvider || undefined,
          category: f.recordsCategory || undefined,
          status: f.recordsStatus || undefined,
          start_at: toIsoBoundary(f.recordsStartDate, "start"),
          end_at: toIsoBoundary(f.recordsEndDate, "end"),
          search: f.recordsSearch.trim() || undefined,
        });
        if (this.activeTab !== "records") return;
        this.records = data;
        this.filterOptions = data.options;
        const total = data.records?.total || 0;
        const page = data.records?.page || 1;
        const pageSize = data.records?.page_size || f.recordsPageSize;
        const totalPages = Math.max(1, Math.ceil(total / pageSize));
        if (page > totalPages) {
          this.filters.recordsPage = totalPages;
          await this.loadRecords();
          return;
        }
        this.recordsStatus = total === 0 ? "empty" : "success";
      } catch (error) {
        const message = errorMessage(error);
        if (!message) return;
        if (this.activeTab !== "records") return;
        this.recordsError = message;
        this.recordsStatus = "error";
      }
    },

    selectYear(year: number) {
      if (this.selectedYear === year) return;
      this.selectedYear = year;
      void this.loadWritingHero();
    },

    updateWritingFilters(partial: Partial<Pick<AnalyticsFilters, "writingProjectId" | "writingStartDate" | "writingEndDate">>) {
      Object.assign(this.filters, partial);
      void this.loadWritingDetail();
    },

    resetWritingFilters() {
      const range = buildDefaultRange();
      this.filters.writingProjectId = "";
      this.filters.writingStartDate = range.start;
      this.filters.writingEndDate = range.end;
      void this.loadWritingDetail();
    },

    updateRecordsFilters(
      partial: Partial<
        Omit<AnalyticsFilters, "recordsPageSize" | "recordsSortBy" | "recordsSortOrder" | "writingProjectId" | "writingStartDate" | "writingEndDate">
      > & { resetPage?: boolean }
    ) {
      const { resetPage = true, ...rest } = partial;
      Object.assign(this.filters, rest);
      if (resetPage) this.filters.recordsPage = 1;
      void this.loadRecords();
    },

    scheduleRecordsSearch(value: string) {
      this.filters.recordsSearch = value;
      if (this.searchTimer) clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => {
        this.filters.recordsPage = 1;
        void this.loadRecords();
      }, 300);
    },

    toggleRecordsSort(sortBy: RecordsSortBy) {
      if (this.filters.recordsSortBy === sortBy) {
        this.filters.recordsSortOrder = this.filters.recordsSortOrder === "asc" ? "desc" : "asc";
      } else {
        this.filters.recordsSortBy = sortBy;
        this.filters.recordsSortOrder = "desc";
      }
      this.filters.recordsPage = 1;
      void this.loadRecords();
    },

    setRecordsPage(page: number) {
      this.filters.recordsPage = page;
      void this.loadRecords();
    },

    resetRecordsFilters() {
      this.filters.recordsProjectId = "";
      this.filters.recordsModelId = "";
      this.filters.recordsProvider = "";
      this.filters.recordsCategory = "";
      this.filters.recordsStatus = "";
      this.filters.recordsStartDate = "";
      this.filters.recordsEndDate = "";
      this.filters.recordsSearch = "";
      this.filters.recordsPage = 1;
      this.filters.recordsSortBy = "created_at";
      this.filters.recordsSortOrder = "desc";
      void this.loadRecords();
    },

    reset() {
      if (this.searchTimer) clearTimeout(this.searchTimer);
      abortAnalyticsRequests();
      this.$reset();
    },
  },
});
