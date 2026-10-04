<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ProjectShell from "@/layouts/ProjectShell.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";
import ChapterRecoveryBanner from "../components/ChapterRecoveryBanner.vue";
import { useWorkbenchStore } from "@/features/workbench/store/workbench.store";
import { RouteNames } from "@/router/route-names";
import { useReaderWorkspace, QUICK_LABELS } from "../composables/useReaderWorkspace";
import type { QuickAction } from "../api/reader.api";
import "../styles/reader-workspace.css";

const route = useRoute();
const router = useRouter();
const workbench = useWorkbenchStore();

const projectId = computed(() => String(route.params.projectId || ""));
const initialChapter = computed(() => {
  const raw = route.query.chapter;
  const value = Array.isArray(raw) ? raw[0] : raw;
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
});

const projectDetail = computed(() =>
  workbench.detail?.project?.id === projectId.value ? workbench.detail : null
);

const {
  rootRef,
  titleRef,
  contentRef,
  messagesRef,
  assistantInputRef,
  selectionBarRef,
  confirmBtnRef,
  cancelBtnRef,
  chapterNumber,
  filter,
  mode,
  messages,
  saveState,
  saveStatusLabel,
  title,
  content,
  assistantInput,
  refChipText,
  chaptersOpen,
  assistantOpen,
  workspaceError,
  recoveryBannerRef,
  capabilitiesMissing,
  showChapter,
  aiBusy,
  dialog,
  selectionMenu,
  chapterLabel,
  chapterCharCount,
  wordCountLabel,
  selectedCountLabel,
  capabilities,
  canUseAssistant,
  currentFailure,
  discardDisabled,
  commitDisabled,
  submitDisabled,
  acceptDisabled,
  editorDisabled,
  contentReadOnly,
  filteredChapters,
  chapterCountLabel,
  changeByMessage,
  isChapterDirty,
  diffLines,
  openChapter,
  bootstrapProject,
  onEditorInput,
  onSelectionChange,
  onContentContextMenu,
  hideSelectionMenu,
  handleQuick,
  flushSave,
  createSession,
  sendAssistant,
  decideChange,
  rollbackTo,
  discardDraft,
  showVersions,
  restoreVersionAsDraft,
  commitRevisionFlow,
  submitFailedReviewFlow,
  acceptWithWarningsFlow,
  openChaptersOverlay,
  openAssistantOverlay,
  closeAssistantOverlay,
  onAssistantKeydown,
  closeDialog,
} = useReaderWorkspace({
  projectId,
  projectDetail,
  initialChapter,
  onProjectReload: async () => {
    if (projectId.value) await workbench.loadDetail(projectId.value);
  },
});

async function ensureDetail() {
  if (!projectId.value) return;
  if (workbench.detail?.project?.id !== projectId.value) {
    await workbench.loadDetail(projectId.value);
  } else if (projectDetail.value) {
    await bootstrapProject(projectDetail.value, initialChapter.value);
  }
}

onMounted(() => {
  void ensureDetail().catch(() => undefined);
});

watch(projectId, () => {
  void ensureDetail().catch(() => undefined);
});

function onOpenChapter(number: number) {
  void router.replace({
    params: route.params,
    query: { ...route.query, chapter: String(number) },
  });
  const chapter = projectDetail.value?.chapters.find((item) => item.number === number);
  if (chapter) void openChapter(chapter);
}

function onQuick(action: QuickAction | "attach") {
  void handleQuick(action);
}
</script>

