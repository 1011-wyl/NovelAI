import { z } from "zod";
import type { NovelCreatePayload } from "@/api/contracts";

export const DRAFT_STORAGE_KEY = "novelAgentCreateDraft";

export type CreateFormState = {
  audience_channel: "男频" | "女频";
  genre: string;
  preferred_title: string;
  idea: string;
  experiences: string[];
  elements: string[];
  protagonist_tags: string[];
  romance: string;
  must_have: string;
  nice_to_have: string;
  exclude: string;
  chapter_target_chars: number;
  daily_chapters: number;
  reserve_target: number;
  require_plan_confirmation: boolean;
  showAdvanced: boolean;
};

export const defaultCreateForm = (): CreateFormState => ({
  audience_channel: "男频",
  genre: "",
  preferred_title: "",
  idea: "",
  experiences: [],
  elements: [],
  protagonist_tags: [],
  romance: "",
  must_have: "",
  nice_to_have: "",
  exclude: "",
  chapter_target_chars: 2200,
  daily_chapters: 2,
  reserve_target: 5,
  require_plan_confirmation: true,
  showAdvanced: false,
});

const titleSchema = z
  .string()
  .trim()
  .max(80, "书名最多 80 字")
  .optional()
  .or(z.literal(""));

export const step1Schema = z.object({
  audience_channel: z.enum(["男频", "女频"]),
  genre: z.string().trim().min(1, "请选择题材"),
  preferred_title: titleSchema,
  idea: z
    .string()
    .trim()
    .min(1, "请填写核心想法")
    .max(2000, "核心想法最多 2000 字"),
});

export const step2Schema = z.object({
  experiences: z.array(z.string()).max(8, "阅读体验最多选择 8 个"),
  elements: z.array(z.string()).max(12, "核心元素最多选择 12 个"),
  protagonist_tags: z.array(z.string()).max(8, "主角设定最多选择 8 个"),
  romance: z.string().optional(),
});

export const step3Schema = z.object({
  must_have: z.string().optional(),
  nice_to_have: z.string().optional(),
  exclude: z.string().optional(),
  chapter_target_chars: z
    .number({ invalid_type_error: "单章字数须为数字" })
    .min(800, "单章字数不少于 800")
    .max(8000, "单章字数不超过 8000"),
  daily_chapters: z
    .number({ invalid_type_error: "每日章节须为数字" })
    .min(1, "每日章节至少 1")
    .max(20, "每日章节不超过 20"),
  reserve_target: z
    .number({ invalid_type_error: "储备安全线须为数字" })
    .min(1, "储备安全线至少 1")
    .max(50, "储备安全线不超过 50"),
  require_plan_confirmation: z.boolean(),
});

export type FieldErrors = Record<string, string>;

export function zodErrorsToMap(error: z.ZodError): FieldErrors {
  const map: FieldErrors = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    if (!map[key]) map[key] = issue.message;
  }
  return map;
}

export function splitCsv(value: string): string[] {
  return String(value || "")
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.indexOf(item) === index);
}

export function toCreatePayload(form: CreateFormState): NovelCreatePayload {
  const preferred = form.preferred_title.trim();
  const romance = form.romance.trim();
  return {
    preferred_title: preferred ? preferred : null,
    audience_channel: form.audience_channel,
    genre: form.genre.trim(),
    experiences: [...form.experiences],
    elements: [...form.elements],
    protagonist_tags: [...form.protagonist_tags],
    romance: !romance || romance === "自动推导" ? null : romance,
    idea: form.idea.trim(),
    must_have: splitCsv(form.must_have),
    nice_to_have: splitCsv(form.nice_to_have),
    exclude: splitCsv(form.exclude),
    chapter_target_chars: form.chapter_target_chars,
    daily_chapters: form.daily_chapters,
    reserve_target: form.reserve_target,
    require_plan_confirmation: true,
  };
}

export function validateStep(step: number, form: CreateFormState): FieldErrors {
  const schema = step === 1 ? step1Schema : step === 2 ? step2Schema : step3Schema;
  const result = schema.safeParse(form);
  if (result.success) return {};
  return zodErrorsToMap(result.error);
}

export function formHasContent(form: CreateFormState): boolean {
  const blank = defaultCreateForm();
  return (
    form.idea.trim() !== "" ||
    form.preferred_title.trim() !== "" ||
    form.genre !== blank.genre ||
    form.experiences.length > 0 ||
    form.elements.length > 0 ||
    form.protagonist_tags.length > 0 ||
    form.must_have.trim() !== "" ||
    form.nice_to_have.trim() !== "" ||
    form.exclude.trim() !== "" ||
    form.audience_channel !== blank.audience_channel
  );
}
