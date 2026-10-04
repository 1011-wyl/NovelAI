<script setup lang="ts">
import { computed } from "vue";
import type { CreateFormState } from "@/features/novel-create/schema";

const props = defineProps<{
  form: CreateFormState;
}>();

const ideaPreview = computed(() => {
  const text = props.form.idea.trim();
  if (!text) return "尚未填写";
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
});

const tags = computed(() => [
  ...props.form.experiences,
  ...props.form.elements,
  ...props.form.protagonist_tags,
]);
</script>

<template>
  <aside class="summary" aria-label="需求摘要">
    <h2>需求摘要</h2>
    <p class="muted">实时汇总，不可在此编辑。</p>
    <dl>
      <div>
        <dt>频道</dt>
        <dd>{{ form.audience_channel }}</dd>
      </div>
      <div>
        <dt>题材</dt>
        <dd>{{ form.genre || "待选择" }}</dd>
      </div>
      <div>
        <dt>书名</dt>
        <dd>{{ form.preferred_title.trim() || "待生成标题" }}</dd>
      </div>
      <div>
        <dt>核心想法</dt>
        <dd>{{ ideaPreview }}</dd>
      </div>
      <div>
        <dt>已选标签</dt>
        <dd>{{ tags.length ? tags.join("、") : "暂无" }}</dd>
      </div>
      <div>
        <dt>感情线</dt>
        <dd>{{ form.romance || "自动推导" }}</dd>
      </div>
      <div>
        <dt>连载设置</dt>
        <dd>
          每章 {{ form.chapter_target_chars }} 字 · 每日 {{ form.daily_chapters }} 章 · 储备
          {{ form.reserve_target }}
        </dd>
      </div>
      <div>
        <dt>方案确认</dt>
        <dd>生成后需确认</dd>
      </div>
    </dl>
  </aside>
</template>

<style scoped>
.summary {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-surface-muted);
  height: fit-content;
}

h2 {
  font-size: 1.05rem;
  margin-bottom: var(--space-1);
}

dl {
  margin: var(--space-4) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

div {
  display: grid;
  gap: 2px;
}

dt {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

dd {
  margin: 0;
  font-size: 0.95rem;
  word-break: break-word;
}
</style>
