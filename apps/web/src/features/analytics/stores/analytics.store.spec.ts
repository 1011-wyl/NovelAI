import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useAnalyticsStore } from "./analytics.store";
import * as api from "../api/analytics.api";
import { ApiError } from "@/api/api-error";

vi.mock("../api/analytics.api", () => ({
  fetchWritingDashboard: vi.fn(),
  fetchLlmStats: vi.fn(),
  fetchLlmRecords: vi.fn(),
  fetchFilterOptions: vi.fn(),
  abortAnalyticsRequests: vi.fn(),
}));

const emptyWriting = {
  summary: { active_days: 0, creative_chapters: 0 },
  time_series: [],
};

const filterOptions = {
  project_ids: [],
  model_providers: [],
  model_ids: [],
  categories: ["agent"],
  operations: [],
  statuses: ["success"],
  project_options: [{ value: "p1", label: "测试小说" }],
  model_options: [],
};

describe("useAnalyticsStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(api.fetchFilterOptions).mockResolvedValue(filterOptions);
    vi.mocked(api.fetchWritingDashboard).mockResolvedValue(emptyWriting);
    vi.mocked(api.fetchLlmStats).mockResolvedValue({
      summary: {
        calls_total: 0,
        success_total: 0,
        tokens_total: 0,
        tokens_input_total: 0,
        tokens_output_total: 0,
        avg_latency_ms: null,
        avg_first_token_ms: null,
      },
      model_time_series: [],
      by_model: [],
      by_project: [],
      options: filterOptions,
    });
    vi.mocked(api.fetchLlmRecords).mockResolvedValue({
      options: filterOptions,
      records: { items: [], total: 0, page: 1, page_size: 20 },
    });
  });

  it("switches tabs via Vue reactive state and loads the active tab", async () => {
    const store = useAnalyticsStore();
    expect(store.activeTab).toBe("writing");
    store.setTab("records");
    expect(store.activeTab).toBe("records");
    await vi.waitFor(() => expect(api.fetchLlmRecords).toHaveBeenCalled());
  });

  it("keeps filters after a failed request and supports retry", async () => {
    const store = useAnalyticsStore();
    store.filters.writingProjectId = "p1";
    vi.mocked(api.fetchWritingDashboard).mockRejectedValueOnce(
      new ApiError("网络失败", { kind: "network" })
    );
    await store.loadWritingDetail();
    expect(store.writingDetailStatus).toBe("error");
    expect(store.filters.writingProjectId).toBe("p1");
    vi.mocked(api.fetchWritingDashboard).mockResolvedValueOnce({
      summary: { active_days: 1, creative_chapters: 1 },
      time_series: [
        { date: "2026-10-01", user_word_delta: 100, agent_word_delta: 0, import_word_delta: 0 },
      ],
    });
    await store.loadWritingDetail();
    expect(store.writingDetailStatus).toBe("success");
    expect(store.filters.writingProjectId).toBe("p1");
  });

  it("ignores stale aborted responses when switching tabs quickly", async () => {
    const store = useAnalyticsStore();
    vi.mocked(api.fetchWritingDashboard).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          setTimeout(() => reject(new ApiError("请求已过期", { kind: "aborted" })), 10);
        })
    );
    const writingPromise = store.loadWritingDetail();
    store.setTab("llm");
    await writingPromise;
    expect(store.activeTab).toBe("llm");
    expect(store.writingDetailStatus).not.toBe("error");
    expect(store.writingDetail).toBeNull();
  });

  it("toggles records sort and resets page", async () => {
    const store = useAnalyticsStore();
    store.filters.recordsPage = 3;
    store.toggleRecordsSort("tokens_input");
    expect(store.filters.recordsSortBy).toBe("tokens_input");
    expect(store.filters.recordsSortOrder).toBe("desc");
    expect(store.filters.recordsPage).toBe(1);
    await vi.waitFor(() => expect(api.fetchLlmRecords).toHaveBeenCalled());
  });
});
