<script setup lang="ts">
import { PROVIDER_OPTIONS } from "../model/providers";
import type { LlmProvider } from "../model/contracts";

const props = defineProps<{
  provider: LlmProvider;
  baseUrl: string;
  model: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:provider": [value: LlmProvider];
  "update:baseUrl": [value: string];
  "update:model": [value: string];
  "provider-change": [value: LlmProvider];
}>();
</script>

<template>
  <section class="block">
    <h3>模型服务</h3>
    <label class="field">
      <span>供应商</span>
      <select
        :value="props.provider"
        :disabled="disabled"
        @change="emit('provider-change', ($event.target as HTMLSelectElement).value as LlmProvider)"
      >
        <option v-for="option in PROVIDER_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>API 地址</span>
      <input
        :value="props.baseUrl"
        :disabled="disabled"
        autocomplete="off"
        @input="emit('update:baseUrl', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label class="field">
      <span>模型 ID</span>
      <input
        :value="props.model"
        :disabled="disabled"
        autocomplete="off"
        @input="emit('update:model', ($event.target as HTMLInputElement).value)"
      />
    </label>
  </section>
</template>

<style scoped>
.block {
  display: grid;
  gap: var(--space-3);
}
.field {
  display: grid;
  gap: var(--space-1);
  font-size: 0.9rem;
  font-weight: 600;
}
.field input,
.field select {
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
</style>
