<script setup lang="ts">
import { ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseField from "@/components/base/BaseField.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import type { ProjectSummary } from "@/api/contracts";

const props = defineProps<{
  open: boolean;
  novel: ProjectSummary | null;
  saving?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  close: [];
  save: [title: string];
}>();

const title = ref("");
const fieldError = ref("");

watch(
  () => props.open,
  (open) => {
    if (open && props.novel) {
      title.value = props.novel.title;
      fieldError.value = "";
    }
  }
);

function onSubmit() {
  const next = title.value.trim();
  if (!next) {
    fieldError.value = "书名不能为空";
    return;
  }
  if (next.length > 80) {
    fieldError.value = "书名最多 80 字";
    return;
  }
  fieldError.value = "";
  emit("save", next);
}
</script>

<template>
  <BaseDialog
    :open="open"
    title="修改书名"
    description="修改后将同步到书架与创作方案标题。"
    @close="emit('close')"
  >
    <form id="rename-form" @submit.prevent="onSubmit">
      <BaseField
        label="书名"
        for-id="rename-title"
        required
        :error="fieldError || error"
      >
        <input
          id="rename-title"
          v-model="title"
          autofocus
          maxlength="80"
          autocomplete="off"
          :disabled="saving"
        />
      </BaseField>
    </form>
    <template #footer>
      <BaseButton :disabled="saving" @click="emit('close')">取消</BaseButton>
      <BaseButton type="submit" variant="primary" :loading="saving" @click="onSubmit">
        保存
      </BaseButton>
    </template>
  </BaseDialog>
</template>
