import { requestJson } from "@/api/http-client";
import type { OpeningRepairPreview } from "../types/workbench.types";

export type OpeningRepairApplyResult = {
  snapshot_id: string;
  next_action?: string;
  preview?: OpeningRepairPreview;
};

export type LatestOpeningRepairSnapshot = {
  id: string;
  status: string;
  created_at: string;
  applied_at?: string | null;
  rollback_allowed: boolean;
  blocked_reason?: string | null;
};

export async function previewOpeningRepair(id: string): Promise<OpeningRepairPreview> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/opening-repair-preview`);
}

export async function applyOpeningRepair(
  id: string,
  payload: { confirm: boolean; expected_project_updated_at: string }
): Promise<OpeningRepairApplyResult> {
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

export async function getLatestOpeningRepairSnapshot(
  id: string
): Promise<{ snapshot: LatestOpeningRepairSnapshot | null }> {
  return requestJson(`/api/novels/${encodeURIComponent(id)}/opening-repair-snapshots/latest`);
}
