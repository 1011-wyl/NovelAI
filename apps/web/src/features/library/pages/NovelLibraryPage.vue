<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppShell from "@/layouts/AppShell.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import LibraryToolbar from "@/features/library/components/LibraryToolbar.vue";
import NovelCard from "@/features/library/components/NovelCard.vue";
import NovelListItem from "@/features/library/components/NovelListItem.vue";
import RenameNovelDialog from "@/features/library/components/RenameNovelDialog.vue";
import DeleteNovelDialog from "@/features/library/components/DeleteNovelDialog.vue";
import type { ProjectSummary } from "@/api/contracts";
import { toUserError, useProjectsStore } from "@/stores/projects.store";
import { RouteNames } from "@/router/route-names";

const projects = useProjectsStore();
const router = useRouter();

const searchDraft = ref(projects.searchQuery);
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const renameTarget = ref<ProjectSummary | null>(null);
const deleteTarget = ref<ProjectSummary | null>(null);
const renameSaving = ref(false);
const deleteSaving = ref(false);
const renameError = ref("");
const deleteError = ref("");

const isEmpty = computed(
  () => !projects.loading && !projects.error && projects.items.length === 0
);
const noSearchResult = computed(
  () =>
    !projects.loading &&
    !projects.error &&
    projects.items.length > 0 &&
    projects.filteredProjects.length === 0
);

watch(searchDraft, (value) => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    projects.searchQuery = value;
  }, 200);
});

onMounted(() => {
  void projects.loadProjects().catch(() => undefined);
});

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});

function goCreate() {
  void router.push({ name: RouteNames.NovelCreate });
}

function clearSearch() {
  searchDraft.value = "";
  projects.searchQuery = "";
}

async function reload() {
  try {
    await projects.loadProjects();
  } catch {
    /* shown via store.error */
  }
}

async function onRenameSave(title: string) {
  if (!renameTarget.value) return;
  renameSaving.value = true;
  renameError.value = "";
  try {
    await projects.renameProject(renameTarget.value.id, title);
    renameTarget.value = null;
  } catch (error) {
    renameError.value = toUserError(error, "修改书名失败");
  } finally {
    renameSaving.value = false;
  }
}

async function onDeleteConfirm(confirmationTitle?: string) {
  if (!deleteTarget.value) return;
  deleteSaving.value = true;
  deleteError.value = "";
  const id = deleteTarget.value.id;
  try {
    await projects.deleteProject(id, confirmationTitle);
    deleteTarget.value = null;
  } catch (error) {
    deleteError.value = toUserError(error, "删除失败");
  } finally {
    deleteSaving.value = false;
  }
}
</script>

<template>
  <AppShell>
    <div class="library-page">
      <header class="page-header">
        <h1>我的小说</h1>
        <p class="muted">从书架开始，选择或创建一本小说进入创作工作台。</p>
      </header>

      <p v-if="projects.notice" class="notice" role="status">
        {{ projects.notice }}
        <button type="button" class="notice-dismiss" @click="projects.clearNotice()">
          知道了
        </button>
      </p>

      <LibraryToolbar
        v-model:search-query="searchDraft"
        v-model:sort-by="projects.sortBy"
        v-model:view-mode="projects.viewMode"
        @create="goCreate"
      />

      <LoadingBlock v-if="projects.loading && projects.items.length === 0" label="正在加载书架" :lines="5" />

      <div v-else-if="projects.error" class="state-panel" role="alert">
        <h2>书架加载失败</h2>
        <p class="muted">{{ projects.error }}</p>
        <BaseButton variant="primary" @click="reload">重新加载</BaseButton>
      </div>

      <div v-else-if="isEmpty" class="state-panel">
        <h2>从一个想法开始你的第一本小说</h2>
        <p class="muted">创建后会生成创作方案，并进入对应的创作工作台。</p>
        <BaseButton variant="primary" @click="goCreate">创建第一本小说</BaseButton>
      </div>

      <div v-else-if="noSearchResult" class="state-panel">
        <h2>没有找到匹配的小说</h2>
        <p class="muted">当前搜索：{{ projects.searchQuery }}</p>
        <BaseButton @click="clearSearch">清空搜索</BaseButton>
      </div>

      <div v-else-if="projects.viewMode === 'grid'" class="novel-grid">
        <NovelCard
          v-for="novel in projects.filteredProjects"
          :key="novel.id"
          :novel="novel"
          @rename="renameTarget = $event"
          @delete="deleteTarget = $event"
        />
      </div>

      <div v-else class="novel-list">
        <NovelListItem
          v-for="novel in projects.filteredProjects"
          :key="novel.id"
          :novel="novel"
          @rename="renameTarget = $event"
          @delete="deleteTarget = $event"
        />
      </div>
    </div>

    <RenameNovelDialog
      :open="!!renameTarget"
      :novel="renameTarget"
      :saving="renameSaving"
      :error="renameError"
      @close="renameTarget = null"
      @save="onRenameSave"
    />
    <DeleteNovelDialog
      :open="!!deleteTarget"
      :novel="deleteTarget"
      :deleting="deleteSaving"
      :error="deleteError"
      @close="deleteTarget = null"
      @confirm="onDeleteConfirm"
    />
  </AppShell>
</template>

<style scoped>
.page-header {
  margin-bottom: var(--space-4);
}

.page-header h1 {
  font-size: 1.75rem;
  margin-bottom: var(--space-2);
}

.notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface-muted);
}

.notice-dismiss {
  border: 0;
  background: transparent;
  text-decoration: underline;
  min-height: var(--touch-min);
}

.state-panel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}

.novel-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-4);
}

.novel-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

@media (max-width: 1199px) {
  .novel-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .novel-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
