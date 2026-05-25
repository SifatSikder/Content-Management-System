import { apiFetchAuthed } from "@/lib/api-client";

import type {
  AwaitingItem,
  StageCount,
  StuckProject,
  ThroughputBucket,
  TimeInStage,
} from "./types";

/**
 * Every dashboard endpoint takes a `department_id` (Phase B) — caller resolves
 * it from `useCurrentDepartment()` before invoking.
 */

export function fetchAwaiting(departmentId: string): Promise<AwaitingItem[]> {
  return apiFetchAuthed<AwaitingItem[]>(
    `/dashboard/awaiting?department_id=${encodeURIComponent(departmentId)}`,
  );
}

export function fetchStages(departmentId: string): Promise<StageCount[]> {
  return apiFetchAuthed<StageCount[]>(
    `/dashboard/stages?department_id=${encodeURIComponent(departmentId)}`,
  );
}

export function fetchStuck(departmentId: string, days = 5): Promise<StuckProject[]> {
  return apiFetchAuthed<StuckProject[]>(
    `/dashboard/stuck?department_id=${encodeURIComponent(departmentId)}&days=${days}`,
  );
}

export function fetchThroughput(
  departmentId: string,
  weeks = 12,
): Promise<ThroughputBucket[]> {
  return apiFetchAuthed<ThroughputBucket[]>(
    `/dashboard/throughput?department_id=${encodeURIComponent(departmentId)}&weeks=${weeks}`,
  );
}

export function fetchTimeInStage(departmentId: string): Promise<TimeInStage[]> {
  return apiFetchAuthed<TimeInStage[]>(
    `/dashboard/time-in-stage?department_id=${encodeURIComponent(departmentId)}`,
  );
}
