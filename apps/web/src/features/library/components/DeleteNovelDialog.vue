<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseField from "@/components/base/BaseField.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import type { ProjectSummary } from "@/api/contracts";
import { useProjectsStore } from "@/stores/projects.store";

const props = defineProps<{
  open: boolean;
  novel: ProjectSummary | null;
  deleting?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  close: [];
  confirm: [confirmationTitle?: string];
}>();

const projects = useProjectsStore();
const confirmation = ref("");
const fieldError = ref("");

const needsTitle = computed(() =>
  props.novel ? projects.requiresTitleConfirmation(props.novel) : false
);

watch(
  () => props.open,
  (open) => {
    if (open) {
      confirmation.value = "";
      fieldError.value = "";
    }
  }
);

function onConfirm() {
  if (!props.novel) return;
  if (needsTitle.value) {
    if (confirmation.value !== props.novel.title) {
      fieldError.value = "请完整输入当前书名以确认删除";
      return;
    }
    emit("confirm", confirmation.value);
    return;
  }
  emit("confirm");
}
</script>

<template>
  <BaseDialog
    :open="open"
    title="删除小说"
    :description="
      needsTitle
        ? '正式作品删除不可撤销，请完整输入当前书名确认。'
        : '将删除这本未确认的草稿小说，此操作不可撤销。'
    "
    @close="emit('close')"
  >
    <p v-if="novel" class="target">
      目标作品：<strong>{{ novel.title }}</strong>
    </p>
    <BaseField
      v-if="needsTitle"
      label="输入书名确认"
      for-id="delete-confirm-title"
      required
      :error="fieldError || error"
    >
      <input
        id="delete-confirm-title"
        v-model="confirmation"
        autofocus
        autocomplete="off"
        :disabled="deleting"
        :placeholder="novel?.title"
      />
    </BaseField>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>
    <template #footer>
      <BaseButton :disabled="deleting" @click="emit('close')">取消</BaseButton>
      <BaseButton variant="danger" :loading="deleting" @click="onConfirm">
        确认删除
      </BaseButton>
    </template>
  </BaseDialog>
</template>

<style scoped>
.target {
  margin-bottom: var(--space-3);
}

.error {
  color: var(--color-danger);
}
</style>
