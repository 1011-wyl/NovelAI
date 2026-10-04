<script setup lang="ts">
defineProps<{
  message: string;
}>();

const emit = defineEmits<{
  retry: [];
}>();
</script>

<template>
  <div class="analytics-error-state" role="alert" tabindex="-1" data-testid="analytics-error">
    <p>{{ message }}</p>
    <button type="button" class="button ghost" data-testid="analytics-retry" @click="emit('retry')">
      重试
    </button>
  </div>
</template>
