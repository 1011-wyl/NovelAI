<script setup lang="ts">
import { RouterLink } from "vue-router";
import AppShell from "@/layouts/AppShell.vue";
import BaseButton from "@/components/base/BaseButton.vue";
</script>

<template>
  <AppShell>
    <div class="state-page">
      <h1>页面不存在</h1>
      <p class="muted">你访问的路径无效，或已被移动。</p>
      <RouterLink to="/novels">
        <BaseButton variant="primary">返回书架</BaseButton>
      </RouterLink>
    </div>
  </AppShell>
</template>

<style scoped>
.state-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-8) 0;
}
</style>
