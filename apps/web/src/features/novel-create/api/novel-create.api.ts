import type { NovelCreatePayload, ProjectRecord, TagCatalog } from "@/api/contracts";
import { createCancellableGetter, requestJson } from "@/api/http-client";

const tagsGetter = createCancellableGetter();

export async function fetchTagCatalog(): Promise<TagCatalog> {
  return tagsGetter.run((signal) => requestJson<TagCatalog>("/api/tags", { signal }));
}

export async function createNovel(
  payload: NovelCreatePayload,
  signal?: AbortSignal
): Promise<ProjectRecord> {
  return requestJson<ProjectRecord>("/api/novels", {
    method: "POST",
    body: payload,
    signal,
  });
}

export function abortTagCatalog() {
  tagsGetter.abort();
}
