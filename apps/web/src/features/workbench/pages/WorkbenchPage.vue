<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import ProjectShell from "@/layouts/ProjectShell.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";
import DeleteNovelDialog from "@/features/library/components/DeleteNovelDialog.vue";
import BriefDisplay from "@/features/story-brief/components/BriefDisplay.vue";
import BriefWorkbench from "@/features/story-brief/components/BriefWorkbench.vue";
import { useWorkbenchStore } from "@/features/workbench/store/workbench.store";
import { useOpeningRepairStore } from "@/features/workbench/store/opening-repair.store";
import { toUserError, useProjectsStore } from "@/stores/projects.store";
import { useAppStore } from "@/stores/app.store";
import { RouteNames } from "@/router/route-names";
import type { ChapterRecord, ProjectSummary } from "@/api/contracts";
import type { ChapterFailure, OpeningRepairPreview } from "../types/workbench.types";
import FailedChapterActions from "../components/FailedChapterActions.vue";
import OpeningRepairDialog from "../components/OpeningRepairDialog.vue";
import "../styles/workbench.css";

const route = useRoute();
const router = useRouter();
const workbench = useWorkbenchStore();
const openingRepair = useOpeningRepairStore();
const projects = useProjectsStore();
const app = useAppStore();

const editingBrief = ref(false);
const deleteOpen = ref(false);
const deleteError = ref("");
const reworkTarget = ref<ChapterRecord | null>(null);
const reworkMode = ref("replan");
const reworkFeedback = ref("");
const generatingLocked = ref(false);
const repairOpen = ref(false);
const repairPreview = ref<OpeningRepairPreview | null>(null);
const acceptTarget = ref<ChapterRecord | null>(null);

const projectId = computed(() => String(route.params.projectId || ""));
const summaryForDelete = computed<ProjectSummary | null>(() => {
  const current = workbench.project;
  if (!current) return null;
  return (
    projects.items.find((item) => item.id === current.id) || {
      id: current.id,
      title: current.title,
      status: current.status,
      confirmed: current.confirmed,
      audience_channel: current.request.audience_channel,
      genre: current.request.genre,
      chapter_count: workbench.chapters.length,
      content_chars: 0,
      current_chapter: current.current_chapter,
      created_at: current.created_at,
      updated_at: current.updated_at,
    }
  );
});

const reversedChapters = computed(() => workbench.chapters.slice().reverse());
const reserveChapters = computed(() => reversedChapters.value.slice(0, 5));
const canGenerate = computed(
  () => Boolean(workbench.project?.confirmed && workbench.project?.status === "ACTIVE")
);
const generateLabel = computed(() => workbench.generateLabel);

function failureFor(chapter: ChapterRecord): ChapterFailure | undefined {
  return workbench.chapterFailures.find((item) => item.chapter_number === chapter.number);
}

function chapterStatusLabel(chapter: ChapterRecord) {
  if (chapter.status !== "FAILED") return chapter.status;
  const failure = failureFor(chapter);
  const status = failure?.quality_status || "";
  if (status === "LENGTH_REPAIRING" || status === "LENGTH_NEEDS_ATTENTION") return "字数不足";
  if (status === "GENERATION_FAILED") return "生成未完成";
  return "质量待修改";
}

function failureSummary(failure: ChapterFailure | undefined) {
  if (!failure) return "需要处理";
  const status = failure.quality_status || "";
  if (status === "LENGTH_REPAIRING" || status === "LENGTH_NEEDS_ATTENTION") {
    const actual = failure.actual_length || 0;
    const minimum = failure.accepted_length_min || 0;
    return minimum ? `当前 ${actual} 字，至少需要 ${minimum} 字` : "正文字数不足";
  }
  if (status === "GENERATION_FAILED") return "正文生成未完成";
  if (failure.score != null) {
    return `质量分 ${Number(failure.score).toFixed(1)}，通过条件 > ${Number(failure.pass_score_exclusive ?? 60).toFixed(1)}`;
  }
  return "本章需要检查";
}

const deleteLabel = computed(() =>
  workbench.editableDraft ? "删除草稿" : "删除作品"
);

