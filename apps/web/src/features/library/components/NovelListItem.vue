<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { MoreHorizontal } from "lucide-vue-next";
import BaseStatusBadge from "@/components/base/BaseStatusBadge.vue";
import BaseIconButton from "@/components/base/BaseIconButton.vue";
import type { ProjectSummary } from "@/api/contracts";
import { useActionMenu } from "@/composables/useActionMenu";
import { formatChars, formatRelativeTime, shelfStatusOf } from "@/features/library/types";

const props = defineProps<{
  novel: ProjectSummary;
}>();

const emit = defineEmits<{
  rename: [novel: ProjectSummary];
  delete: [novel: ProjectSummary];
}>();

const { menuOpen, menuRootRef, toggleMenu, closeMenu, onMenuKeydown } = useActionMenu();
const status = computed(() => shelfStatusOf(props.novel));

function renameNovel() {
  closeMenu(true);
  emit("rename", props.novel);
}

function deleteNovel() {
  closeMenu(true);
  emit("delete", props.novel);
}

</script>

<template>
  <article class="novel-list-item">
    <RouterLink
      class="title-link"
      :to="`/novels/${novel.id}/workbench`"
      :title="novel.title"
    >
      {{ novel.title }}
    </RouterLink>
    <span class="muted">{{ novel.genre }}</span>
    <span class="muted">{{ formatChars(novel.content_chars) }} · {{ novel.chapter_count }} 章</span>
    <BaseStatusBadge :label="status.label" :tone="status.tone" />
    <span class="muted">{{ formatRelativeTime(novel.updated_at) }}</span>
    <div class="actions">
      <RouterLink class="continue-link" :to="`/novels/${novel.id}/workbench`">
        继续创作
      </RouterLink>
      <div ref="menuRootRef" class="menu" @keydown="onMenuKeydown">
        <BaseIconButton
          label="更多操作"
          aria-haspopup="menu"
          :aria-expanded="menuOpen"
          @click="toggleMenu"
        >
          <MoreHorizontal :size="18" />
        </BaseIconButton>
        <div v-if="menuOpen" class="menu-panel" role="menu">
          <button type="button" role="menuitem" @click="renameNovel">
            修改书名
          </button>
          <button type="button" role="menuitem" @click="deleteNovel">
            删除
          </button>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.novel-list-item {
  display: grid;
  grid-template-columns: minmax(140px, 1.4fr) 0.8fr 1fr auto 0.8fr auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.title-link {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  justify-content: flex-end;
}

.continue-link {
  min-height: var(--touch-min);
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.menu {
  position: relative;
}

.menu-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  min-width: 140px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-float);
  padding: var(--space-1);
  z-index: 5;
}

.menu-panel button {
  display: block;
  width: 100%;
  text-align: left;
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 0;
  background: transparent;
}

@media (max-width: 900px) {
  .novel-list-item {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }
}
</style>
