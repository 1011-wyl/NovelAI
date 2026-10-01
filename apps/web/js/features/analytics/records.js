import { toIsoBoundary } from "../../core/date.js";
import { categoryLabel, operationLabel, STATUS_LABELS } from "./labels.js";

export function createRecordsController({
  state,
  api,
  charts,
  root,
  escapeHtml,
  formatNumber,
  formatSeconds,
  formatDateTime,
  isActive,
}) {
  let searchTimer = null;

  function $(selector) {
    return root.querySelector(selector);
  }

  function $$(selector) {
    return [...root.querySelectorAll(selector)];
  }

  function fillSelect(select, options, allLabel = "全部") {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${allLabel}</option>${(options || []).map((item) => {
      if (typeof item === "string") return `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`;
      return `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label || item.value)}</option>`;
    }).join("")}`;
    if ([...select.options].some((opt) => opt.value === current)) select.value = current;
  }

  function renderRecordsFilters(options) {
    fillSelect($("#recordsProjectFilter"), options?.project_options || []);
    fillSelect($("#recordsModelFilter"), (options?.model_options || []).map((item) => item.value));
    fillSelect($("#recordsProviderFilter"), options?.model_providers || []);
    fillSelect($("#recordsCategoryFilter"), (options?.categories || []).map((value) => ({ value, label: categoryLabel(value) })));
    fillSelect($("#recordsStatusFilter"), (options?.statuses || []).map((value) => ({ value, label: STATUS_LABELS[value] || value })));
  }

  function renderPagination(total, page, pageSize) {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const controls = $("#recordsPaginationControls");
    const pages = [];
    const pushPage = (p) => pages.push(p);
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i += 1) pushPage(i);
    } else {
      pushPage(1);
      if (page > 3) pages.push("…");
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i += 1) pushPage(i);
      if (page < totalPages - 2) pages.push("…");
      pushPage(totalPages);
    }
    controls.innerHTML = `
      <button type="button" class="records-page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>上一页</button>
      ${pages.map((p) => (p === "…" ? `<span>…</span>` : `<button type="button" class="records-page-btn${p === page ? " active" : ""}" data-page="${p}">${p}</button>`)).join("")}
      <button type="button" class="records-page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页</button>`;
    $$("#recordsPaginationControls .records-page-btn").forEach((btn) => btn.addEventListener("click", () => {
      const next = Number(btn.dataset.page);
      if (!Number.isFinite(next) || next < 1 || next > totalPages) return;
      state.filters.recordsPage = next;
      void loadRecords();
    }));
  }

  function renderRecordsTable() {
    const payload = state.records;
    const card = $("#recordsTableCard");
    const tbody = $("#recordsTableBody");
    const items = payload?.records?.items || [];
    const total = payload?.records?.total || 0;
    const page = payload?.records?.page || 1;
    const pageSize = payload?.records?.page_size || 20;

    $$(".records-sort").forEach((btn) => {
      const active = btn.dataset.sort === state.filters.recordsSortBy;
      btn.dataset.active = String(active);
      btn.dataset.indicator = active ? (state.filters.recordsSortOrder === "asc" ? "↑" : "↓") : "";
    });

    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="9"><div class="records-empty">没有符合条件的调用记录</div></td></tr>`;
    } else {
      tbody.innerHTML = items.map((record) => {
        const cache = record.token_cache ? `（${formatNumber(record.token_cache)}）` : "";
        const statusClass = record.status === "success" ? "success" : "failed";
        const statusText = STATUS_LABELS[record.status] || record.status;
        return `<tr>
          <td>${escapeHtml(formatDateTime(record.created_at))}</td>
          <td class="project-cell" title="${escapeHtml(record.project_title || "未归属项目")}">${escapeHtml(record.project_title || "未归属项目")}</td>
          <td>${escapeHtml(record.model_id || "—")}</td>
          <td>${escapeHtml(`${categoryLabel(record.category)} / ${operationLabel(record)}`)}</td>
          <td>${escapeHtml(formatSeconds(record.latency_ms))}</td>
          <td>${escapeHtml(formatSeconds(record.first_token_ms))}</td>
          <td>${escapeHtml(`${formatNumber(record.tokens_input)}${cache}`)}</td>
          <td>${escapeHtml(formatNumber(record.tokens_output))}</td>
          <td><span class="status-badge ${statusClass}">${escapeHtml(statusText)}</span></td>
        </tr>`;
      }).join("");
    }

    const start = total ? (page - 1) * pageSize + 1 : 0;
    const end = total ? Math.min(page * pageSize, total) : 0;
    $("#recordsRangeText").textContent = `第 ${start}–${end} 条，共 ${formatNumber(total)} 条`;
    renderPagination(total, page, pageSize);
    card?.classList.remove("is-loading");
  }

  function recordsQueryParams() {
    const f = state.filters;
    const query = new URLSearchParams({
      page: String(f.recordsPage),
      page_size: String(f.recordsPageSize),
      sort_by: f.recordsSortBy,
      sort_order: f.recordsSortOrder,
    });
    if (f.recordsProjectId) query.set("project_id", f.recordsProjectId);
    if (f.recordsModelId) query.set("model_id", f.recordsModelId);
    if (f.recordsProvider) query.set("model_provider", f.recordsProvider);
    if (f.recordsCategory) query.set("category", f.recordsCategory);
    if (f.recordsStatus) query.set("status", f.recordsStatus);
    if (f.recordsStartDate) query.set("start_at", toIsoBoundary(f.recordsStartDate, "start"));
    if (f.recordsEndDate) query.set("end_at", toIsoBoundary(f.recordsEndDate, "end"));
    if (f.recordsSearch.trim()) query.set("search", f.recordsSearch.trim());
    return query;
  }

  async function loadRecords({ allowPageCorrection = true } = {}) {
    $("#recordsTableCard")?.classList.add("is-loading");
    try {
      const data = await api.loadRecords(recordsQueryParams());
      if (!isActive() || state.activeTab !== "records") return;
      const total = data?.records?.total || 0;
      const pageSize = data?.records?.page_size || state.filters.recordsPageSize || 20;
      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      if (allowPageCorrection && state.filters.recordsPage > totalPages) {
        state.filters.recordsPage = totalPages;
        return loadRecords({ allowPageCorrection: false });
      }
      state.records = data;
      state.filterOptions = data.options || state.filterOptions;
      renderRecordsFilters(data.options);
      renderRecordsTable();
    } catch (error) {
      if (error.stale) return;
      $("#recordsTableBody").innerHTML = `<tr><td colspan="9"><div class="records-empty">${escapeHtml(error.message || "加载失败")} <button type="button" class="button ghost" id="recordsRetryBtn">重试</button></div></td></tr>`;
      $("#recordsRetryBtn")?.addEventListener("click", () => void loadRecords());
      $("#recordsTableCard")?.classList.remove("is-loading");
    }
  }

  function syncRecordsFilterInputs() {
    const map = {
      recordsProjectFilter: "recordsProjectId",
      recordsModelFilter: "recordsModelId",
      recordsProviderFilter: "recordsProvider",
      recordsCategoryFilter: "recordsCategory",
      recordsStatusFilter: "recordsStatus",
      recordsStartDate: "recordsStartDate",
      recordsEndDate: "recordsEndDate",
      recordsSearch: "recordsSearch",
    };
    Object.entries(map).forEach(([id, key]) => {
      const el = $(`#${id}`);
      if (el) el.value = state.filters[key];
    });
  }

  function resetRecordsFilters() {
    state.filters.recordsProjectId = "";
    state.filters.recordsModelId = "";
    state.filters.recordsProvider = "";
    state.filters.recordsCategory = "";
    state.filters.recordsStatus = "";
    state.filters.recordsStartDate = "";
    state.filters.recordsEndDate = "";
    state.filters.recordsSearch = "";
    state.filters.recordsPage = 1;
    state.filters.recordsSortBy = "created_at";
    state.filters.recordsSortOrder = "desc";
    syncRecordsFilterInputs();
    void loadRecords();
  }

  function clearSearchTimer() {
    clearTimeout(searchTimer);
    searchTimer = null;
  }

  function bind(signal) {
    const opts = signal ? { signal } : undefined;
    const recordsFilterChange = (key, event) => {
      state.filters[key] = event.target.value;
      state.filters.recordsPage = 1;
      void loadRecords();
    };
    $("#recordsProjectFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsProjectId", e), opts);
    $("#recordsModelFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsModelId", e), opts);
    $("#recordsProviderFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsProvider", e), opts);
    $("#recordsCategoryFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsCategory", e), opts);
    $("#recordsStatusFilter")?.addEventListener("change", (e) => recordsFilterChange("recordsStatus", e), opts);
    $("#recordsStartDate")?.addEventListener("change", (e) => recordsFilterChange("recordsStartDate", e), opts);
    $("#recordsEndDate")?.addEventListener("change", (e) => recordsFilterChange("recordsEndDate", e), opts);
    $("#recordsSearch")?.addEventListener("input", (event) => {
      state.filters.recordsSearch = event.target.value;
      state.filters.recordsPage = 1;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => void loadRecords(), 300);
    }, opts);
    $("#recordsFilterReset")?.addEventListener("click", resetRecordsFilters, opts);

    $$(".records-sort").forEach((btn) => btn.addEventListener("click", () => {
      const field = btn.dataset.sort;
      if (state.filters.recordsSortBy === field) {
        state.filters.recordsSortOrder = state.filters.recordsSortOrder === "asc" ? "desc" : "asc";
      } else {
        state.filters.recordsSortBy = field;
        state.filters.recordsSortOrder = "desc";
      }
      state.filters.recordsPage = 1;
      void loadRecords();
    }, opts));

    syncRecordsFilterInputs();
  }

  function refresh() {
    void loadRecords();
  }

  function destroy() {
    clearSearchTimer();
  }

  return {
    loadRecords,
    bind,
    refresh,
    destroy,
    clearSearchTimer,
    resetRecordsFilters,
    syncRecordsFilterInputs,
    fillSelect,
    renderRecordsFilters,
    renderRecordsTable,
    renderPagination,
    recordsQueryParams,
  };
}
