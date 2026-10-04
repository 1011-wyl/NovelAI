export type { ChapterFailure } from "@/api/contracts";

export type OpeningRepairPreview = {
  eligible: boolean;
  reasons: string[];
  project_updated_at: string;
  detected_problems: string[];
  opening_anchor: Record<string, unknown>;
  character_changes: Array<{
    name: string;
    from_relationships?: Record<string, string>;
    to_relationships?: Record<string, string>;
    moved_to_future?: boolean;
  }>;
  chapter_changes: Array<Record<string, unknown>>;
  preserved_artifacts: string[];
};
