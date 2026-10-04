import { createCancellableGetter, requestJson } from "@/api/http-client";
import type {
  LlmRecordsResponse,
  LlmStatsResponse,
  WritingDashboardResponse,
} from "../types/analytics.types";

const writingHeroGetter = createCancellableGetter();
const writingDetailGetter = createCancellableGetter();
const llmGetter = createCancellableGetter();
const recordsGetter = createCancellableGetter();
const optionsGetter = createCancellableGetter();

export type WritingQuery = {
  timezone: string;
  start_at: string;
  end_at: string;
  project_id?: string;
};

export type RecordsQuery = {
  page: number;
  page_size: number;
  sort_by: string;
  sort_order: string;
  project_id?: string;
  model_id?: string;
  model_provider?: string;
  category?: string;
  status?: string;
  start_at?: string;
  end_at?: string;
  search?: string;
};

function toSearchParams(query: Record<string, string | number | undefined>): URLSearchParams {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === "") return;
    params.set(key, String(value));
  });
  return params;
}

export async function fetchWritingDashboard(
  query: WritingQuery,
  scope: "hero" | "detail" = "detail"
): Promise<WritingDashboardResponse> {
  const getter = scope === "hero" ? writingHeroGetter : writingDetailGetter;
  const params = toSearchParams(query);
  return getter.run((signal) =>
    requestJson<WritingDashboardResponse>(`/api/dashboard/writing?${params}`, { signal })
  );
}

export async function fetchLlmStats(): Promise<LlmStatsResponse> {
  return llmGetter.run((signal) =>
    requestJson<LlmStatsResponse>("/api/dashboard/llm-api/stats", { signal })
  );
}

export async function fetchLlmRecords(query: RecordsQuery): Promise<LlmRecordsResponse> {
  const params = toSearchParams(query);
  return recordsGetter.run((signal) =>
    requestJson<LlmRecordsResponse>(`/api/dashboard/llm-api/records?${params}`, { signal })
  );
}

export async function fetchFilterOptions(): Promise<LlmStatsResponse["options"]> {
  const data = await optionsGetter.run((signal) =>
    requestJson<LlmStatsResponse>("/api/dashboard/llm-api/stats", { signal })
  );
  return data.options;
}

export function abortAnalyticsRequests() {
  writingHeroGetter.abort();
  writingDetailGetter.abort();
  llmGetter.abort();
  recordsGetter.abort();
  optionsGetter.abort();
}
