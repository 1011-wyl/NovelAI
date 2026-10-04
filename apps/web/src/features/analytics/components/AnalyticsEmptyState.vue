<script setup lang="ts">
defineProps<{
  message?: string;
}>();
</script>

<template>
  <div class="analytics-empty-state" role="status" data-testid="analytics-empty">
    {{ message || "暂无统计数据" }}
  </div>
</template>
