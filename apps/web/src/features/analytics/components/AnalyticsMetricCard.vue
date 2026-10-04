<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  hint?: string;
}>();
</script>

<template>
  <article class="analytics-metric-card">
    <span>{{ label }}</span>
    <strong>{{ value }}</strong>
    <small v-if="hint">{{ hint }}</small>
  </article>
</template>
