import type { ProjectListResponse, ProjectSummary } from "@/api/contracts";
import { createCancellableGetter, requestJson } from "@/api/http-client";

const listGetter = createCancellableGetter();

export async function listNovels(): Promise<ProjectListResponse> {
  return listGetter.run((signal) =>
    requestJson<ProjectListResponse>("/api/novels", { signal })
  );
}

export async function renameNovel(id: string, title: string): Promise<ProjectSummary> {
  return requestJson<ProjectSummary>(`/api/novels/${encodeURIComponent(id)}/metadata`, {
    method: "PUT",
    body: { title },
  });
}

export async function deleteNovel(id: string, confirmationTitle?: string): Promise<void> {
  await requestJson(`/api/novels/${encodeURIComponent(id)}`, {
    method: "DELETE",
    body: { confirmation_title: confirmationTitle ?? null },
  });
}

export function abortLibraryList() {
  listGetter.abort();
}
