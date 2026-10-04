<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { MoreHorizontal } from "lucide-vue-next";
import BaseStatusBadge from "@/components/base/BaseStatusBadge.vue";
import BaseIconButton from "@/components/base/BaseIconButton.vue";
import type { ProjectSummary } from "@/api/contracts";
import { useActionMenu } from "@/composables/useActionMenu";
import {
  coverSeed,
  formatChars,
  formatRelativeTime,
  shelfStatusOf,
} from "@/features/library/types";

const props = defineProps<{
  novel: ProjectSummary;
}>();

const emit = defineEmits<{
  rename: [novel: ProjectSummary];
  delete: [novel: ProjectSummary];
}>();

const { menuOpen, menuRootRef, toggleMenu, closeMenu, onMenuKeydown } = useActionMenu();
const status = computed(() => shelfStatusOf(props.novel));
const seed = computed(() => coverSeed(props.novel));
const initial = computed(() => props.novel.title.slice(0, 1) || "书");
const hue = computed(() => seed.value % 360);

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
  <article class="novel-card">
    <RouterLink
      class="novel-card__cover-link"
      :to="`/novels/${novel.id}/workbench`"
      :title="novel.title"
      :aria-label="`打开《${novel.title}》创作工作台`"
    >
      <div
        class="novel-card__cover"
        :style="{
          background: `linear-gradient(145deg, hsl(${hue} 18% 86%), hsl(${(hue + 40) % 360} 12% 72%))`,
        }"
      >
        <svg viewBox="0 0 64 96" aria-hidden="true" class="book-icon">
          <rect x="10" y="8" width="44" height="80" rx="3" fill="rgba(255,255,255,0.55)" />
          <rect x="14" y="12" width="4" height="72" fill="rgba(32,32,32,0.2)" />
        </svg>
        <span class="cover-initial">{{ initial }}</span>
      </div>
    </RouterLink>
    <div class="novel-card__body">
      <h3 class="novel-card__title" :title="novel.title">{{ novel.title }}</h3>
      <p class="meta muted">
        <span>{{ novel.genre }}</span>
        ·
        <span>{{ formatChars(novel.content_chars) }}</span>
        ·
        <span>{{ novel.chapter_count }} 章</span>
      </p>
      <div class="novel-card__status-row">
        <BaseStatusBadge :label="status.label" :tone="status.tone" />
        <span class="muted time">{{ formatRelativeTime(novel.updated_at) }}</span>
      </div>
      <div class="novel-card__actions">
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
    </div>
  </article>
</template>

<style scoped>
.novel-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-surface);
  transition: border-color 180ms ease;
}

.novel-card:hover {
  border-color: color-mix(in srgb, var(--color-text) 25%, var(--color-border));
}

.novel-card__cover-link {
  display: block;
}

.novel-card__cover {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: grid;
  place-items: center;
}

.book-icon {
  width: 48px;
  opacity: 0.7;
}

.cover-initial {
  position: absolute;
  bottom: var(--space-3);
  right: var(--space-3);
  font-size: 1.5rem;
  font-weight: 700;
  color: rgba(32, 32, 32, 0.7);
}

.novel-card__title {
  font-size: 1rem;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.7em;
}

.meta {
  font-size: 0.85rem;
}

.novel-card__status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.time {
  font-size: 0.8rem;
}

.novel-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  bottom: calc(100% + 4px);
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
  border-radius: var(--radius-sm);
}

.menu-panel button:hover {
  background: var(--color-surface-muted);
}
</style>
