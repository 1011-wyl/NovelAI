export type { CreateFormState } from "./schema";

export const TAG_LIMITS = {
  experiences: 8,
  elements: 12,
  protagonist_tags: 8,
} as const;

export type TagGroup = keyof typeof TAG_LIMITS;
