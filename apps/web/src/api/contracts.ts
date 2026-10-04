export type ProjectStatus =
  | "DRAFT"
  | "ACTIVE"
  | "PAUSED"
  | "HUMAN_REQUIRED"
  | "ARCHIVED";

export type ProjectSummary = {
  id: string;
  title: string;
  status: ProjectStatus;
  confirmed: boolean;
  audience_channel: string;
  genre: string;
  chapter_count: number;
  content_chars: number;
  current_chapter: number;
  created_at: string;
  updated_at: string;
};

export type ProjectListResponse = {
  items: ProjectSummary[];
};

export type NovelCreatePayload = {
  preferred_title: string | null;
  audience_channel: string;
  genre: string;
  experiences: string[];
  elements: string[];
  protagonist_tags: string[];
  romance: string | null;
  idea: string;
  must_have: string[];
  nice_to_have: string[];
  exclude: string[];
  chapter_target_chars: number;
  daily_chapters: number;
  reserve_target: number;
  require_plan_confirmation: boolean;
};

export type ChannelTags = {
  genres: string[];
  experiences: string[];
  elements: string[];
  protagonist_tags: string[];
  romance: string[];
};

export type TagCatalog = {
  default_channel: string;
  channels: Record<string, ChannelTags>;
  note?: string;
  references?: Array<{ name: string; url: string }>;
};

export type CreativeBrief = {
  selected_title: string;
  title_candidates: string[];
  synopsis: string;
  target_readers: string;
  selling_points: string[];
  protagonist: string;
  protagonist_name?: string;
  protagonist_profile: string;
  main_conflict: string;
  reader_contract: string;
  core_expectation: string;
  world_rules: string[];
  total_chapters: number;
  volume_count: number;
  opening_three_chapters: string[];
  opening_chapter_anchors?: Array<{
    number: 1 | 2 | 3;
    title: string;
    core_event: string;
    must_establish?: string[];
    forbidden_assumptions?: string[];
    ending_direction?: string;
  }>;
  update_plan: string;
  style_guide: string[];
  character_profiles?: unknown[];
  [key: string]: unknown;
};

export type ProjectRecord = {
  id: string;
  title: string;
  status: ProjectStatus;
  confirmed: boolean;
  request: NovelCreatePayload;
  brief: CreativeBrief;
  current_chapter: number;
  created_at: string;
  updated_at: string;
};

export type ChapterRecord = {
  id: string;
  number: number;
  title: string;
  summary: string;
  status: string;
  version: number;
  content?: string;
  created_at: string;
  [key: string]: unknown;
};

export type PipelineEvent = {
  node: string;
  message: string;
  progress: number;
};

export type CharacterRecord = {
  id: string;
  name: string;
  role: string;
  version?: number;
  immutable_facts?: string[];
  current_state?: Record<string, unknown>;
  [key: string]: unknown;
};

export type WorldFact = {
  category: string;
  statement: string;
  locked?: boolean;
  [key: string]: unknown;
};

export type TimelineItem = {
  chapter_number: number;
  event: string;
  [key: string]: unknown;
};

export type ResearchSource = {
  title?: string;
  domain?: string;
  excerpt?: string;
  url?: string;
  verified?: boolean;
  reliability?: number;
  [key: string]: unknown;
};

export type ProjectDetail = {
  project: ProjectRecord;
  chapters: ChapterRecord[];
  latest_events: PipelineEvent[];
  characters: CharacterRecord[];
  world_facts: WorldFact[];
  timeline: TimelineItem[];
  research_sources: ResearchSource[];
  semantic_document_count: number;
  reserve_count: number;
  chapter_failures?: ChapterFailure[];
  skills?: Record<string, unknown>;
};

export type ChapterFailure = {
  chapter_number: number;
  error_code?: string | null;
  node?: string | null;
  decision?: string | null;
  score?: number | null;
  issues?: Array<{ category?: string; severity?: string; message?: string }>;
  reviewed_at?: string | null;
  recommended_rework_mode?: "reuse_plan" | "replan" | "auto" | string;
  opening_repair_eligible?: boolean;
  can_accept_with_warnings?: boolean;
  lowest_component?: string | null;
  score_trace?: number[];
  review_attempt?: number;
  max_review_attempts?: number;
  revision_count?: number;
  quality_status?: string | null;
  preflight_only?: boolean;
  pass_score_exclusive?: number;
  selected_score?: number | null;
  best_attempt_index?: number;
  actual_length?: number;
  target_length?: number;
  accepted_length_min?: number;
  accepted_length_max?: number;
  length_repair_count?: number;
};

export type BriefVersion = {
  version: number;
  source: string;
  feedback?: string | null;
  brief: CreativeBrief;
  created_at?: string;
};

export type HealthPayload = {
  mode?: string;
  apis?: Record<string, { enabled?: boolean; configured?: boolean; provider?: string; model?: string }>;
  [key: string]: unknown;
};

export type SettingsPayload = {
  preferences: {
    daily_chapters: number;
    reserve_target: number;
    budget_limit: number;
    debug_mode: boolean;
    [key: string]: unknown;
  };
  runtime?: Record<string, { enabled?: boolean; configured?: boolean; provider?: string; model?: string }>;
};
