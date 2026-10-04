import type {
  BriefVersion,
  CreativeBrief,
  ProjectDetail,
  ProjectRecord,
} from "@/api/contracts";
import type { OpeningRepairPreview } from "../types/workbench.types";
import { createCancellableGetter, requestJson } from "@/api/http-client";

const detailGetter = createCancellableGetter();
const versionsGetter = createCancellableGetter();

export async function getProjectDetail(id: string): Promise<ProjectDetail> {
  return detailGetter.run((signal) =>
    requestJson<ProjectDetail>(`/api/novels/${encodeURIComponent(id)}`, { signal })
  );
}

export function abortProjectDetail() {
  detailGetter.abort();
}

export async function confirmProject(id: string): Promise<ProjectRecord> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/confirm`, {
    method: "POST",
    body: {},
  });
}

export async function pauseProject(id: string): Promise<ProjectRecord> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/pause`, {
    method: "POST",
    body: {},
  });
}

export async function resumeProject(id: string): Promise<ProjectRecord> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/resume`, {
    method: "POST",
    body: {},
  });
}

export async function recoverProject(id: string): Promise<ProjectRecord> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/recover`, {
    method: "POST",
    body: {},
  });
}

export async function generateNextChapter(id: string) {
  return requestJson<{ items: Array<{ chapter: { title: string; status: string }; events: unknown[] }> }>(
    `/api/novels/${encodeURIComponent(id)}/runs`,
    { method: "POST", body: { count: 1 } }
  );
}

export async function reworkChapter(
  id: string,
  chapterNumber: number,
  feedback: string,
  mode = "auto"
) {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/chapters/${chapterNumber}/rework`, {
    method: "POST",
    body: { feedback, mode },
  });
}

export async function acceptChapterWithWarnings(
  id: string,
  chapterNumber: number,
  payload: { confirm: boolean; base_version: number; expected_draft_hash: string }
) {
  return requestJson(
    `/api/novels/${encodeURIComponent(id)}/chapters/${chapterNumber}/accept-with-warnings`,
    { method: "POST", body: payload }
  );
}

export async function getChapterWorkspace(id: string, chapterNumber: number) {
  return requestJson<{
    chapter: { version: number; content?: string | null; title?: string };
    draft: { content_hash: string; base_version: number } | null;
    capabilities?: { accept_with_warnings?: boolean };
  }>(`/api/novels/${encodeURIComponent(id)}/chapters/${chapterNumber}/workspace`);
}

export async function previewOpeningRepair(id: string) {
  return requestJson<OpeningRepairPreview>(
    `/api/novels/${encodeURIComponent(id)}/opening-repair-preview`
  );
}

export async function applyOpeningRepair(
  id: string,
  payload: { confirm: boolean; expected_project_updated_at: string }
) {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/opening-repair`, {
    method: "POST",
    body: payload,
  });
}

export async function rollbackOpeningRepair(id: string, snapshotId: string) {
  return requestJson(
    `/api/novels/${encodeURIComponent(id)}/opening-repair/${encodeURIComponent(snapshotId)}/rollback`,
    { method: "POST", body: {} }
  );
}

export async function rebuildCharacters(id: string) {
  return requestJson<{
    processed_chapters: number;
    character_count: number;
    removed_nonimportant?: number;
    failures?: unknown[];
  }>(`/api/novels/${encodeURIComponent(id)}/characters/rebuild`, {
    method: "POST",
    body: {},
  });
}

export async function updateBrief(id: string, brief: CreativeBrief) {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/brief`, {
    method: "PUT",
    body: brief,
  });
}

export async function regenerateBrief(id: string, payload: { feedback: string; sections: string[] }) {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/brief-regenerate`, {
    method: "POST",
    body: payload,
  });
}

export async function listBriefVersions(id: string): Promise<{ items: BriefVersion[] }> {
  return versionsGetter.run((signal) =>
    requestJson<{ items: BriefVersion[] }>(
      `/api/novels/${encodeURIComponent(id)}/brief-versions`,
      { signal }
    )
  );
}

export async function restoreBrief(id: string, version: number) {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/brief-restore`, {
    method: "POST",
    body: { version },
  });
}

export function abortBriefVersions() {
  versionsGetter.abort();
}
