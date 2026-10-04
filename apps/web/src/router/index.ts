import { createRouter, createWebHistory } from "vue-router";
import { RouteNames } from "./route-names";
import { projectContextGuard } from "./guards";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/novels",
    },
    {
      path: "/novels",
      name: RouteNames.Library,
      component: () => import("@/features/library/pages/NovelLibraryPage.vue"),
      meta: { title: "我的小说" },
    },
    {
      path: "/novels/new",
      name: RouteNames.NovelCreate,
      component: () => import("@/features/novel-create/pages/NovelCreatePage.vue"),
      meta: { title: "创建小说" },
    },
    {
      path: "/novels/:projectId/workbench",
      name: RouteNames.Workbench,
      component: () => import("@/features/workbench/pages/WorkbenchPage.vue"),
      meta: { title: "创作工作台", projectScoped: true },
    },
    {
      path: "/novels/:projectId/reader",
      name: RouteNames.Reader,
      component: () => import("@/features/reader/pages/ReaderPage.vue"),
      meta: { title: "作品阅读", projectScoped: true, fullBleed: true },
    },
    {
      path: "/novels/:projectId/memory",
      name: RouteNames.Memory,
      component: () => import("@/features/memory/pages/MemoryPage.vue"),
      meta: { title: "长期记忆", projectScoped: true },
    },
    {
      path: "/novels/:projectId/missing",
      name: RouteNames.ProjectMissing,
      component: () => import("@/features/library/pages/ProjectMissingPage.vue"),
      meta: { title: "项目不存在" },
    },
    {
      path: "/analytics",
      name: RouteNames.Analytics,
      component: () => import("@/features/analytics/pages/AnalyticsPage.vue"),
      meta: { title: "仪表盘", fullBleed: true },
    },
    {
      path: "/settings",
      name: RouteNames.Settings,
      component: () => import("@/features/settings/pages/SettingsPage.vue"),
      meta: { title: "系统设置" },
    },
    {
      path: "/:pathMatch(.*)*",
      name: RouteNames.NotFound,
      component: () => import("@/features/library/pages/NotFoundPage.vue"),
      meta: { title: "页面不存在" },
    },
  ],
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach(projectContextGuard);

router.afterEach((to) => {
  const title = typeof to.meta.title === "string" ? to.meta.title : "Novel Agent";
  document.title = `${title} · Novel Agent`;
});

export default router;
