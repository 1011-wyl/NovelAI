import { buildDefaultRange } from "../../core/date.js";

export function createAnalyticsState(now = new Date()) {
  const range = buildDefaultRange();
  return {
    activeTab: "writing",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    selectedYear: now.getFullYear(),
    availableYears: [],
    writingHero: null,
    writingDetail: null,
    llmStats: null,
    records: null,
    filterOptions: null,
    filters: {
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
    },
  };
}
