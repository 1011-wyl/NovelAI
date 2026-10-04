<script setup lang="ts">
import { computed } from "vue";
import type { CreativeBrief, NovelCreatePayload } from "@/api/contracts";

const props = defineProps<{
  brief: CreativeBrief | null;
  request: NovelCreatePayload | null;
}>();

const experiences = computed(() => props.request?.experiences?.join(" / ") || "自动确定体验");
</script>

<template>
  <div v-if="brief && request" class="brief-grid">
    <div class="brief-block">
      <h4>频道与题材</h4>
      <p>
        <b>{{ request.audience_channel }}</b><br />
        {{ request.genre }} · {{ experiences }}
      </p>
    </div>
    <div class="brief-block">
      <h4>核心卖点</h4>
      <ul>
        <li v-for="(item, index) in brief.selling_points || []" :key="index">{{ item }}</li>
      </ul>
    </div>
    <div class="brief-block">
      <h4>主角与主要冲突</h4>
      <p>
        <b>{{ brief.protagonist }}</b><br />
        {{ brief.main_conflict }}
      </p>
    </div>
    <div class="brief-block">
      <h4>读者契约与核心期待</h4>
      <p>{{ brief.reader_contract || "等待方案生成" }}</p>
      <p><b>当前期待：</b>{{ brief.core_expectation || "等待方案生成" }}</p>
    </div>
    <div class="brief-block">
      <h4>世界规则</h4>
      <ul>
        <li v-for="(item, index) in brief.world_rules || []" :key="index">{{ item }}</li>
      </ul>
    </div>
    <div class="brief-block">
      <h4>连载计划</h4>
      <p>
        {{ brief.update_plan }}<br />
        预计 {{ brief.total_chapters }} 章 / {{ brief.volume_count }} 卷
      </p>
    </div>
  </div>
  <div v-else class="empty">创建小说后显示方案、卖点和世界规则。</div>
</template>
