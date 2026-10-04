<script setup lang="ts">
import { ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import type { OpeningRepairPreview } from "../types/workbench.types";

const props = defineProps<{
  open: boolean;
  preview: OpeningRepairPreview | null;
  acting?: boolean;
}>();
const emit = defineEmits<{
  close: [];
  confirm: [];
}>();

const confirmed = ref(false);

watch(
  () => [props.open, props.preview?.project_updated_at, props.preview] as const,
  ([open]) => {
    if (open) confirmed.value = false;
  }
);
</script>

<template>
  <BaseDialog :open="open" title="检查并修复开篇数据" @close="emit('close')">
    <div v-if="preview" class="repair-preview">
      <p v-if="!preview.eligible">当前项目不能自动修复：{{ preview.reasons.join("；") }}</p>
      <template v-else>
        <p>系统判断开篇数据可能被未来设定污染。确认后会先建立可回退快照，不会立即生成新章节。</p>
        <h4>检测到的问题</h4>
        <ul>
          <li v-for="(item, index) in preview.detected_problems" :key="index">{{ item }}</li>
        </ul>
        <h4>正确开篇锚点</h4>
        <p>{{ preview.opening_anchor.title || "（旧数据无标题）" }}：{{ preview.opening_anchor.core_event }}</p>
        <h4>人物关系将如何调整</h4>
        <ul>
          <li v-for="change in preview.character_changes" :key="change.name">
            {{ change.name }}：当前 {{ JSON.stringify(change.from_relationships || {}) }}
            → 初态 {{ JSON.stringify(change.to_relationships || {}) }}
            <span v-if="change.moved_to_future">；原关系写入未来弧线</span>
          </li>
        </ul>
        <h4>章节状态变化</h4>
        <ul>
          <li v-for="(item, index) in preview.chapter_changes" :key="index">
            第 {{ item.chapter_number }} 章：{{ item.from_status }} → {{ item.to_status }}
            （{{ item.from_title }} → {{ item.to_title }}）
          </li>
        </ul>
        <h4>会保存的内容</h4>
        <ul>
          <li v-for="(item, index) in preview.preserved_artifacts" :key="index">{{ item }}</li>
        </ul>
        <p>若之后还没有正式章节，可以用“回退开篇修复”恢复本次快照。</p>
        <label>
          <input v-model="confirmed" type="checkbox" aria-label="我已阅读影响范围，确认修复开篇数据" />
          我已阅读影响范围，确认修复开篇数据
        </label>
      </template>
    </div>
    <p v-else-if="acting">正在读取影响范围…</p>
    <template #footer>
      <BaseButton variant="ghost" @click="emit('close')">取消</BaseButton>
      <BaseButton
        variant="primary"
        :disabled="!preview?.eligible || !confirmed || acting"
        :loading="acting"
        @click="emit('confirm')"
      >
        {{ acting ? "正在修复" : "确认修复" }}
      </BaseButton>
    </template>
  </BaseDialog>
</template>
