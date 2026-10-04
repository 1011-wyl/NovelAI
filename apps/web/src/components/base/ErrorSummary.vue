<script setup lang="ts">
import { onMounted, ref } from "vue";

defineProps<{
  title?: string;
  messages: string[];
}>();

const rootRef = ref<HTMLElement | null>(null);

onMounted(() => {
  rootRef.value?.focus();
});
</script>

<template>
  <div
    ref="rootRef"
    class="error-summary"
    role="alert"
    tabindex="-1"
  >
    <p class="error-summary__title">{{ title || "请修正以下问题后继续" }}</p>
    <ul>
      <li v-for="(message, index) in messages" :key="`${index}-${message}`">
        {{ message }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.error-summary {
  border: 1px solid color-mix(in srgb, var(--color-danger) 40%, var(--color-border));
  background: color-mix(in srgb, var(--color-danger) 8%, white);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.error-summary__title {
  font-weight: 600;
  margin-bottom: var(--space-2);
}

ul {
  margin: 0;
  padding-left: 1.2rem;
}
</style>
