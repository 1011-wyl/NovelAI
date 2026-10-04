export const RouteNames = {
  Library: "library",
  NovelCreate: "novel-create",
  Workbench: "workbench",
  Reader: "reader",
  Memory: "memory",
  Analytics: "analytics",
  Settings: "settings",
  NotFound: "not-found",
  ProjectMissing: "project-missing",
} as const;

export type RouteName = (typeof RouteNames)[keyof typeof RouteNames];

export const PROJECT_SCOPED_ROUTES = new Set<string>([
  RouteNames.Workbench,
  RouteNames.Reader,
  RouteNames.Memory,
]);
