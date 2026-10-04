<script setup lang="ts">
import BaseField from "@/components/base/BaseField.vue";
import { useNovelCreateStore } from "@/features/novel-create/store/novel-create.store";
import { TAG_LIMITS, type TagGroup } from "@/features/novel-create/types";

const store = useNovelCreateStore();

const groups: Array<{ key: TagGroup; label: string }> = [
  { key: "experiences", label: "阅读体验" },
  { key: "elements", label: "核心元素" },
  { key: "protagonist_tags", label: "主角设定" },
];

function isChecked(group: TagGroup, value: string) {
  return store.form[group].includes(value);
}

function onToggle(group: TagGroup, value: string, checked: boolean) {
  const currently = isChecked(group, value);
  if (checked === currently) return;
  store.toggleTag(group, value);
}
</script>

<template>
  <section class="step">
    <h2>创作偏好</h2>
    <p class="muted">用标签描绘阅读体验与故事元素。达到上限时会就地提示。</p>
    <p v-if="store.channelWarning" class="warning" role="status">{{ store.channelWarning }}</p>

    <fieldset v-for="group in groups" :key="group.key" class="tag-group">
      <legend>
        {{ group.label }}
        <span class="muted">（最多 {{ TAG_LIMITS[group.key] }} 个）</span>
      </legend>
      <div class="chips">
        <label
          v-for="value in store.channelTags?.[group.key] || []"
          :key="value"
          class="chip"
        >
          <input
            type="checkbox"
            :name="group.key"
            :value="value"
            :checked="isChecked(group.key, value)"
            @change="onToggle(group.key, value, ($event.target as HTMLInputElement).checked)"
          />
          <span>{{ value }}</span>
        </label>
      </div>
      <p v-if="store.fieldErrors[group.key]" class="error" role="alert">
        {{ store.fieldErrors[group.key] }}
      </p>
    </fieldset>

    <BaseField label="感情线（可选）" for-id="romance" :error="store.fieldErrors.romance">
      <select id="romance" v-model="store.form.romance">
        <option value="">自动推导</option>
        <option
          v-for="item in (store.channelTags?.romance || []).filter((x) => x !== '自动推导')"
          :key="item"
          :value="item"
        >
          {{ item }}
        </option>
      </select>
    </BaseField>
  </section>
</template>

<style scoped>
.step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.warning {
  color: var(--color-warning);
  background: color-mix(in srgb, var(--color-warning) 10%, white);
  border: 1px solid color-mix(in srgb, var(--color-warning) 30%, var(--color-border));
  border-radius: var(--radius-sm);
  padding: var(--space-3);
}

.tag-group {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
}

.chip:has(input:checked) {
  border-color: var(--color-primary);
  background: var(--color-surface-muted);
}

.error {
  margin: var(--space-2) 0 0;
  color: var(--color-danger);
  font-size: 0.85rem;
}
</style>
