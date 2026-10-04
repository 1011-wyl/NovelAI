<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    variant?: "primary" | "secondary" | "danger" | "ghost";
    disabled?: boolean;
    loading?: boolean;
    wide?: boolean;
  }>(),
  {
    type: "button",
    variant: "secondary",
    disabled: false,
    loading: false,
    wide: false,
  }
);
</script>

<template>
  <button
    class="base-button"
    :class="[`is-${variant}`, { 'is-wide': wide, 'is-loading': loading }]"
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="base-button__spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: var(--touch-min);
  padding: 0 var(--space-4);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease;
}

.base-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.is-primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-on-primary);
}

.is-danger {
  background: var(--color-danger);
  border-color: var(--color-danger);
  color: #fff;
}

.is-ghost {
  background: transparent;
  border-color: transparent;
}

.is-wide {
  width: 100%;
}

.base-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .base-button__spinner {
    animation: none;
  }
}
</style>
