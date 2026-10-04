<script setup lang="ts">
defineProps<{
  timeoutSeconds: number;
  maxRetries: number;
  open: boolean;
  disabled?: boolean;
}>();
const emit = defineEmits<{
  "update:timeoutSeconds": [value: number];
  "update:maxRetries": [value: number];
  "update:open": [value: boolean];
}>();
</script>

<template>
  <section class="block">
    <button type="button" class="toggle" @click="emit('update:open', !open)">
      {{ open ? "收起高级设置" : "高级设置" }}
    </button>
    <div v-if="open" class="grid">
      <label>
        超时（秒）
        <input
          :value="timeoutSeconds"
          :disabled="disabled"
          type="number"
          min="10"
          max="300"
          @input="emit('update:timeoutSeconds', Number(($event.target as HTMLInputElement).value))"
        />
      </label>
      <label>
        最大重试
        <input
          :value="maxRetries"
          :disabled="disabled"
          type="number"
          min="0"
          max="5"
          @input="emit('update:maxRetries', Number(($event.target as HTMLInputElement).value))"
        />
      </label>
    </div>
  </section>
</template>

<style scoped>
.toggle {
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  min-height: var(--touch-min);
  text-align: left;
}
.grid { display: grid; gap: var(--space-3); }
label { display: grid; gap: var(--space-1); font-weight: 600; font-size: 0.9rem; }
input {
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
</style>
