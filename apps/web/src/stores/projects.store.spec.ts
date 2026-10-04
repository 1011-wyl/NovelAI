import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import {
  PROJECT_STORAGE_KEY,
  useProjectsStore,
  mapShelfStatus,
} from "@/stores/projects.store";
import type { ProjectSummary } from "@/api/contracts";

vi.mock("@/features/library/api/library.api", () => ({
  listNovels: vi.fn(),
  renameNovel: vi.fn(),
  deleteNovel: vi.fn(),
  abortLibraryList: vi.fn(),
}));

import { listNovels, deleteNovel } from "@/features/library/api/library.api";

const sample = (overrides: Partial<ProjectSummary> = {}): ProjectSummary => ({
  id: "novel_1",
  title: "长夜征途",
  status: "ACTIVE",
  confirmed: true,
  audience_channel: "男频",
  genre: "玄幻脑洞",
  chapter_count: 3,
  content_chars: 6812,
  current_chapter: 3,
  created_at: "2026-10-01T08:00:00Z",
  updated_at: "2026-10-02T09:30:00Z",
  ...overrides,
});

describe("projects.store", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.mocked(listNovels).mockReset();
    vi.mocked(deleteNovel).mockReset();
  });

  it("migrates novelAgentProject from localStorage", async () => {
    localStorage.setItem(PROJECT_STORAGE_KEY, "novel_1");
    vi.mocked(listNovels).mockResolvedValue({
      items: [sample(), sample({ id: "novel_2", title: "另一本" })],
    });
    const store = useProjectsStore();
    expect(store.selectedProjectId).toBe("novel_1");
    await store.loadProjects();
    expect(store.selectedProjectId).toBe("novel_1");
  });

  it("clears invalid migrated selection after load", async () => {
    localStorage.setItem(PROJECT_STORAGE_KEY, "missing");
    vi.mocked(listNovels).mockResolvedValue({ items: [sample()] });
    const store = useProjectsStore();
    await store.loadProjects();
    expect(store.selectedProjectId).toBeNull();
  });

  it("filters by search and sorts by title", async () => {
    vi.mocked(listNovels).mockResolvedValue({
      items: [
        sample({ id: "b", title: "北斗", genre: "科幻", updated_at: "2026-10-01T00:00:00Z" }),
        sample({ id: "a", title: "安河", genre: "玄幻脑洞", updated_at: "2026-10-03T00:00:00Z" }),
      ],
    });
    const store = useProjectsStore();
    await store.loadProjects();
    store.searchQuery = "玄幻";
    expect(store.filteredProjects.map((item) => item.id)).toEqual(["a"]);
    store.searchQuery = "";
    store.sortBy = "title";
    expect(store.filteredProjects.map((item) => item.title)).toEqual(["安河", "北斗"]);
  });

  it("persists viewMode preference", () => {
    const store = useProjectsStore();
    store.viewMode = "list";
    expect(localStorage.getItem("novelAgentLibraryView")).toBe("list");
  });

  it("clears selection when deleting current project", async () => {
    vi.mocked(listNovels).mockResolvedValue({ items: [sample()] });
    vi.mocked(deleteNovel).mockResolvedValue(undefined);
    const store = useProjectsStore();
    await store.loadProjects();
    store.selectProject("novel_1");
    await store.deleteProject("novel_1", "长夜征途");
    expect(store.selectedProjectId).toBeNull();
    expect(store.items).toHaveLength(0);
  });

  it("maps shelf status labels", () => {
    expect(mapShelfStatus({ status: "DRAFT", confirmed: false }).label).toBe("待确认方案");
    expect(mapShelfStatus({ status: "ACTIVE", confirmed: true }).label).toBe("创作中");
    expect(mapShelfStatus({ status: "PAUSED", confirmed: true }).label).toBe("已暂停");
    expect(mapShelfStatus({ status: "HUMAN_REQUIRED", confirmed: true }).label).toBe("需要处理");
    expect(mapShelfStatus({ status: "ARCHIVED", confirmed: true }).label).toBe("已归档");
  });
});
