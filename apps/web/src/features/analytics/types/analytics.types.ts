export type AnalyticsTab = "writing" | "llm" | "records";

export type FilterOption = {
  value: string;
  label: string;
};

export type AnalyticsFilterOptions = {
  project_ids: string[];
  model_providers: string[];
  model_ids: string[];
  categories: string[];
  operations: string[];
  statuses: string[];
  project_options: FilterOption[];
  model_options: FilterOption[];
};

export type WritingTimePoint = {
  date: string;
  user_word_delta: number;
  agent_word_delta: number;
  import_word_delta: number;
};

export type WritingDashboardResponse = {
  summary: {
    active_days: number;
    creative_chapters: number;
  };
  time_series: WritingTimePoint[];
};

export type LlmSummary = {
  calls_total: number;
  success_total: number;
  tokens_total: number;
  tokens_input_total: number;
  tokens_output_total: number;
  avg_latency_ms: number | null;
  avg_first_token_ms: number | null;
};

export type LlmKeyedStat = {
  key: string;
  label: string;
  calls: number;
  tokens_total: number;
};

export type LlmModelTimePoint = {
  date: string;
  key: string;
  label: string;
  calls: number;
  tokens_total: number;
  avg_latency_ms: number | null;
};

export type LlmStatsResponse = {
  summary: LlmSummary;
  model_time_series: LlmModelTimePoint[];
  by_model: LlmKeyedStat[];
  by_project: LlmKeyedStat[];
  options: AnalyticsFilterOptions;
};

export type LlmRecordItem = {
  id: string;
  created_at: string;
  project_id: string | null;
  project_title: string | null;
  chapter_id: string | null;
  category: string;
  operation: string;
  model_id: string;
  model_provider: string;
  tokens_input: number;
  tokens_output: number;
  tokens_total: number;
  token_cache: number;
  latency_ms: number | null;
  first_token_ms: number | null;
  status: string;
  error_type: string | null;
  error_message: string | null;
  error_status_code: number | null;
  retry_count: number;
};

export type LlmRecordsResponse = {
  options: AnalyticsFilterOptions;
  records: {
    items: LlmRecordItem[];
    total: number;
    page: number;
    page_size: number;
  };
};

export type RecordsSortBy =
  | "created_at"
  | "latency_ms"
  | "first_token_ms"
  | "tokens_input"
  | "tokens_output";

export type SortOrder = "asc" | "desc";

export type LoadStatus = "idle" | "loading" | "success" | "error" | "empty";

export type AnalyticsFilters = {
  writingProjectId: string;
  writingStartDate: string;
  writingEndDate: string;
  recordsProjectId: string;
  recordsModelId: string;
  recordsProvider: string;
  recordsCategory: string;
  recordsStatus: string;
  recordsStartDate: string;
  recordsEndDate: string;
  recordsSearch: string;
  recordsPage: number;
  recordsPageSize: number;
  recordsSortBy: RecordsSortBy;
  recordsSortOrder: SortOrder;
};

export type YearMetrics = {
  activeDays: number;
  streakDays: number;
  chapters: number;
  totalWords: number;
};
