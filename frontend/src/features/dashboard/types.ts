/**
 * Dashboard DTOs.
 *
 * `stage` is the department stage *key* (a free-form string) post-Phase-B —
 * not the legacy `PipelineStage` enum. Components must resolve display names
 * via the stage's `name_i18n` (see `useDepartmentStages`).
 */

export interface AwaitingItem {
  project_id: string;
  project_title: string;
  stage: string;
  cut_id: string;
  cut_version: number;
  uploaded_at: string;
  uploader_id: string | null;
}

export interface StageCount {
  stage: string;
  count: number;
}

export interface StuckProject {
  project_id: string;
  project_title: string;
  stage: string;
  owner_id: string;
  owner_name: string;
  last_activity_at: string | null;
  days_idle: number;
}

export interface ThroughputBucket {
  week_start: string;
  count: number;
}

export interface TimeInStage {
  stage: string;
  sample_size: number;
  avg_days: number | null;
  max_days: number | null;
}
