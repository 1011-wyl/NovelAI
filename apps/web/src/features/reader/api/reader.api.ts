import type { ChapterRecord } from "@/api/contracts";
import { requestJson } from "@/api/http-client";

export type AssistantMode = "advisor" | "coauthor" | "editor";

export type QuickAction = "polish" | "shorten" | "expand" | "visualize" | "dialogue";

export type ChapterSelectionPayload = {
  start: number;
  end: number;
  text: string;
  chapter_version: number;
  draft_hash: string;
};

export type ChapterEditDraft = {
  chapter_id: string;
  project_id: string;
  base_version: number;
  title: string;
  content: string;
  source: string;
  applied_change_ids: string[];
  content_hash: string;
  created_at: string;
  updated_at: string;
};

export type ChapterVersionSnapshot = {
  version: number;
  kind: string;
  title: string | null;
  source: string;
  is_official: boolean;
  content?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type AssistantSession = {
  id: string;
  project_id: string;
  chapter_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
};

export type AssistantMessage = {
  id: string;
  session_id: string;
  sequence: number;
  role: "user" | "assistant";
  mode: AssistantMode | string;
  content: string;
  selection?: { start: number; end: number; text: string } | null;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export type DiffLine = {
  type: "added" | "removed" | "context" | string;
  text: string;
};

export type DiffSection = {
  lines?: DiffLine[];
};

export type AssistantChangeSet = {
  id: string;
  session_id: string;
  message_id: string;
  chapter_id: string;
  operation: string;
  base_version: number;
  base_draft_hash: string;
  before_title: string;
  before_content: string;
  after_title: string;
  after_content: string;
  diff_json: { sections?: DiffSection[] };
  explanation: string;
  status: string;
  created_at: string;
  decided_at?: string | null;
  reverted_at?: string | null;
};

export type DownstreamInfo = {
  count: number;
  first_number: number | null;
  last_number: number | null;
};

export type ChapterWorkspace = {
  project: { id: string; title: string; status: string };
  chapter: ChapterRecord;
  draft: ChapterEditDraft | null;
  editable: boolean;
  capabilities?: {
    edit_draft: boolean;
    use_assistant: boolean;
    commit_revision: boolean;
    submit_for_review: boolean;
    replan: boolean;
    accept_with_warnings?: boolean;
  };
  read_only_reason: string | null;
  downstream: DownstreamInfo;
  versions: ChapterVersionSnapshot[];
  sessions: AssistantSession[];
};

export type SaveDraftPayload = {
  base_version: number;
  title: string;
  content: string;
  expected_draft_hash: string | null;
};

export type SendAssistantPayload = {
  content: string;
  mode: AssistantMode | string;
  quick_action?: QuickAction | null;
  selection?: ChapterSelectionPayload | null;
};

export type SendAssistantResult = {
  user_message: AssistantMessage;
  assistant_message: AssistantMessage;
  change_set: AssistantChangeSet | null;
};

export type ApproveChangeResult = {
  change_set: AssistantChangeSet;
  draft: ChapterEditDraft;
};

export type CommitRevisionResult = {
  chapter: ChapterRecord;
  reset_chapters: number[];
  memory_changes?: Record<string, unknown>;
  warnings?: string[];
  semantic_index_status?: string;
};

export function getChapterWorkspace(projectId: string, chapterNumber: number) {
  return requestJson<ChapterWorkspace>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/workspace`
  );
}

export function saveEditDraft(projectId: string, chapterNumber: number, payload: SaveDraftPayload) {
  return requestJson<ChapterEditDraft>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/edit-draft`,
    { method: "PUT", body: payload }
  );
}

export function discardEditDraft(projectId: string, chapterNumber: number) {
  return requestJson<null>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/edit-draft`,
    { method: "DELETE", body: {} }
  );
}

export function commitRevision(
  projectId: string,
  chapterNumber: number,
  payload: { base_version: number; expected_draft_hash: string }
) {
  return requestJson<CommitRevisionResult>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/revisions`,
    { method: "POST", body: payload }
  );
}

export function submitFailedReview(
  projectId: string,
  chapterNumber: number,
  payload: { base_version: number; expected_draft_hash: string }
) {
  return requestJson<{ passed: boolean; message?: string; chapter?: ChapterRecord }>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/review-submit`,
    { method: "POST", body: payload }
  );
}

export function acceptWithWarnings(
  projectId: string,
  chapterNumber: number,
  payload: { confirm: boolean; base_version: number; expected_draft_hash: string }
) {
  return requestJson<{
    passed: boolean;
    accepted_with_warnings?: boolean;
    message?: string;
    chapter?: ChapterRecord;
  }>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/accept-with-warnings`,
    { method: "POST", body: payload }
  );
}

export function restoreVersion(projectId: string, chapterNumber: number, version: number) {
  return requestJson<ChapterEditDraft>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/versions/${version}/restore`,
    { method: "POST", body: {} }
  );
}

export function createAssistantSession(projectId: string, chapterNumber: number) {
  return requestJson<AssistantSession>(
    `/api/novels/${encodeURIComponent(projectId)}/chapters/${chapterNumber}/assistant/sessions`,
    { method: "POST", body: {} }
  );
}

export function listAssistantMessages(sessionId: string) {
  return requestJson<{ items: AssistantMessage[] }>(
    `/api/assistant/sessions/${encodeURIComponent(sessionId)}/messages`
  );
}

export function listAssistantChanges(sessionId: string) {
  return requestJson<{ items: AssistantChangeSet[] }>(
    `/api/assistant/sessions/${encodeURIComponent(sessionId)}/changes`
  );
}

export function sendAssistantMessage(sessionId: string, payload: SendAssistantPayload) {
  return requestJson<SendAssistantResult>(
    `/api/assistant/sessions/${encodeURIComponent(sessionId)}/messages`,
    { method: "POST", body: payload }
  );
}

export function approveChange(changeId: string) {
  return requestJson<ApproveChangeResult>(
    `/api/assistant/changes/${encodeURIComponent(changeId)}/approve`,
    { method: "POST", body: {} }
  );
}

export function rejectChange(changeId: string) {
  return requestJson<AssistantChangeSet>(
    `/api/assistant/changes/${encodeURIComponent(changeId)}/reject`,
    { method: "POST", body: {} }
  );
}

export function rollbackSession(
  sessionId: string,
  payload: { to_message_id: string; expected_draft_hash: string }
) {
  return requestJson<ChapterEditDraft>(
    `/api/assistant/sessions/${encodeURIComponent(sessionId)}/rollback`,
    { method: "POST", body: payload }
  );
}
