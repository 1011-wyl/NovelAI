import type { NavigationGuardNext, RouteLocationNormalized } from "vue-router";
import { useProjectsStore } from "@/stores/projects.store";
import { PROJECT_SCOPED_ROUTES, RouteNames } from "./route-names";

const CONFIRMED_ONLY_ROUTES = new Set<string>([
  RouteNames.Reader,
  RouteNames.Memory,
]);

export async function projectContextGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext
) {
  const projects = useProjectsStore();
  const name = String(to.name || "");

  if (PROJECT_SCOPED_ROUTES.has(name)) {
    const paramId = typeof to.params.projectId === "string" ? to.params.projectId : "";
    if (paramId) {
      let canValidateProject = projects.items.length > 0;
      if (!canValidateProject) {
        try {
          await projects.loadProjects();
          canValidateProject = true;
        } catch {
          /* load error handled by page */
        }
      }
      const project = projects.items.find((item) => item.id === paramId);
      if (canValidateProject && !project) {
        next({ name: RouteNames.ProjectMissing, params: { projectId: paramId }, replace: true });
        return;
      }
      projects.selectProject(paramId);
      if (project && CONFIRMED_ONLY_ROUTES.has(name) && !project.confirmed) {
        projects.setNotice("请先检查并确认创作方案");
        next({
          name: RouteNames.Workbench,
          params: { projectId: paramId },
          replace: true,
        });
        return;
      }
      next();
      return;
    }

    const recent = projects.selectedProjectId;
    if (recent) {
      next({
        name,
        params: { projectId: recent },
        query: to.query,
        hash: to.hash,
        replace: true,
      });
      return;
    }

    projects.setNotice("请先创建或选择一本小说");
    next({ name: RouteNames.Library, replace: true });
    return;
  }

  next();
}
