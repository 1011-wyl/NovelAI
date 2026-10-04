<script setup lang="ts">
import AppShell from "./AppShell.vue";
import ProjectPicker from "@/components/navigation/ProjectPicker.vue";
</script>

<template>
  <AppShell>
    <template #top>
      <div class="project-shell-top">
        <ProjectPicker />
        <slot name="top" />
      </div>
    </template>
    <slot />
  </AppShell>
</template>

<style scoped>
.project-shell-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
</style>
