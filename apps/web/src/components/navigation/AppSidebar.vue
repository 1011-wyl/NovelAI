<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import {
  BookOpen,
  LayoutDashboard,
  Library,
  MemoryStick,
  PanelLeftClose,
  Settings,
  PenLine,
} from "lucide-vue-next";
import BaseIconButton from "@/components/base/BaseIconButton.vue";
import { useAppStore } from "@/stores/app.store";
import { useProjectsStore } from "@/stores/projects.store";
import { RouteNames } from "@/router/route-names";

const app = useAppStore();
const projects = useProjectsStore();
const route = useRoute();
const router = useRouter();

const projectId = computed(() => {
  const param = route.params.projectId;
  if (typeof param === "string" && param) return param;
  return projects.selectedProjectId;
});

const selectedProject = computed(() =>
  projects.items.find((item) => item.id === projectId.value) ?? null
);

const projectConfirmed = computed(() => Boolean(selectedProject.value?.confirmed));

const primaryLinks = computed(() => {
  const id = projectId.value;
  return [
    { name: RouteNames.Library, label: "我的小说", to: "/novels", icon: Library, always: true },
    {
      name: RouteNames.Workbench,
      label: "创作工作台",
      to: id ? `/novels/${id}/workbench` : "/novels",
      icon: PenLine,
      needsProject: true,
    },
    {
      name: RouteNames.Reader,
      label: "作品阅读",
      to: id ? `/novels/${id}/reader` : "/novels",
      icon: BookOpen,
      needsProject: true,
      needsConfirmed: true,
    },
    {
      name: RouteNames.Memory,
      label: "长期记忆",
      to: id ? `/novels/${id}/memory` : "/novels",
      icon: MemoryStick,
      needsProject: true,
      needsConfirmed: true,
    },
    {
      name: RouteNames.Analytics,
      label: "仪表盘",
      to: "/analytics",
      icon: LayoutDashboard,
      always: true,
    },
  ];
});

function isActive(name: string) {
  return route.name === name;
}

async function onNavClick(
  event: Event,
  link: { needsProject?: boolean; needsConfirmed?: boolean; to: string; name: string }
) {
  if (link.needsProject && !projectId.value) {
    event.preventDefault();
    projects.setNotice("请先创建或选择一本小说");
    await router.push({ name: RouteNames.Library });
    app.toggleSidebar(false);
    return;
  }
  if (link.needsConfirmed && !projectConfirmed.value) {
    event.preventDefault();
    projects.setNotice("请先检查并确认创作方案");
    await router.push({
      name: RouteNames.Workbench,
      params: { projectId: projectId.value },
    });
  }
  app.toggleSidebar(false);
}

function closeMobile() {
  app.toggleSidebar(false);
}

function expandSidebar() {
  if (typeof window !== "undefined" && window.matchMedia?.("(max-width: 767px)").matches) {
    return;
  }
  if (!app.sidebarCollapsed) return;
  app.toggleSidebarCollapsed(false);
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{ 'is-open': app.sidebarOpen, 'is-collapsed': app.sidebarCollapsed }"
  >
    <div class="sidebar__brand">
      <button
        v-if="app.sidebarCollapsed"
        type="button"
        class="brand-toggle"
        aria-label="展开导航"
        :aria-expanded="false"
        @click="expandSidebar"
      >
        <span class="brand-short">N</span>
      </button>
      <div class="brand-copy">
        <p class="brand-mark">Novel Agent</p>
        <p class="muted brand-sub">面向长篇连载的创作助手</p>
      </div>
      <BaseIconButton
        v-if="!app.sidebarCollapsed"
        class="sidebar-collapse"
        label="收起导航"
        :aria-expanded="true"
        @click="app.toggleSidebarCollapsed(true)"
      >
        <PanelLeftClose :size="19" aria-hidden="true" />
      </BaseIconButton>
    </div>
    <nav class="sidebar__nav" aria-label="主导航">
      <div class="sidebar__primary">
        <RouterLink
          v-for="link in primaryLinks"
          :key="link.name"
          :to="link.to"
          class="nav-link"
          :class="{ 'is-active': isActive(link.name) }"
          :aria-label="app.sidebarCollapsed ? link.label : undefined"
          :title="app.sidebarCollapsed ? link.label : undefined"
          @click="(e) => onNavClick(e, link)"
        >
          <component :is="link.icon" :size="18" aria-hidden="true" />
          <span>{{ link.label }}</span>
        </RouterLink>
      </div>
      <div class="sidebar__footer">
        <RouterLink
          :to="{ name: RouteNames.Settings }"
          class="nav-link"
          :class="{ 'is-active': isActive(RouteNames.Settings) }"
          :aria-label="app.sidebarCollapsed ? '系统设置' : undefined"
          :title="app.sidebarCollapsed ? '系统设置' : undefined"
          @click="closeMobile"
        >
          <Settings :size="18" aria-hidden="true" />
          <span>系统设置</span>
        </RouterLink>
      </div>
    </nav>
  </aside>
  <button
    v-if="app.sidebarOpen"
    type="button"
    class="sidebar-backdrop"
    aria-label="关闭导航"
    @click="closeMobile"
  />
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-border);
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  flex-shrink: 0;
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  transition: width 180ms ease, padding 180ms ease;
}

.sidebar.is-collapsed {
  width: var(--sidebar-collapsed-width);
  padding-left: var(--space-2);
  padding-right: var(--space-2);
}

.sidebar__brand {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.brand-copy {
  min-width: 0;
}

.brand-toggle {
  appearance: none;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.brand-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

.brand-short {
  display: inline-grid;
  place-items: center;
  width: var(--touch-min);
  height: var(--touch-min);
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 1.15rem;
  font-weight: 700;
}

.brand-mark {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.brand-sub {
  margin-top: var(--space-1);
  font-size: 0.8rem;
}

.sidebar__nav {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.sidebar__primary {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-height: 0;
  overflow-y: auto;
}

.sidebar__footer {
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.sidebar.is-collapsed .sidebar__brand {
  flex-direction: column;
  align-items: center;
}

.sidebar.is-collapsed .brand-copy,
.sidebar.is-collapsed .nav-link span {
  display: none;
}

.sidebar.is-collapsed .nav-link {
  justify-content: center;
  padding: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  transition: background 160ms ease;
}

.nav-link:hover {
  background: var(--color-surface-muted);
}

.nav-link.is-active {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  font-weight: 600;
}

.sidebar-backdrop {
  display: none;
}

@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 40;
    transform: translateX(-100%);
    transition: transform 200ms ease;
    width: var(--sidebar-width);
    height: 100dvh;
    padding: var(--space-6) var(--space-4);
    overflow: hidden;
  }

  .sidebar.is-collapsed {
    width: var(--sidebar-width);
    padding: var(--space-6) var(--space-4);
  }

  .sidebar.is-collapsed .sidebar__brand {
    flex-direction: row;
    align-items: flex-start;
  }

  .sidebar.is-collapsed .brand-copy {
    display: block;
  }

  .sidebar.is-collapsed .nav-link span {
    display: inline;
  }

  .sidebar.is-collapsed .brand-toggle {
    display: none;
  }

  .sidebar.is-collapsed .nav-link {
    justify-content: flex-start;
    padding: 0 var(--space-3);
  }

  .sidebar-collapse {
    display: none;
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0 0 0 var(--sidebar-width);
    z-index: 30;
    border: 0;
    background: rgba(0, 0, 0, 0.35);
  }
}
</style>
