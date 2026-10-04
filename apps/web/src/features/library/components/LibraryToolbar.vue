<script setup lang="ts">
import { LayoutGrid, List, Plus, Search } from "lucide-vue-next";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIconButton from "@/components/base/BaseIconButton.vue";
import type { LibrarySortBy, LibraryViewMode } from "@/stores/projects.store";

defineProps<{
  searchQuery: string;
  sortBy: LibrarySortBy;
  viewMode: LibraryViewMode;
}>();

const emit = defineEmits<{
  "update:searchQuery": [value: string];
  "update:sortBy": [value: LibrarySortBy];
  "update:viewMode": [value: LibraryViewMode];
  create: [];
}>();
</script>

<template>
  <div class="library-toolbar">
    <BaseButton variant="primary" @click="emit('create')">
      <Plus :size="16" aria-hidden="true" />
      新建小说
    </BaseButton>
    <label class="search">
      <Search :size="16" aria-hidden="true" />
      <span class="sr-only">搜索小说</span>
      <input
        type="search"
        placeholder="搜索小说……"
        :value="searchQuery"
        @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label class="sort">
      <span class="sr-only">排序</span>
      <select
        :value="sortBy"
        @change="emit('update:sortBy', ($event.target as HTMLSelectElement).value as LibrarySortBy)"
      >
        <option value="updated_at">最近编辑</option>
        <option value="created_at">最近创建</option>
        <option value="title">书名</option>
      </select>
    </label>
    <div class="view-toggle" role="group" aria-label="视图切换">
      <BaseIconButton
        label="网格视图"
        :class="{ active: viewMode === 'grid' }"
        @click="emit('update:viewMode', 'grid')"
      >
        <LayoutGrid :size="18" />
      </BaseIconButton>
      <BaseIconButton
        label="列表视图"
        :class="{ active: viewMode === 'list' }"
        @click="emit('update:viewMode', 'list')"
      >
        <List :size="18" />
      </BaseIconButton>
    </div>
  </div>
</template>

<style scoped>
.library-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-6);
}

.search {
  flex: 1;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  min-height: 40px;
}

.sort select {
  min-height: var(--touch-min);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.view-toggle {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.view-toggle :deep(.icon-button) {
  border-radius: 0;
  border: 0;
}

.view-toggle :deep(.icon-button.active) {
  background: var(--color-surface-muted);
}

@media (max-width: 767px) {
  .library-toolbar {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
  }

  .search {
    min-width: 0;
  }

  .sort {
    min-width: 0;
  }

  .sort select {
    width: 100%;
  }

  .view-toggle {
    justify-self: start;
  }
}
</style>
