import type { JobStatus, Course } from "@/lib/types";
import { JOB_TERMINAL_STATUSES } from "@/lib/jobStatusMaps";

export type CourseDisplayStatus = "draft" | "generating" | "ready" | "stopped";

export const COURSE_DISPLAY_STATUS_LABEL: Record<CourseDisplayStatus, string> = {
  draft: "Draft",
  generating: "Generating",
  ready: "DOCX ready",
  stopped: "Stopped early",
};

export const COURSE_DISPLAY_STATUS_TONE: Record<
  CourseDisplayStatus,
  "neutral" | "info" | "success" | "warning"
> = {
  draft: "neutral",
  generating: "info",
  ready: "success",
  stopped: "warning",
};

/** Derive a user-facing course status from versions + latest job (not raw DB `course.status`). */
export function deriveCourseDisplayStatus(
  hasVersions: boolean,
  latestJobStatus: string | null,
): CourseDisplayStatus {
  if (latestJobStatus && !JOB_TERMINAL_STATUSES.has(latestJobStatus as JobStatus)) {
    return "generating";
  }
  if (hasVersions) return "ready";
  if (latestJobStatus === "partial" || latestJobStatus === "failed" || latestJobStatus === "canceled") {
    return "stopped";
  }
  return "draft";
}

export type CourseWithDisplayStatus = Course & { displayStatus: CourseDisplayStatus };