async function load() {
  if (!projectId.value) return;
  await app.refreshHealth();
  await workbench.loadDetail(projectId.value);
  await openingRepair.loadLatest(projectId.value);
}

watch(projectId, () => {
  void load().catch(() => undefined);
});

onMounted(() => {
  if (route.query.created === "1") {
    workbench.setCreatedBanner(true);
    void router.replace({
      name: RouteNames.Workbench,
      params: { projectId: projectId.value },
    });
  }
  void load().catch(() => undefined);
});

onUnmounted(() => {
  workbench.reset();
  openingRepair.reset();
});

async function onGenerate() {
  if (generatingLocked.value || !canGenerate.value) return;
  generatingLocked.value = true;
  try {
    await workbench.generate(projectId.value);
  } catch {
    /* flashed */
  } finally {
    generatingLocked.value = false;
  }
}

async function onConfirmDelete(confirmationTitle?: string) {
  if (!summaryForDelete.value) return;
  deleteError.value = "";
  try {
    app.setBusy(true);
    await projects.deleteProject(summaryForDelete.value.id, confirmationTitle);
    app.flash("作品已删除。");
    deleteOpen.value = false;
    await router.replace({ name: RouteNames.Library });
  } catch (error) {
    deleteError.value = toUserError(error, "删除失败");
  } finally {
    app.setBusy(false);
  }
}

async function confirmRework() {
  if (!reworkTarget.value) return;
  const number = reworkTarget.value.number;
  const feedback = reworkFeedback.value.trim();
  const mode = reworkMode.value;
  reworkTarget.value = null;
  reworkFeedback.value = "";
  try {
    await workbench.rework(projectId.value, number, feedback, mode);
  } catch {
    /* flashed */
  }
}

function startRework(chapter: ChapterRecord, mode: string) {
  reworkMode.value = mode;
  reworkTarget.value = chapter;
}

function startAccept(chapter: ChapterRecord) {
  acceptTarget.value = chapter;
}

async function confirmAccept() {
  if (!acceptTarget.value) return;
  const number = acceptTarget.value.number;
  acceptTarget.value = null;
  try {
    await workbench.acceptWithWarnings(projectId.value, number);
  } catch {
    /* flashed */
  }
}

async function openRepair() {
  try {
    repairPreview.value = (await workbench.inspectOpeningRepair(projectId.value)) ?? null;
    repairOpen.value = true;
  } catch {
    /* flashed */
  }
}

async function confirmRepair() {
  if (!repairPreview.value) return;
  await workbench.confirmOpeningRepair(
    projectId.value,
    repairPreview.value.project_updated_at
  );
  await openingRepair.loadLatest(projectId.value);
  repairOpen.value = false;
}

async function undoRepair() {
  try {
    await openingRepair.undo(projectId.value);
    await workbench.loadDetail(projectId.value);
  } catch {
    /* flashed */
  }
}

function chapterStatusClass(status: string) {
  if (status === "READY") return "status-ready";
  if (status === "FAILED") return "status-failed";
  return "";
}
</script>

