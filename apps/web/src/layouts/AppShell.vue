<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { Menu } from "lucide-vue-next";
import AppSidebar from "@/components/navigation/AppSidebar.vue";
import StatusBar from "@/components/navigation/StatusBar.vue";
import BaseIconButton from "@/components/base/BaseIconButton.vue";
import { useAppStore } from "@/stores/app.store";

const app = useAppStore();
const route = useRoute();
const fullBleed = computed(() => Boolean(route.meta.fullBleed));
</script>

<template>
  <div
    class="app-shell"
    :class="{
      'is-full-bleed': fullBleed,
      'is-sidebar-collapsed': app.sidebarCollapsed,
    }"
  >
    <AppSidebar />
    <div class="app-shell__main">
      <header class="app-shell__top">
        <BaseIconButton class="menu-toggle" label="打开导航" @click="app.toggleSidebar(true)">
          <Menu :size="20" />
        </BaseIconButton>
        <div class="app-shell__top-slot">
          <slot name="top" />
        </div>
        <StatusBar />
      </header>
      <main class="app-shell__content" :class="{ 'is-full-bleed': fullBleed }">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  width: 100%;
  padding-left: var(--sidebar-width);
  background: var(--color-bg);
  transition: padding-left 180ms ease;
}

.app-shell.is-sidebar-collapsed {
  padding-left: var(--sidebar-collapsed-width);
}

.app-shell__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.app-shell__top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 56px;
  padding: var(--space-2) var(--space-6);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.app-shell__top-slot {
  flex: 1;
  min-width: 0;
}

.app-shell__content {
  flex: 1;
  padding: var(--space-6);
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

.app-shell.is-full-bleed {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
}

.app-shell.is-full-bleed .app-shell__main {
  min-height: 0;
}

.app-shell__content.is-full-bleed {
  max-width: none;
  margin: 0;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.menu-toggle {
  display: none;
}

@media (max-width: 767px) {
  .app-shell,
  .app-shell.is-sidebar-collapsed {
    padding-left: 0;
  }

  .menu-toggle {
    display: inline-flex;
  }

  .app-shell__content,
  .app-shell__top {
    padding-left: var(--space-4);
    padding-right: var(--space-4);
  }
}
</style>
