<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    tone?: "neutral" | "success" | "warning" | "danger" | "muted";
  }>(),
  { tone: "neutral" }
);
</script>

<template>
  <span class="status-badge" :class="`is-${tone}`">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 var(--space-2);
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-muted);
  color: var(--color-text);
  font-size: 0.75rem;
  line-height: 1;
  white-space: nowrap;
}

.is-success {
  color: var(--color-success);
  border-color: color-mix(in srgb, var(--color-success) 35%, var(--color-border));
  background: color-mix(in srgb, var(--color-success) 10%, white);
}

.is-warning {
  color: var(--color-warning);
  border-color: color-mix(in srgb, var(--color-warning) 35%, var(--color-border));
  background: color-mix(in srgb, var(--color-warning) 12%, white);
}

.is-danger {
  color: var(--color-danger);
  border-color: color-mix(in srgb, var(--color-danger) 35%, var(--color-border));
  background: color-mix(in srgb, var(--color-danger) 10%, white);
}

.is-muted {
  color: var(--color-text-muted);
}
</style>
