import { computed, ref, watch } from "vue";
import { defineStore } from "pinia";
import type { ProjectSummary } from "@/api/contracts";
import { ApiError, isApiError } from "@/api/api-error";
import {
  deleteNovel,
  listNovels,
  renameNovel,
} from "@/features/library/api/library.api";

export const PROJECT_STORAGE_KEY = "novelAgentProject";
export const LIBRARY_VIEW_KEY = "novelAgentLibraryView";
export const LIBRARY_SORT_KEY = "novelAgentLibrarySort";

export type LibrarySortBy = "updated_at" | "created_at" | "title";
export type LibraryViewMode = "grid" | "list";

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* ignore quota / private mode */
  }
}

export function mapShelfStatus(project: Pick<ProjectSummary, "status" | "confirmed">): {
  label: string;
  tone: "neutral" | "success" | "warning" | "danger" | "muted";
} {
  if (project.status === "DRAFT" && !project.confirmed) {
    return { label: "待确认方案", tone: "warning" };
  }
  switch (project.status) {
    case "ACTIVE":
      return { label: "创作中", tone: "success" };
    case "PAUSED":
      return { label: "已暂停", tone: "muted" };
    case "HUMAN_REQUIRED":
      return { label: "需要处理", tone: "danger" };
    case "ARCHIVED":
      return { label: "已归档", tone: "muted" };
    case "DRAFT":
      return { label: "待确认方案", tone: "warning" };
    default:
      return { label: project.status, tone: "neutral" };
  }
}

export const useProjectsStore = defineStore("projects", () => {
  const items = ref<ProjectSummary[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const selectedProjectId = ref<string | null>(readStorage(PROJECT_STORAGE_KEY));
  const searchQuery = ref("");
  const sortBy = ref<LibrarySortBy>(
    (readStorage(LIBRARY_SORT_KEY) as LibrarySortBy) || "updated_at"
  );
  const viewMode = ref<LibraryViewMode>(
    (readStorage(LIBRARY_VIEW_KEY) as LibraryViewMode) || "grid"
  );
  const notice = ref<string | null>(null);

  watch(selectedProjectId, (id) => writeStorage(PROJECT_STORAGE_KEY, id), { flush: "sync" });
  watch(sortBy, (value) => writeStorage(LIBRARY_SORT_KEY, value), { flush: "sync" });
  watch(viewMode, (value) => writeStorage(LIBRARY_VIEW_KEY, value), { flush: "sync" });

  const selectedProject = computed(
    () => items.value.find((item) => item.id === selectedProjectId.value) ?? null
  );

  const filteredProjects = computed(() => {
    const q = searchQuery.value.trim().toLowerCase();
    let list = items.value.slice();
    if (q) {
      list = list.filter(
        (item) =>
          item.title.toLowerCase().includes(q) || item.genre.toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      if (sortBy.value === "title") {
        return a.title.localeCompare(b.title, "zh-CN");
      }
      const left = sortBy.value === "created_at" ? a.created_at : a.updated_at;
      const right = sortBy.value === "created_at" ? b.created_at : b.updated_at;
      return right.localeCompare(left);
    });
    return list;
  });

  function setNotice(message: string | null) {
    notice.value = message;
  }

  function clearNotice() {
    notice.value = null;
  }

  function selectProject(id: string | null) {
    selectedProjectId.value = id;
  }

  function clearSelection() {
    selectedProjectId.value = null;
  }

  function migrateLegacySelection() {
    const legacy = readStorage(PROJECT_STORAGE_KEY);
    if (legacy && !selectedProjectId.value) {
      selectedProjectId.value = legacy;
    }
  }

  function validateSelectionAgainstItems() {
    if (!selectedProjectId.value) return;
    if (!items.value.some((item) => item.id === selectedProjectId.value)) {
      clearSelection();
    }
  }

  async function loadProjects() {
    loading.value = true;
    error.value = null;
    try {
      migrateLegacySelection();
      const response = await listNovels();
      items.value = response.items;
      validateSelectionAgainstItems();
    } catch (err) {
      if (isApiError(err) && err.kind === "aborted") return;
      error.value = err instanceof Error ? err.message : "加载书架失败";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function renameProject(id: string, title: string) {
    const updated = await renameNovel(id, title);
    const index = items.value.findIndex((item) => item.id === id);
    if (index >= 0) items.value[index] = updated;
    else items.value.unshift(updated);
    return updated;
  }

  async function deleteProject(id: string, confirmationTitle?: string) {
    await deleteNovel(id, confirmationTitle);
    items.value = items.value.filter((item) => item.id !== id);
    if (selectedProjectId.value === id) {
      clearSelection();
    }
  }

  function upsertProject(summary: ProjectSummary) {
    const index = items.value.findIndex((item) => item.id === summary.id);
    if (index >= 0) items.value[index] = summary;
    else items.value.unshift(summary);
  }

  function requiresTitleConfirmation(project: ProjectSummary): boolean {
    return !(project.status === "DRAFT" && !project.confirmed && project.chapter_count === 0);
  }

  return {
    items,
    loading,
    error,
    selectedProjectId,
    selectedProject,
    searchQuery,
    sortBy,
    viewMode,
    notice,
    filteredProjects,
    setNotice,
    clearNotice,
    selectProject,
    clearSelection,
    loadProjects,
    renameProject,
    deleteProject,
    upsertProject,
    requiresTitleConfirmation,
    migrateLegacySelection,
    validateSelectionAgainstItems,
  };
});

export function toUserError(error: unknown, fallback = "操作失败"): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}
