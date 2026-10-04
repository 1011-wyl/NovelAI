import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { isApiError } from "@/api/api-error";
import { toUserError } from "@/stores/projects.store";
import { useAppStore } from "@/stores/app.store";
import {
  applyOpeningRepair,
  getLatestOpeningRepairSnapshot,
  previewOpeningRepair,
  rollbackOpeningRepair,
  type LatestOpeningRepairSnapshot,
} from "../api/opening-repair.api";
import type { OpeningRepairPreview } from "../types/workbench.types";

export const useOpeningRepairStore = defineStore("opening-repair", () => {
  const latest = ref<LatestOpeningRepairSnapshot | null>(null);
  const loaded = ref(false);
  const loadError = ref<string | null>(null);
  const preview = ref<OpeningRepairPreview | null>(null);

  const canRollback = computed(
    () => Boolean(latest.value?.id) && latest.value?.rollback_allowed === true && !loadError.value
  );

  async function loadLatest(projectId: string) {
    loadError.value = null;
    loaded.value = false;
    latest.value = null;
    try {
      const payload = await getLatestOpeningRepairSnapshot(projectId);
      latest.value = payload.snapshot;
      loaded.value = true;
    } catch (err) {
      if (isApiError(err) && err.kind === "aborted") return;
      loadError.value = toUserError(err, "无法查询开篇修复快照");
      latest.value = null;
      loaded.value = true;
    }
  }

  async function inspect(projectId: string) {
    preview.value = await previewOpeningRepair(projectId);
    return preview.value;
  }

  async function apply(projectId: string, expectedUpdatedAt: string) {
    const result = await applyOpeningRepair(projectId, {
      confirm: true,
      expected_project_updated_at: expectedUpdatedAt,
    });
    await loadLatest(projectId);
    return result;
  }

  async function undo(projectId: string) {
    if (!latest.value?.id || !latest.value.rollback_allowed) {
      throw new Error(latest.value?.blocked_reason || "当前不能回退开篇修复");
    }
    const app = useAppStore();
    await rollbackOpeningRepair(projectId, latest.value.id);
    latest.value = null;
    app.flash("已回退开篇修复。");
    await loadLatest(projectId);
  }

  function reset() {
    latest.value = null;
    loaded.value = false;
    loadError.value = null;
    preview.value = null;
  }

  return {
    latest,
    loaded,
    loadError,
    preview,
    canRollback,
    loadLatest,
    inspect,
    apply,
    undo,
    reset,
  };
});
