<script setup lang="ts">
import BaseButton from "@/components/base/BaseButton.vue";
import type { ChapterFailure } from "../types/workbench.types";

const props = defineProps<{ failure: ChapterFailure }>();
const emit = defineEmits<{
  replan: [];
  reuse: [];
  inspect: [];
  repair: [];
  accept: [];
}>();
</script>

<template>
  <div class="failed-actions">
    <BaseButton variant="ghost" @click="emit('inspect')">查看审校意见</BaseButton>
    <BaseButton variant="primary" @click="emit('replan')">重新规划并重写</BaseButton>
    <BaseButton
      v-if="props.failure.recommended_rework_mode === 'reuse_plan'"
      variant="ghost"
      @click="emit('reuse')"
    >
      沿用细纲重写
    </BaseButton>
    <BaseButton
      v-if="props.failure.can_accept_with_warnings"
      variant="ghost"
      @click="emit('accept')"
    >
      接受当前版本并继续
    </BaseButton>
    <BaseButton
      v-if="props.failure.opening_repair_eligible"
      variant="ghost"
      @click="emit('repair')"
    >
      检查并修复开篇数据
    </BaseButton>
  </div>
</template>
