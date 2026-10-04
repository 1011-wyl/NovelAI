<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import AppShell from "@/layouts/AppShell.vue";
import AnalyticsTabs from "../components/AnalyticsTabs.vue";
import LlmAnalyticsPanel from "../components/LlmAnalyticsPanel.vue";
import RecordsAnalyticsPanel from "../components/RecordsAnalyticsPanel.vue";
import WritingAnalyticsPanel from "../components/WritingAnalyticsPanel.vue";
import { useAnalyticsStore } from "../stores/analytics.store";
import type { AnalyticsTab } from "../types/analytics.types";
import "../styles/analytics.css";

const store = useAnalyticsStore();
const { activeTab } = storeToRefs(store);

function onTabChange(tab: AnalyticsTab) {
  store.setTab(tab);
}

onMounted(() => {
  void store.loadActiveTab();
});

onUnmounted(() => {
  store.reset();
});
</script>

<template>
  <AppShell>
    <div id="analyticsView" class="analytics-view active" aria-labelledby="analyticsTitle">
      <div class="analytics-shell">
        <header class="analytics-header">
          <h1 id="analyticsTitle">仪表盘</h1>
        </header>
        <AnalyticsTabs :model-value="activeTab" @update:model-value="onTabChange" />
        <WritingAnalyticsPanel v-if="activeTab === 'writing'" />
        <LlmAnalyticsPanel v-else-if="activeTab === 'llm'" />
        <RecordsAnalyticsPanel v-else />
      </div>
    </div>
  </AppShell>
</template>
