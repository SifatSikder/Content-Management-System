import type { PipelineStage } from "@/lib/enums";

export interface AwaitingItem {
  project_id: string;
  project_title: string;
  stage: PipelineStage;
  cut_id: string;
  cut_version: number;
  uploaded_at: string;
  uploader_id: string | null;
}

export interface StageCount {
  stage: PipelineStage;
  count: number;
}

export interface StuckProject {
  project_id: string;
  project_title: string;
  stage: PipelineStage;
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
  stage: PipelineStage;
  sample_size: number;
  avg_days: number | null;
  max_days: number | null;
}
