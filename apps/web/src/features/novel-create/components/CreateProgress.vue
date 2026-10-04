<script setup lang="ts">
defineProps<{
  step: number;
  total?: number;
}>();
</script>

<template>
  <div class="create-progress" aria-live="polite">
    <p class="eyebrow">创建小说</p>
    <p class="step-label">第 {{ step }} 步，共 {{ total || 3 }} 步</p>
    <ol class="dots" aria-hidden="true">
      <li v-for="n in total || 3" :key="n" :class="{ active: n === step, done: n < step }" />
    </ol>
  </div>
</template>

<style scoped>
.create-progress {
  margin-bottom: var(--space-4);
}

.eyebrow {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.step-label {
  font-weight: 600;
  margin: var(--space-1) 0 var(--space-3);
}

.dots {
  display: flex;
  gap: var(--space-2);
  list-style: none;
  margin: 0;
  padding: 0;
}

.dots li {
  width: 28px;
  height: 4px;
  border-radius: 999px;
  background: var(--color-border);
}

.dots li.active,
.dots li.done {
  background: var(--color-primary);
}
</style>
