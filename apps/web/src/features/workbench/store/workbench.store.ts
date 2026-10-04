import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { BriefVersion, PipelineEvent, ProjectDetail } from "@/api/contracts";
import { isApiError } from "@/api/api-error";
import { toUserError, useProjectsStore } from "@/stores/projects.store";
import { useAppStore } from "@/stores/app.store";
import {
  abortBriefVersions,
  abortProjectDetail,
  acceptChapterWithWarnings,
  applyOpeningRepair,
  confirmProject,
  generateNextChapter,
  getChapterWorkspace,
  getProjectDetail,
  listBriefVersions,
  pauseProject,
  previewOpeningRepair,
  recoverProject,
  regenerateBrief,
  restoreBrief,
  resumeProject,
  reworkChapter,
  rollbackOpeningRepair,
  updateBrief,
} from "../api/workbench.api";
import type { OpeningRepairPreview } from "../types/workbench.types";
import type { CreativeBrief } from "@/api/contracts";

const WORKBENCH_STATUS: Record<string, string> = {
  DRAFT: "等待方案确认",
  ACTIVE: "自动连载可用",
  PAUSED: "已暂停",
  HUMAN_REQUIRED: "需要人工处理",
  ARCHIVED: "已归档",
};

export const useWorkbenchStore = defineStore("workbench", () => {
  const detail = ref<ProjectDetail | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const pipelineEvents = ref<PipelineEvent[]>([]);
  const briefVersions = ref<BriefVersion[]>([]);
  const createdBanner = ref(false);
  const acting = ref(false);

  const project = computed(() => detail.value?.project ?? null);
  const chapters = computed(() => detail.value?.chapters ?? []);
  const editableDraft = computed(() => {
    const current = detail.value;
    if (!current) return false;
    return (
      current.project.status === "DRAFT" &&
      !current.project.confirmed &&
      current.chapters.length === 0
    );
  });

  const statusLabel = computed(() => {
    const status = project.value?.status;
    return status ? WORKBENCH_STATUS[status] || status : "等待创建";
  });

  const readyCount = computed(
    () =>
      chapters.value.filter((item) => ["READY", "SCHEDULED", "PUBLISHED"].includes(item.status))
        .length
  );

  const todayCount = computed(() => {
    const today = new Date().toISOString().slice(0, 10);
    return chapters.value.filter(
      (item) => item.created_at?.slice(0, 10) === today && item.status === "READY"
    ).length;
  });

  const healthLabel = computed(() =>
    chapters.value.some((item) => item.status === "FAILED") ? "需处理" : "正常"
  );
  const chapterFailures = computed(() => detail.value?.chapter_failures ?? []);
  const failedChapterOne = computed(() =>
    chapterFailures.value.find((item) => item.chapter_number === 1)
  );
  const generateLabel = computed(() =>
    failedChapterOne.value ? "重新生成第 1 章" : "生成下一章"
  );

  function setCreatedBanner(value: boolean) {
    createdBanner.value = value;
  }

  async function loadDetail(projectId: string) {
    loading.value = true;
    error.value = null;
    try {
      const payload = await getProjectDetail(projectId);
      detail.value = payload;
      if (payload.latest_events?.length) {
        pipelineEvents.value = payload.latest_events;
      }
      if (editableDraft.value) {
        await loadVersions(projectId);
      } else {
        briefVersions.value = [];
      }
    } catch (err) {
      if (isApiError(err) && err.kind === "aborted") return;
      error.value = toUserError(err, "加载工作台失败");
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function loadVersions(projectId: string) {
    try {
      const payload = await listBriefVersions(projectId);
      briefVersions.value = payload.items || [];
    } catch (err) {
      if (isApiError(err) && err.kind === "aborted") return;
      throw err;
    }
  }

  async function withAction<T>(fn: () => Promise<T>, successMessage?: string): Promise<T | undefined> {
    const app = useAppStore();
    acting.value = true;
    app.setBusy(true);
    try {
      const result = await fn();
      if (successMessage) app.flash(successMessage);
      return result;
    } catch (err) {
      if (isApiError(err) && err.kind === "aborted") return undefined;
      app.flash(toUserError(err), true);
      throw err;
    } finally {
      acting.value = false;
      app.setBusy(false);
    }
  }

  async function confirm(projectId: string) {
    await withAction(async () => {
      await confirmProject(projectId);
      await loadDetail(projectId);
      const projects = useProjectsStore();
      const summary = projects.items.find((item) => item.id === projectId);
      if (summary && project.value) {
        projects.upsertProject({
          ...summary,
          title: project.value.title,
          status: project.value.status,
          confirmed: project.value.confirmed,
          current_chapter: project.value.current_chapter,
          updated_at: project.value.updated_at,
        });
      } else {
        await projects.loadProjects().catch(() => undefined);
      }
    }, "创作方案已确认，智能体可以开始连载。");
  }

  async function togglePause(projectId: string) {
    const paused = project.value?.status === "PAUSED";
    await withAction(async () => {
      if (paused) await resumeProject(projectId);
      else await pauseProject(projectId);
      await loadDetail(projectId);
    }, paused ? "项目已恢复。" : "项目已暂停。");
  }

  async function recover(projectId: string) {
    await withAction(async () => {
      await recoverProject(projectId);
      await loadDetail(projectId);
    }, "已修复主角姓名数据，项目可以重新生成。");
  }

  async function generate(projectId: string) {
    await withAction(async () => {
      const payload = await generateNextChapter(projectId);
      const result = payload.items[0];
      pipelineEvents.value = (result.events as PipelineEvent[]) || [];
      const app = useAppStore();
      if (result.chapter.status === "READY") {
        app.flash(`${result.chapter.title} 已通过审核并进入 READY 储备。`);
      } else {
        app.flash(`${result.chapter.title} 暂未通过质量门槛，已保留草稿；可再次生成进行定向重写。`, true);
      }
      const projects = useProjectsStore();
      await projects.loadProjects();
      await loadDetail(projectId);
    });
  }

  async function rework(
    projectId: string,
    chapterNumber: number,
    feedback: string,
    mode = "auto"
  ) {
    await withAction(async () => {
      await reworkChapter(projectId, chapterNumber, feedback, mode);
      await loadDetail(projectId);
    }, feedback.trim() ? `第 ${chapterNumber} 章已打回重做，修改意见已记录。` : `第 ${chapterNumber} 章及后续章节已打回重做。`);
  }

  async function acceptWithWarnings(projectId: string, chapterNumber: number) {
    await withAction(async () => {
      const workspace = await getChapterWorkspace(projectId, chapterNumber);
      if (!workspace.capabilities?.accept_with_warnings) {
        throw new Error("当前章节仍有硬阻断，不能接受当前版本");
      }
      let draftHash = workspace.draft?.content_hash;
      let baseVersion = workspace.draft?.base_version ?? workspace.chapter.version;
      if (!draftHash) {
        const encoder = new TextEncoder();
        const title = (workspace.chapter.title || "").trim();
        const content = (workspace.chapter.content || "")
          .replace(/\r\n/g, "\n")
          .replace(/\r/g, "\n");
        const digest = await crypto.subtle.digest(
          "SHA-256",
          encoder.encode(`${title}\0${content}`)
        );
        draftHash = Array.from(new Uint8Array(digest))
          .map((byte) => byte.toString(16).padStart(2, "0"))
          .join("");
        baseVersion = workspace.chapter.version;
      }
      await acceptChapterWithWarnings(projectId, chapterNumber, {
        confirm: true,
        base_version: baseVersion,
        expected_draft_hash: draftHash,
      });
      await loadDetail(projectId);
    }, `第 ${chapterNumber} 章已接受当前版本并继续。`);
  }

  async function inspectOpeningRepair(projectId: string): Promise<OpeningRepairPreview | undefined> {
    return withAction(async () => previewOpeningRepair(projectId));
  }

  async function confirmOpeningRepair(
    projectId: string,
    expectedUpdatedAt: string
  ) {
    return withAction(async () => {
      const result = await applyOpeningRepair(projectId, {
        confirm: true,
        expected_project_updated_at: expectedUpdatedAt,
      });
      await loadDetail(projectId);
      return result as { snapshot_id?: string };
    }, "开篇数据已修复，可重新生成第 1 章");
  }

  async function undoOpeningRepair(projectId: string, snapshotId: string) {
    await withAction(async () => {
      await rollbackOpeningRepair(projectId, snapshotId);
      await loadDetail(projectId);
    }, "已回退开篇修复。");
  }

  async function saveBrief(projectId: string, brief: CreativeBrief) {
    await withAction(async () => {
      await updateBrief(projectId, brief);
      await loadDetail(projectId);
    }, "方案修改已保存为新版本。");
  }

  async function redoBrief(projectId: string, payload: { feedback: string; sections: string[] }) {
    const message = payload.sections.length
      ? "选中的方案模块已重做并保存为新版本。"
      : "已生成新的创作方案版本。";
    await withAction(async () => {
      await regenerateBrief(projectId, payload);
      await loadDetail(projectId);
    }, message);
  }

  async function restoreVersion(projectId: string, version: number) {
    await withAction(async () => {
      await restoreBrief(projectId, version);
      await loadDetail(projectId);
    }, `已恢复 v${version}，并保存为新的当前版本。`);
  }

  function reset() {
    abortProjectDetail();
    abortBriefVersions();
    detail.value = null;
    error.value = null;
    pipelineEvents.value = [];
    briefVersions.value = [];
    createdBanner.value = false;
  }

  return {
    detail,
    loading,
    error,
    pipelineEvents,
    briefVersions,
    createdBanner,
    acting,
    project,
    chapters,
    editableDraft,
    statusLabel,
    readyCount,
    todayCount,
    healthLabel,
    chapterFailures,
    generateLabel,
    setCreatedBanner,
    loadDetail,
    confirm,
    togglePause,
    recover,
    generate,
    rework,
    acceptWithWarnings,
    inspectOpeningRepair,
    confirmOpeningRepair,
    undoOpeningRepair,
    saveBrief,
    redoBrief,
    restoreVersion,
    reset,
  };
});
