<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";
import AppShell from "@/layouts/AppShell.vue";
import BaseButton from "@/components/base/BaseButton.vue";

const route = useRoute();
const projectId = String(route.params.projectId || "");
</script>

<template>
  <AppShell>
    <div class="state-page">
      <h1>项目不存在</h1>
      <p class="muted">找不到小说 {{ projectId }}，它可能已被删除。</p>
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
