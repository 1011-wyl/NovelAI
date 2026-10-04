<script setup lang="ts">
import BaseField from "@/components/base/BaseField.vue";
import { useNovelCreateStore } from "@/features/novel-create/store/novel-create.store";

const store = useNovelCreateStore();
</script>

<template>
  <section class="step">
    <h2>连载计划与边界</h2>
    <p class="muted">说明必须包含与明确不要的内容，并确认更新节奏。</p>

    <BaseField
      label="必须包含"
      for-id="must_have"
      hint="可用逗号分隔多项"
      :error="store.fieldErrors.must_have"
    >
      <input id="must_have" v-model="store.form.must_have" />
    </BaseField>

    <BaseField
      label="明确不要"
      for-id="exclude"
      hint="例如：过度血腥, 悲剧结局"
      :error="store.fieldErrors.exclude"
    >
      <input id="exclude" v-model="store.form.exclude" />
    </BaseField>

    <p class="confirmation-note">
      生成后会先进入方案审阅；确认创作方案后，才会开放章节生产、长期记忆与作品阅读。
    </p>

    <button
      type="button"
      class="advanced-toggle"
      :aria-expanded="store.form.showAdvanced"
      @click="store.form.showAdvanced = !store.form.showAdvanced"
    >
      {{ store.form.showAdvanced ? "收起更多设置" : "更多设置" }}
    </button>

    <div v-if="store.form.showAdvanced" class="advanced">
      <BaseField
        label="希望包含"
        for-id="nice_to_have"
        :error="store.fieldErrors.nice_to_have"
      >
        <input id="nice_to_have" v-model="store.form.nice_to_have" />
      </BaseField>
      <div class="field-row">
        <BaseField
          label="单章目标字数"
          for-id="chapter_target_chars"
          :error="store.fieldErrors.chapter_target_chars"
        >
          <input
            id="chapter_target_chars"
            v-model.number="store.form.chapter_target_chars"
            type="number"
            min="800"
            max="8000"
            @blur="store.blurValidate('chapter_target_chars')"
          />
        </BaseField>
        <BaseField
          label="每日章节"
          for-id="daily_chapters"
          :error="store.fieldErrors.daily_chapters"
        >
          <input
            id="daily_chapters"
            v-model.number="store.form.daily_chapters"
            type="number"
            min="1"
            max="20"
            @blur="store.blurValidate('daily_chapters')"
          />
        </BaseField>
      </div>
      <BaseField
        label="储备安全线"
        for-id="reserve_target"
        :error="store.fieldErrors.reserve_target"
      >
        <input
          id="reserve_target"
          v-model.number="store.form.reserve_target"
          type="number"
          min="1"
          max="50"
          @blur="store.blurValidate('reserve_target')"
        />
      </BaseField>
    </div>
  </section>
</template>

<style scoped>
.step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.confirmation-note {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.advanced-toggle {
  align-self: flex-start;
  border: 0;
  background: transparent;
  text-decoration: underline;
  text-underline-offset: 3px;
  min-height: var(--touch-min);
  padding: 0;
}

.advanced {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-top: var(--space-2);
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

@media (max-width: 767px) {
  .field-row {
    grid-template-columns: 1fr;
  }
}
</style>
