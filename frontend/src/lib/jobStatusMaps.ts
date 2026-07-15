/**
 * Exhaustive JobStatus UI maps — TypeScript fails the build if a status is missing.
 * Keep in sync with frontend/src/lib/types.ts JobStatus.
 */

import type { JobStatus } from "@/lib/types";

export type StatusTone = "neutral" | "info" | "warning" | "danger" | "success";

export const JOB_STATUS_TONE: Record<JobStatus, StatusTone> = {
  pending: "neutral",
  running: "info",
  paused: "warning",
  partial: "warning",
  failed: "danger",
  canceled: "neutral",
  completed: "success",
};

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  pending: "Pending",
  running: "Running",
  paused: "Paused",
  partial: "Stopped early",
  failed: "Failed",
  canceled: "Canceled",
  completed: "Completed",
};

export const JOB_TERMINAL_STATUSES: ReadonlySet<JobStatus> = new Set([
  "completed",
  "failed",
  "partial",
  "canceled",
  // Treat paused as terminal in the UI until cooperative cancel/resume exists.
  "paused",
]);
