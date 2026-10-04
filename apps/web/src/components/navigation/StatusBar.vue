<script setup lang="ts">
import { computed } from "vue";
import { useAppStore } from "@/stores/app.store";

const app = useAppStore();

const toneClass = computed(() => {
  switch (app.health) {
    case "ok":
      return "is-ok";
    case "degraded":
      return "is-warn";
    case "down":
      return "is-down";
    default:
      return "is-unknown";
  }
});
</script>

<template>
  <div class="status-bar" role="status">
    <span class="dot" :class="toneClass" aria-hidden="true" />
    <span>{{ app.healthMessage }}</span>
  </div>
</template>

<style scoped>
.status-bar {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 8px;
  padding: 6px 10px;
  color: var(--color-text);
  font-size: 12px;
  line-height: 1.2;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
}

.is-ok {
  background: var(--color-success);
}

.is-warn {
  background: var(--color-warning);
}

.is-down {
  background: var(--color-danger);
}
</style>