<template>
  <ProjectShell>
    <p
      v-if="workbench.createdBanner && !workbench.project?.confirmed"
      class="created-banner"
      role="status"
    >
      创作方案已生成，请检查后确认
    </p>
    <LoadingBlock v-if="workbench.loading && !workbench.detail" />
    <ErrorSummary v-else-if="workbench.error && !workbench.detail" :messages="[workbench.error]" />
    <div v-else-if="workbench.project" class="workbench-page">
      <section class="hero-card">
        <div>
          <span class="pill">{{ workbench.statusLabel }}</span>
          <h2>{{ workbench.project.title }}</h2>
          <p>{{ workbench.project.brief.synopsis }}</p>
        </div>
        <div class="hero-actions">
          <BaseButton
            v-if="!workbench.project.confirmed"
            variant="primary"
            :disabled="workbench.acting"
            @click="workbench.confirm(projectId)"
          >
            确认创作方案
          </BaseButton>
          <BaseButton
            v-if="workbench.editableDraft"
            variant="ghost"
            @click="editingBrief = !editingBrief"
          >
            修改方案
          </BaseButton>
          <BaseButton
            v-if="workbench.editableDraft"
            variant="ghost"
            :disabled="workbench.acting"
            @click="workbench.redoBrief(projectId, { feedback: '', sections: [] })"
          >
            重新生成
          </BaseButton>
          <BaseButton
            v-if="workbench.project.status === 'HUMAN_REQUIRED'"
            :disabled="workbench.acting"
            @click="workbench.recover(projectId)"
          >
            修复并恢复
          </BaseButton>
          <BaseButton
            v-if="workbench.project.confirmed"
            variant="primary"
            :disabled="!canGenerate || generatingLocked || workbench.acting"
            :loading="generatingLocked"
            @click="onGenerate"
          >
            {{ generateLabel }}
          </BaseButton>
          <BaseButton
            v-if="openingRepair.latest && !openingRepair.loadError"
            variant="ghost"
            :disabled="workbench.acting || !openingRepair.canRollback"
            :title="openingRepair.latest.blocked_reason || '回退开篇修复'"
            @click="undoRepair"
          >
            回退开篇修复
          </BaseButton>
          <span
            v-if="openingRepair.latest && !openingRepair.canRollback && openingRepair.latest.blocked_reason"
            class="empty"
          >
            {{ openingRepair.latest.blocked_reason }}
          </span>
          <BaseButton
            v-if="workbench.project.confirmed"
            variant="ghost"
            :disabled="workbench.acting"
            @click="workbench.togglePause(projectId)"
          >
            {{ workbench.project.status === "PAUSED" ? "继续" : "暂停" }}
          </BaseButton>
          <BaseButton variant="danger" @click="deleteOpen = true">{{ deleteLabel }}</BaseButton>
        </div>
      </section>

      <BriefWorkbench
        v-if="workbench.editableDraft && workbench.project.brief"
        v-model:editing="editingBrief"
        :brief="workbench.project.brief"
        :versions="workbench.briefVersions"
        :acting="workbench.acting"
        @save="(brief) => workbench.saveBrief(projectId, brief)"
        @regenerate="(payload) => workbench.redoBrief(projectId, payload)"
        @restore="(version) => workbench.restoreVersion(projectId, version)"
      />

      <template v-if="workbench.project.confirmed">
        <div class="metric-grid">
          <article class="metric"><span>今日完成</span><strong>{{ workbench.todayCount }}</strong><small>章节</small></article>
          <article class="metric">
            <span>READY 储备</span>
            <strong>{{ workbench.detail?.reserve_count ?? 0 }}</strong>
            <small>目标 {{ workbench.project.request.reserve_target }}</small>
          </article>
          <article class="metric"><span>当前进度</span><strong>{{ workbench.readyCount }}</strong><small>正式章节</small></article>
          <article class="metric"><span>运行健康度</span><strong>{{ workbench.healthLabel }}</strong><small>本地数据层</small></article>
        </div>

        <div class="two-column">
        <article class="legacy-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">生产流程</p>
              <h3>章节生产流程</h3>
            </div>
            <span class="badge">可恢复</span>
          </div>
          <div class="pipeline">
            <div v-if="!workbench.pipelineEvents.length" class="empty">生成章节后，这里会显示每个工作流节点。</div>
            <div v-for="(event, index) in workbench.pipelineEvents" :key="index" class="pipeline-event">
              <span class="node-dot">{{ index + 1 }}</span>
              <div>
                <b>{{ event.node }}</b>
                <p>{{ event.message }}</p>
              </div>
              <time>{{ event.progress }}%</time>
            </div>
          </div>
        </article>
        <article class="legacy-panel">
          <div class="panel-head">
            <h3>章节储备</h3>
            <button class="text-button" type="button" @click="router.push({ name: RouteNames.Reader, params: { projectId } })">
              查看全部
            </button>
          </div>
          <div class="chapter-list">
            <div v-if="!reversedChapters.length" class="empty">暂无章节</div>
            <div
              v-for="chapter in reserveChapters"
              :key="chapter.id"
              class="chapter-row"
            >
              <div class="chapter-row__top">
                <RouterLink
                  class="chapter-row__link"
                  :to="{
                    name: RouteNames.Reader,
                    params: { projectId },
                    query: { chapter: String(chapter.number) },
                  }"
                >
                  <b>{{ chapter.title }}</b>
                  <span>v{{ chapter.version }} · {{ chapter.summary || "等待生成" }}</span>
                </RouterLink>
                <span class="chapter-status" :class="chapterStatusClass(chapter.status)">
                  {{ chapterStatusLabel(chapter) }}
                </span>
              </div>
              <div class="chapter-row-actions">
                <p v-if="chapter.status === 'FAILED'" class="chapter-failure-summary">
                  {{ failureSummary(failureFor(chapter)) }}
                </p>
                <details v-if="chapter.status === 'FAILED'" class="chapter-action-menu">
                  <summary>处理</summary>
                  <FailedChapterActions
                    v-if="failureFor(chapter)"
                    :failure="failureFor(chapter)!"
                    @inspect="startRework(chapter, failureFor(chapter)?.recommended_rework_mode || 'replan')"
                    @replan="startRework(chapter, 'replan')"
                    @reuse="startRework(chapter, 'reuse_plan')"
                    @accept="startAccept(chapter)"
                    @repair="openRepair"
                  />
                </details>
                <button
                  v-else-if="chapter.status !== 'PLANNED'"
                  class="text-button"
                  type="button"
                  @click="startRework(chapter, 'auto')"
                >
                  重做
                </button>
              </div>
            </div>
            <p v-if="reversedChapters.length > reserveChapters.length" class="chapter-list-more">
              仅显示最近 {{ reserveChapters.length }} 章，其余请点击「查看全部」。
            </p>
          </div>
        </article>
        </div>

        <article class="legacy-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">创作方案</p>
              <h3>创作方案</h3>
            </div>
          </div>
          <BriefDisplay :brief="workbench.project.brief" :request="workbench.project.request" />
        </article>
      </template>
    </div>

    <DeleteNovelDialog
      :open="deleteOpen"
      :novel="summaryForDelete"
      :error="deleteError"
      @close="deleteOpen = false"
      @confirm="onConfirmDelete"
    />

    <OpeningRepairDialog
      :open="repairOpen"
      :preview="repairPreview"
      :acting="workbench.acting"
      @close="repairOpen = false"
      @confirm="confirmRepair"
    />
    <BaseDialog
      :open="Boolean(reworkTarget)"
      :title="`打回第 ${reworkTarget?.number ?? ''} 章重做`"
      :description="reworkMode === 'replan' ? '将重新规划细纲后再写。修改意见可选。' : '将沿用现有细纲重写。修改意见可选。'"
      @close="reworkTarget = null"
    >
      <textarea
        v-model="reworkFeedback"
        class="rework-feedback"
        rows="4"
        autofocus
        aria-label="章节重做意见"
        placeholder="例如：主角对话太生硬，需要更自然。"
      />
      <template #footer>
        <BaseButton variant="ghost" @click="reworkTarget = null">取消</BaseButton>
        <BaseButton variant="primary" @click="confirmRework">确认打回</BaseButton>
      </template>
    </BaseDialog>
    <BaseDialog
      :open="Boolean(acceptTarget)"
      title="接受当前版本并继续"
      description="仅在没有硬阻断时可用。接受后当前草稿会成为正式章节并写入记忆，之后仍可修订。"
      @close="acceptTarget = null"
    >
      <ul v-if="acceptTarget && failureFor(acceptTarget)">
        <li
          v-for="(issue, index) in (failureFor(acceptTarget)?.issues || []).slice(0, 5)"
          :key="index"
        >
          {{ issue.message || issue.category }}
        </li>
      </ul>
      <template #footer>
        <BaseButton variant="ghost" @click="acceptTarget = null">取消</BaseButton>
        <BaseButton variant="primary" @click="confirmAccept">确认接受并继续</BaseButton>
      </template>
    </BaseDialog>
  </ProjectShell>
</template>

<style scoped>
.rework-feedback {
  width: 100%;
  min-height: 96px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  resize: none;
}
</style>
