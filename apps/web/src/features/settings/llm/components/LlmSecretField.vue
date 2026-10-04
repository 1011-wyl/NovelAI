<script setup lang="ts">
const props = defineProps<{
  modelValue: string;
  mask: string | null;
  show: boolean;
  disabled?: boolean;
}>();
const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:show": [value: boolean];
}>();
</script>

<template>
  <section class="block">
    <h3>访问凭证</h3>
    <p v-if="mask" class="muted">已保存密钥：{{ mask }}。输入框留空表示保留现有密钥。</p>
    <label class="field">
      <span>API Key</span>
      <div class="secret-row">
        <input
          :value="props.modelValue"
          :type="show ? 'text' : 'password'"
          :disabled="disabled"
          autocomplete="off"
          spellcheck="false"
          @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        />
        <button type="button" class="toggle" :disabled="disabled" @click="emit('update:show', !show)">
          {{ show ? "隐藏" : "显示" }}
        </button>
      </div>
    </label>
    <p class="hint">密钥只发送给本机后端，不会从接口回显。</p>
  </section>
</template>

<style scoped>
.block { display: grid; gap: var(--space-3); }
.field { display: grid; gap: var(--space-1); font-size: 0.9rem; font-weight: 600; }
.secret-row { display: flex; gap: var(--space-2); }
.secret-row input {
  flex: 1;
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.toggle {
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}
.hint, .muted { margin: 0; color: var(--color-text-muted); font-size: 0.85rem; font-weight: 400; }
</style>
