<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    disabled?: boolean;
  }>(),
  { disabled: false }
);
</script>

<template>
  <button
    type="button"
    class="icon-button"
    :aria-label="label"
    :title="label"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--touch-min);
  height: var(--touch-min);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  transition: background 160ms ease, border-color 160ms ease;
}

.icon-button:hover:not(:disabled) {
  background: var(--color-surface-muted);
  border-color: var(--color-border);
}

.icon-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
