<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useProjectsStore } from "@/stores/projects.store";
import { RouteNames } from "@/router/route-names";

const projects = useProjectsStore();
const router = useRouter();

const options = computed(() => projects.items);

async function onChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  if (!value) return;
  projects.selectProject(value);
  await router.push({ name: RouteNames.Workbench, params: { projectId: value } });
}
</script>

<template>
  <label class="project-picker">
    <span class="sr-only">当前小说</span>
    <select
      :value="projects.selectedProjectId || ''"
      aria-label="选择当前小说"
      @change="onChange"
    >
      <option disabled value="">选择小说</option>
      <option v-for="item in options" :key="item.id" :value="item.id">
        {{ item.title }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.project-picker select {
  min-height: var(--touch-min);
  max-width: 220px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}
</style>
