<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    forId?: string;
    hint?: string;
    error?: string;
    required?: boolean;
  }>(),
  {
    forId: undefined,
    hint: "",
    error: "",
    required: false,
  }
);
</script>

<template>
  <div class="base-field" :class="{ 'has-error': !!error }">
    <label class="base-field__label" :for="forId">
      {{ label }}
      <span v-if="required" class="required" aria-hidden="true">*</span>
    </label>
    <div class="base-field__control">
      <slot />
    </div>
    <p v-if="error" class="base-field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" class="base-field__hint muted">{{ hint }}</p>
  </div>
</template>

<style scoped>
.base-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.base-field__label {
  font-size: 0.9rem;
  font-weight: 600;
}

.required {
  color: var(--color-danger);
  margin-left: 2px;
}

.base-field__control :deep(input),
.base-field__control :deep(select),
.base-field__control :deep(textarea) {
  width: 100%;
  min-height: var(--touch-min);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.base-field__control :deep(textarea) {
  min-height: 120px;
  resize: none;
}

.has-error :deep(input),
.has-error :deep(select),
.has-error :deep(textarea) {
  border-color: var(--color-danger);
}

.base-field__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 0.85rem;
}

.base-field__hint {
  margin: 0;
  font-size: 0.85rem;
}
</style>
