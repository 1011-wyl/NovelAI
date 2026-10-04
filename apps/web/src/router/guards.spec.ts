import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { NavigationGuardNext, RouteLocationNormalized } from "vue-router";
import { projectContextGuard } from "@/router/guards";
import { RouteNames } from "@/router/route-names";
import { useProjectsStore } from "@/stores/projects.store";

vi.mock("@/features/library/api/library.api", () => ({
  listNovels: vi.fn().mockResolvedValue({ items: [] }),
  renameNovel: vi.fn(),
  deleteNovel: vi.fn(),
  abortLibraryList: vi.fn(),
}));

function routeStub(partial: Partial<RouteLocationNormalized>): RouteLocationNormalized {
  return {
    path: "/",
    name: undefined,
    params: {},
    query: {},
    hash: "",
    fullPath: "/",
    matched: [],
    meta: {},
    redirectedFrom: undefined,
    ...partial,
  } as RouteLocationNormalized;
}

describe("projectContextGuard", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("redirects to library when workbench has no project context", async () => {
    const next = vi.fn() as unknown as NavigationGuardNext;
    await projectContextGuard(
      routeStub({ name: RouteNames.Workbench, params: {} }),
      routeStub({ name: RouteNames.Library }),
      next
    );
    expect(next).toHaveBeenCalledWith({ name: RouteNames.Library, replace: true });
    expect(useProjectsStore().notice).toBe("请先创建或选择一本小说");
  });

  it("redirects to selected project when route omits projectId", async () => {
    const projects = useProjectsStore();
    projects.selectProject("novel_x");
    const next = vi.fn() as unknown as NavigationGuardNext;
    await projectContextGuard(
      routeStub({ name: RouteNames.Workbench, params: {}, query: { tab: "1" } }),
      routeStub({ name: RouteNames.Library }),
      next
    );
    expect(next).toHaveBeenCalledWith({
      name: RouteNames.Workbench,
      params: { projectId: "novel_x" },
      query: { tab: "1" },
      hash: "",
      replace: true,
    });
  });

  it("redirects an explicit unknown project even when the library is empty", async () => {
    const next = vi.fn() as unknown as NavigationGuardNext;
    await projectContextGuard(
      routeStub({ name: RouteNames.Workbench, params: { projectId: "missing" } }),
      routeStub({ name: RouteNames.Library }),
      next
    );
    expect(next).toHaveBeenCalledWith({
      name: RouteNames.ProjectMissing,
      params: { projectId: "missing" },
      replace: true,
    });
  });

  it("keeps reader locked until the creative brief is confirmed", async () => {
    const projects = useProjectsStore();
    projects.items = [
      {
        id: "novel_draft",
        title: "待确认作品",
        status: "DRAFT",
        confirmed: false,
        audience_channel: "女频",
        genre: "现言",
        chapter_count: 0,
        content_chars: 0,
        current_chapter: 0,
        created_at: "2026-10-02T00:00:00Z",
        updated_at: "2026-10-02T00:00:00Z",
      },
    ];
    const next = vi.fn() as unknown as NavigationGuardNext;
    await projectContextGuard(
      routeStub({ name: RouteNames.Reader, params: { projectId: "novel_draft" } }),
      routeStub({ name: RouteNames.Workbench }),
      next
    );
    expect(next).toHaveBeenCalledWith({
      name: RouteNames.Workbench,
      params: { projectId: "novel_draft" },
      replace: true,
    });
    expect(projects.notice).toBe("请先检查并确认创作方案");
  });
});
