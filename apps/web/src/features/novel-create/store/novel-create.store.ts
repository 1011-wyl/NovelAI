import { computed, reactive, ref, watch } from "vue";
import { defineStore } from "pinia";
import type { TagCatalog } from "@/api/contracts";
import { ApiError, isApiError } from "@/api/api-error";
import { createNovel, fetchTagCatalog } from "@/features/novel-create/api/novel-create.api";
import {
  DRAFT_STORAGE_KEY,
  defaultCreateForm,
  formHasContent,
  toCreatePayload,
  validateStep,
  type CreateFormState,
  type FieldErrors,
} from "@/features/novel-create/schema";
import { TAG_LIMITS, type TagGroup } from "@/features/novel-create/types";
import { useProjectsStore } from "@/stores/projects.store";

function readDraft(): CreateFormState | null {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return null;
    return { ...defaultCreateForm(), ...(JSON.parse(raw) as Partial<CreateFormState>) };
  } catch {
    return null;
  }
}

function writeDraft(form: CreateFormState) {
  try {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(form));
  } catch {
    /* ignore */
  }
}

function clearDraftStorage() {
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export const useNovelCreateStore = defineStore("novel-create", () => {
  const step = ref(1);
  const form = reactive<CreateFormState>(readDraft() ?? defaultCreateForm());
  const fieldErrors = ref<FieldErrors>({});
  const formErrorMessages = ref<string[]>([]);
  const catalog = ref<TagCatalog | null>(null);
  const catalogLoading = ref(false);
  const catalogError = ref<string | null>(null);
  const channelWarning = ref<string | null>(null);
  const submitting = ref(false);
  const submitError = ref<string | null>(null);
  let submitController: AbortController | null = null;

  const channelTags = computed(() => catalog.value?.channels?.[form.audience_channel] ?? null);

  watch(
    form,
    (value) => {
      writeDraft(value);
    },
    { deep: true }
  );

  async function loadCatalog() {
    catalogLoading.value = true;
    catalogError.value = null;
    try {
      catalog.value = await fetchTagCatalog();
      ensureGenreDefault();
    } catch (error) {
      if (isApiError(error) && error.kind === "aborted") return;
      catalogError.value = error instanceof Error ? error.message : "标签加载失败";
    } finally {
      catalogLoading.value = false;
    }
  }

  function ensureGenreDefault() {
    const tags = channelTags.value;
    if (!tags?.genres?.length) return;
    if (!form.genre || !tags.genres.includes(form.genre)) {
      form.genre = tags.genres[0];
    }
  }

  function setChannel(channel: "男频" | "女频") {
    if (form.audience_channel === channel) return;
    form.audience_channel = channel;
    const tags = catalog.value?.channels?.[channel];
    if (!tags) return;
    const removed: string[] = [];
    (["experiences", "elements", "protagonist_tags"] as TagGroup[]).forEach((group) => {
      const allowed = new Set(tags[group] || []);
      const next = form[group].filter((item) => {
        const ok = allowed.has(item);
        if (!ok) removed.push(item);
        return ok;
      });
      form[group] = next;
    });
    if (form.romance && !(tags.romance || []).includes(form.romance)) {
      removed.push(form.romance);
      form.romance = "";
    }
    ensureGenreDefault();
    channelWarning.value = removed.length
      ? `已切换到${channel}，并移除不适用的标签：${removed.join("、")}`
      : null;
  }

  function toggleTag(group: TagGroup, value: string) {
    const list = form[group];
    const index = list.indexOf(value);
    if (index >= 0) {
      list.splice(index, 1);
      delete fieldErrors.value[group];
      return;
    }
    if (list.length >= TAG_LIMITS[group]) {
      fieldErrors.value = {
        ...fieldErrors.value,
        [group]: `最多选择 ${TAG_LIMITS[group]} 个`,
      };
      return;
    }
    list.push(value);
    delete fieldErrors.value[group];
  }

  function validateCurrentStep(): boolean {
    const errors = validateStep(step.value, form);
    fieldErrors.value = errors;
    formErrorMessages.value = Object.values(errors);
    return Object.keys(errors).length === 0;
  }

  function nextStep() {
    if (!validateCurrentStep()) return false;
    if (step.value < 3) step.value += 1;
    return true;
  }

  function prevStep() {
    if (step.value > 1) step.value -= 1;
    formErrorMessages.value = [];
  }

  function goStep(target: number) {
    if (target < 1 || target > 3) return;
    if (target > step.value && !validateCurrentStep()) return;
    step.value = target;
  }

  function blurValidate(field: string) {
    const errors = validateStep(step.value, form);
    if (errors[field]) {
      fieldErrors.value = { ...fieldErrors.value, [field]: errors[field] };
    } else {
      const next = { ...fieldErrors.value };
      delete next[field];
      fieldErrors.value = next;
    }
  }

  function mapServerErrors(error: ApiError) {
    const messages: string[] = [error.message];
    const details = error.details;
    const nextErrors: FieldErrors = { ...fieldErrors.value };
    if (Array.isArray(details)) {
      for (const item of details) {
        if (!item || typeof item !== "object") continue;
        const loc = (item as { loc?: unknown }).loc;
        const msg = String((item as { msg?: unknown }).msg || "");
        if (Array.isArray(loc) && loc.length) {
          const field = String(loc[loc.length - 1]);
          if (msg) nextErrors[field] = msg;
          if (["audience_channel", "genre", "preferred_title", "idea"].includes(field)) {
            step.value = 1;
          } else if (
            ["experiences", "elements", "protagonist_tags", "romance"].includes(field)
          ) {
            step.value = 2;
          } else {
            step.value = 3;
          }
        }
        if (msg) messages.push(msg);
      }
    }
    fieldErrors.value = nextErrors;
    formErrorMessages.value = [...new Set(messages)];
  }

  async function submit() {
    if (submitting.value) return null;
    if (!validateCurrentStep()) return null;
    submitting.value = true;
    submitError.value = null;
    formErrorMessages.value = [];
    submitController = new AbortController();
    const payload = toCreatePayload(form);
    try {
      const project = await createNovel(payload, submitController.signal);
      const projects = useProjectsStore();
      projects.selectProject(project.id);
      projects.upsertProject({
        id: project.id,
        title: project.title,
        status: project.status,
        confirmed: project.confirmed,
        audience_channel: project.request?.audience_channel || form.audience_channel,
        genre: project.request?.genre || form.genre,
        chapter_count: 0,
        content_chars: 0,
        current_chapter: project.current_chapter,
        created_at: project.created_at,
        updated_at: project.updated_at,
      });
      clearDraftStorage();
      Object.assign(form, defaultCreateForm());
      step.value = 1;
      return project;
    } catch (error) {
      if (isApiError(error) && error.kind === "aborted") return null;
      if (isApiError(error)) {
        mapServerErrors(error);
        submitError.value = error.message;
      } else {
        submitError.value = error instanceof Error ? error.message : "创建失败";
        formErrorMessages.value = [submitError.value];
      }
      return null;
    } finally {
      submitting.value = false;
      submitController = null;
    }
  }

  function reset() {
    Object.assign(form, defaultCreateForm());
    step.value = 1;
    fieldErrors.value = {};
    formErrorMessages.value = [];
    channelWarning.value = null;
    clearDraftStorage();
  }

  function abandonIfNeeded(): boolean {
    if (!formHasContent(form)) {
      reset();
      return true;
    }
    const ok = window.confirm("表单中有未提交内容，确定放弃并返回书架吗？");
    if (ok) reset();
    return ok;
  }

  return {
    step,
    form,
    fieldErrors,
    formErrorMessages,
    catalog,
    catalogLoading,
    catalogError,
    channelTags,
    channelWarning,
    submitting,
    submitError,
    loadCatalog,
    setChannel,
    toggleTag,
    nextStep,
    prevStep,
    goStep,
    blurValidate,
    submit,
    reset,
    abandonIfNeeded,
    toCreatePayload: () => toCreatePayload(form),
  };
});
