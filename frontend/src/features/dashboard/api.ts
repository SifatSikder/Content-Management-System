import { apiFetchAuthed } from "@/lib/api-client";

import type {
  AwaitingItem,
  StageCount,
  StuckProject,
  ThroughputBucket,
  TimeInStage,
} from "./types";

export function fetchAwaiting(): Promise<AwaitingItem[]> {
  return apiFetchAuthed<AwaitingItem[]>("/dashboard/awaiting");
}

export function fetchStages(): Promise<StageCount[]> {
  return apiFetchAuthed<StageCount[]>("/dashboard/stages");
}

export function fetchStuck(days = 5): Promise<StuckProject[]> {
  return apiFetchAuthed<StuckProject[]>(`/dashboard/stuck?days=${days}`);
}

export function fetchThroughput(weeks = 12): Promise<ThroughputBucket[]> {
  return apiFetchAuthed<ThroughputBucket[]>(`/dashboard/throughput?weeks=${weeks}`);
}

export function fetchTimeInStage(): Promise<TimeInStage[]> {
  return apiFetchAuthed<TimeInStage[]>("/dashboard/time-in-stage");
}
