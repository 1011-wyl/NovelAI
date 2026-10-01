export function createAnalyticsApi(request) {
  const controllers = {
    writingHero: null,
    writingDetail: null,
    llm: null,
    records: null,
    options: null,
  };
  const requestIds = {
    writingHero: 0,
    writingDetail: 0,
    llm: 0,
    records: 0,
    options: 0,
  };
  let filterOptions = null;

  function abort(key) {
    if (controllers[key]) {
      controllers[key].abort();
      controllers[key] = null;
    }
    // Invalidate in-flight work even if the transport ignores AbortSignal.
    requestIds[key] += 1;
  }

  function abortAll() {
    Object.keys(controllers).forEach(abort);
  }

  async function fetchJson(path, key) {
    abort(key);
    const controller = new AbortController();
    controllers[key] = controller;
    const id = ++requestIds[key];
    try {
      const payload = await request(path, { signal: controller.signal });
      if (id !== requestIds[key]) {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      throw error;
    }
  }

  function invalidateFilterOptions() {
    filterOptions = null;
  }

  async function ensureFilterOptions() {
    if (filterOptions) return filterOptions;
    const data = await fetchJson("/api/dashboard/llm-api/stats", "options");
    filterOptions = data.options;
    return filterOptions;
  }

  async function loadWriting(query, scope = "writingDetail") {
    const params = query instanceof URLSearchParams ? query : new URLSearchParams(query || {});
    return fetchJson(`/api/dashboard/writing?${params}`, scope);
  }

  async function loadLlmStats() {
    return fetchJson("/api/dashboard/llm-api/stats", "llm");
  }

  async function loadRecords(query) {
    const params = query instanceof URLSearchParams ? query : new URLSearchParams(query || {});
    return fetchJson(`/api/dashboard/llm-api/records?${params}`, "records");
  }

  return {
    abort,
    abortAll,
    fetchJson,
    ensureFilterOptions,
    invalidateFilterOptions,
    loadWriting,
    loadLlmStats,
    loadRecords,
  };
}
