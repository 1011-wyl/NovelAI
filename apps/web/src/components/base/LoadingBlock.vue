<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string;
    lines?: number;
  }>(),
  {
    label: "加载中…",
    lines: 3,
  }
);
</script>

<template>
  <div class="loading-block" role="status" :aria-label="label">
    <p class="sr-only">{{ label }}</p>
    <div
      v-for="n in lines"
      :key="n"
      class="loading-line"
      :style="{ width: `${70 + ((n * 17) % 25)}%` }"
    />
  </div>
</template>

<style scoped>
.loading-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) 0;
}

.loading-line {
  height: 14px;
  border-radius: var(--radius-sm);
  background: linear-gradient(
    90deg,
    var(--color-surface-muted) 0%,
    #ececec 50%,
    var(--color-surface-muted) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.2s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loading-line {
    animation: none;
  }
}
</style>
