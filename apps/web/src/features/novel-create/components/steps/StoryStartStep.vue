<script setup lang="ts">
import { computed } from "vue";
import BaseField from "@/components/base/BaseField.vue";
import { useNovelCreateStore } from "@/features/novel-create/store/novel-create.store";

const store = useNovelCreateStore();
const ideaCount = computed(() => store.form.idea.length);
</script>

<template>
  <section class="step">
    <h2>故事起点</h2>
    <p class="muted">先确定读者频道、题材和你想写的核心想法。</p>

    <fieldset class="channel">
      <legend>读者频道</legend>
      <label>
        <input
          type="radio"
          name="audience_channel"
          value="男频"
          :checked="store.form.audience_channel === '男频'"
          @change="store.setChannel('男频')"
        />
        <span>
          <strong>男频</strong>
          <small>目标推进、升级反馈、世界探索</small>
        </span>
      </label>
      <label>
        <input
          type="radio"
          name="audience_channel"
          value="女频"
          :checked="store.form.audience_channel === '女频'"
          @change="store.setChannel('女频')"
        />
        <span>
          <strong>女频</strong>
          <small>人物成长、情感因果、关系变化</small>
        </span>
      </label>
    </fieldset>

    <BaseField
      label="题材"
      for-id="genre"
      required
      :error="store.fieldErrors.genre"
    >
      <select
        id="genre"
        v-model="store.form.genre"
        @blur="store.blurValidate('genre')"
      >
        <option disabled value="">请选择题材</option>
        <option
          v-for="genre in store.channelTags?.genres || []"
          :key="genre"
          :value="genre"
        >
          {{ genre }}
        </option>
      </select>
    </BaseField>

    <BaseField
      label="书名（可选）"
      for-id="preferred_title"
      hint="留空则由系统生成多个候选书名"
      :error="store.fieldErrors.preferred_title"
    >
      <input
        id="preferred_title"
        v-model="store.form.preferred_title"
        maxlength="80"
        @blur="store.blurValidate('preferred_title')"
      />
    </BaseField>

    <BaseField
      label="核心想法"
      for-id="idea"
      required
      :hint="`${ideaCount} / 2000`"
      :error="store.fieldErrors.idea"
    >
      <textarea
        id="idea"
        v-model="store.form.idea"
        rows="6"
        maxlength="2000"
        placeholder="例如：主角是一名仓储管理员，没有无限空间，只能依靠职业经验和有限资源建立社区。"
        @blur="store.blurValidate('idea')"
      />
    </BaseField>
  </section>
</template>

<style scoped>
.step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.channel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: grid;
  gap: var(--space-2);
}

.channel label {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  min-height: var(--touch-min);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
}

.channel label:hover {
  background: var(--color-surface-muted);
}

.channel strong {
  display: block;
}

.channel small {
  color: var(--color-text-muted);
}
</style>