<template>
  <ProjectShell>
    <LoadingBlock v-if="workbench.loading && !projectDetail" label="正在加载阅读工作台…" />
    <div
      v-else
      id="readerView"
      ref="rootRef"
      class="writing-workspace active"
      :class="{
        'show-chapter': showChapter,
        'chapters-open': chaptersOpen,
        'assistant-open': assistantOpen,
        'assistant-closed': !assistantOpen,
      }"
    >
      <aside class="workspace-chapters" aria-label="章节列表">
        <div class="ws-panel-head ws-book-head">
          <strong>{{ projectDetail?.project.title || "作品阅读" }}</strong>
        </div>
        <div class="ws-chapter-filters" role="group" aria-label="章节筛选">
          <button type="button" class="ws-filter" :aria-pressed="filter === 'all'" @click="filter = 'all'">全部</button>
          <button type="button" class="ws-filter" :aria-pressed="filter === 'READY'" @click="filter = 'READY'">READY</button>
          <button type="button" class="ws-filter" :aria-pressed="filter === 'other'" @click="filter = 'other'">其他</button>
          <span class="ws-chapter-count">{{ chapterCountLabel }}</span>
        </div>
        <div class="ws-chapter-list">
          <div v-if="!filteredChapters.length" class="empty">暂无章节</div>
          <button
            v-for="chapter in filteredChapters"
            :key="chapter.id"
            type="button"
            class="ws-chapter-item"
            :aria-current="chapter.number === chapterNumber ? 'page' : undefined"
            @click="onOpenChapter(chapter.number)"
          >
            <b>{{ chapter.title }}</b>
            <span class="meta">
              <span>{{ chapter.status }}</span>
              <span>v{{ chapter.version }}</span>
              <span v-if="isChapterDirty(chapter.number)" class="ws-dot" title="未提交" />
            </span>
          </button>
        </div>
      </aside>

      <main class="workspace-editor" aria-label="章节编辑区">
        <ChapterRecoveryBanner
          ref="recoveryBannerRef"
          :chapter="filteredChapters.find((item) => item.number === chapterNumber) || null"
          :failure="currentFailure"
          :current-length="chapterCharCount"
          :can-accept="Boolean(capabilities.accept_with_warnings)"
          :accept-disabled="acceptDisabled"
          @workbench="router.push({ name: RouteNames.Workbench, params: { projectId } })"
          @review="assistantOpen = true"
          @accept="acceptWithWarningsFlow"
        />
        <ErrorSummary v-if="workspaceError || capabilitiesMissing" :messages="[workspaceError || '服务器未返回工作区能力，请刷新或升级后端']" />
        <div class="ws-editor-toolbar">
          <button type="button" class="ws-mode ws-overlay-toggle" aria-label="打开章节目录" @click="openChaptersOverlay">目录</button>
          <strong>{{ chapterLabel }}</strong>
          <span
            class="ws-status"
            :class="{ error: saveState === 'error', conflict: saveState === 'conflict' }"
            role="status"
            @click="saveState === 'error' || saveState === 'conflict' ? flushSave() : undefined"
          >
            {{ saveStatusLabel }}
          </span>
          <span class="spacer" />
          <div class="ws-mode-group" role="group" aria-label="章节操作">
            <button type="button" class="ws-mode" aria-label="版本历史" @click="showVersions">版本</button>
            <button type="button" class="ws-mode" aria-label="放弃草稿" :disabled="discardDisabled" @click="discardDraft">放弃草稿</button>
            <button
              v-if="capabilities.submit_for_review"
              type="button"
              class="ws-mode"
              aria-label="重新送审"
              :disabled="submitDisabled"
              @click="submitFailedReviewFlow"
            >
              重新送审
            </button>
            <button
              v-else
              type="button"
              class="ws-mode"
              aria-label="应用修订"
              :disabled="commitDisabled"
              @click="commitRevisionFlow"
            >
              应用修订
            </button>
          </div>
          <button type="button" class="ws-mode ws-overlay-toggle ws-assistant-toggle" aria-label="打开 AI 助手" @click="openAssistantOverlay">AI</button>
        </div>
        <div class="ws-editor-body">
          <input
            id="wsTitleInput"
            ref="titleRef"
            v-model="title"
            class="ws-title-input"
            type="text"
            maxlength="120"
            spellcheck="false"
            placeholder="章节标题"
            :disabled="editorDisabled"
            :readonly="contentReadOnly"
            @input="onEditorInput"
          />
          <textarea
            id="wsContentInput"
            ref="contentRef"
            v-model="content"
            class="ws-content-input"
            spellcheck="false"
            placeholder="选择 READY 章节后开始阅读或修订。"
            :disabled="editorDisabled"
            :readonly="contentReadOnly"
            @input="onEditorInput"
            @select="onSelectionChange"
            @keyup="onSelectionChange"
            @mouseup="onSelectionChange"
            @contextmenu="onContentContextMenu"
            @scroll="hideSelectionMenu"
          />
          <div class="ws-editor-footer">
            <span>{{ wordCountLabel }}</span>
            <span>{{ selectedCountLabel }}</span>
          </div>
        </div>
      </main>

      <aside class="workspace-assistant" aria-label="AI 修订助手">
        <div class="ws-panel-head">
          <div class="ws-assistant-modes" role="group" aria-label="助手模式">
            <button type="button" class="ws-mode" :aria-pressed="mode === 'advisor'" :disabled="!canUseAssistant" @click="mode = 'advisor'">顾问</button>
            <button type="button" class="ws-mode" :aria-pressed="mode === 'coauthor'" :disabled="!canUseAssistant" @click="mode = 'coauthor'">共创</button>
            <button type="button" class="ws-mode" :aria-pressed="mode === 'editor'" :disabled="!canUseAssistant" @click="mode = 'editor'">编辑</button>
          </div>
          <div class="ws-mode-group" role="group" aria-label="会话操作">
            <button type="button" class="ws-mode" aria-label="新建会话" :disabled="!canUseAssistant" @click="createSession">新建</button>
            <button type="button" class="ws-mode" aria-label="关闭助手" @click="closeAssistantOverlay">关闭</button>
          </div>
        </div>
        <div ref="messagesRef" class="ws-messages">
          <div v-if="!messages.length" class="empty">向 AI 提问或请求改写。修改需批准后才会进入草稿。</div>
          <article v-for="msg in messages" :key="msg.id" class="ws-msg" :class="msg.role">
            <div class="role">{{ msg.role === "user" ? "你" : "AI" }} · {{ msg.mode }}</div>
            <div>{{ msg.content }}</div>
            <div v-if="msg.selection?.text" class="ws-ref-chip visible">
              引用：{{ msg.selection.text.slice(0, 80) }}
            </div>
            <div
              v-if="changeByMessage.get(msg.id)"
              class="ws-change"
              :data-status="changeByMessage.get(msg.id)?.status"
            >
              <div class="ws-diff">
                <div
                  v-for="(line, index) in diffLines(changeByMessage.get(msg.id)!)"
                  :key="index"
                  class="ws-diff-line"
                  :class="line.type"
                >
                  <span>{{ line.mark }}</span>{{ line.text }}
                </div>
              </div>
              <p class="ws-explain">{{ changeByMessage.get(msg.id)?.explanation || "建议修改" }}</p>
              <div v-if="changeByMessage.get(msg.id)?.status === 'proposed'" class="ws-change-actions">
                <button type="button" class="ws-mode" @click="decideChange(changeByMessage.get(msg.id)!.id, 'approve')">批准</button>
                <button type="button" class="ws-mode" @click="decideChange(changeByMessage.get(msg.id)!.id, 'reject')">拒绝</button>
              </div>
              <div v-else class="ws-change-actions">
                <span class="muted">{{ changeByMessage.get(msg.id)?.status }}</span>
              </div>
            </div>
            <div v-if="msg.role === 'user'">
              <button type="button" class="ws-mode" @click="rollbackTo(msg.id)">回滚到这里</button>
            </div>
          </article>
        </div>
        <div class="ws-composer">
          <div class="ws-ref-chip" :class="{ visible: !!refChipText }">{{ refChipText }}</div>
          <textarea
            ref="assistantInputRef"
            v-model="assistantInput"
            :disabled="!canUseAssistant"
            placeholder="输入修订意见… Enter 发送，Shift+Enter 换行"
            @keydown="onAssistantKeydown"
          />
          <div class="ws-composer-actions">
            <button type="button" class="primary-button" aria-label="发送" :disabled="aiBusy || !canUseAssistant" @click="sendAssistant()">发送</button>
          </div>
        </div>
      </aside>

      <div
        v-show="selectionMenu.visible"
        ref="selectionBarRef"
        class="ws-selection-menu"
        role="menu"
        aria-label="选区优化"
        :style="{ left: `${selectionMenu.left}px`, top: `${selectionMenu.top}px` }"
        @mousedown.prevent
      >
        <button
          v-for="(label, action) in QUICK_LABELS"
          :key="action"
          type="button"
          role="menuitem"
          @click="onQuick(action)"
        >
          {{ label }}
        </button>
        <button type="button" role="menuitem" @click="onQuick('attach')">引用到对话</button>
        <span class="ws-selection-count">{{ selectionMenu.charCount }} 字</span>
      </div>

      <BaseDialog
        :open="dialog.kind !== 'closed'"
        :title="dialog.kind === 'closed' ? '' : dialog.title"
        @close="closeDialog(false)"
      >
        <template v-if="dialog.kind === 'confirm'">
          <p v-for="(paragraph, index) in dialog.paragraphs" :key="index">{{ paragraph }}</p>
        </template>
        <template v-else-if="dialog.kind === 'versions'">
          <div v-for="item in dialog.versions" :key="item.version" class="ws-version-item">
            <div>
              <b>v{{ item.version }} · {{ item.kind }}</b>
              <span class="muted">{{ item.source }}</span>
            </div>
            <button type="button" class="text-button" @click="restoreVersionAsDraft(item.version)">
              恢复为草稿
            </button>
          </div>
        </template>
        <template #footer>
          <button
            v-if="dialog.kind === 'confirm' && dialog.cancelLabel"
            ref="cancelBtnRef"
            type="button"
            class="text-button"
            @click="closeDialog(false)"
          >
            {{ dialog.cancelLabel }}
          </button>
          <button
            v-if="dialog.kind === 'confirm'"
            ref="confirmBtnRef"
            type="button"
            :class="dialog.danger ? 'danger-button' : 'primary-button'"
            @click="closeDialog(true)"
          >
            {{ dialog.confirmLabel }}
          </button>
          <button v-else type="button" class="text-button" @click="closeDialog(false)">关闭</button>
        </template>
      </BaseDialog>
    </div>
  </ProjectShell>
</template>
