"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ExplanationLevel, GenerationJob } from "@/lib/types";
import StatusBadge, { type StatusTone } from "@/components/ui/StatusBadge";

// "partial" is a resting state awaiting user action (download the partial
// DOCX, or start over) - not actively progressing, so polling stops here
// too, same as completed/failed.
const TERMINAL_STATUSES = new Set<GenerationJob["status"]>(["completed", "failed", "partial"]);

// High-level progress only - never a reel, never internal JSON, never a
// long report by default. Maps the backend's internal stage tokens (see
// backend/app/generation/orchestrator.py) to what the user should see.
const STAGE_LABELS: Record<string, string> = {
  queued: "Preparing course",
  reading_sources: "Reading sources",
  building_map: "Building course map",
  generating: "Writing course internally",
  reviewing_repetition: "Reviewing repetition",
  reviewing: "Final rebuild",
  exporting: "Exporting DOCX",
  done: "Done",
  failed: "Failed",
  partial: "Stopped early",
};

// The ordered "happy path" of stages, used only for the step indicator
// below - a small, simplified view of STAGE_LABELS above. "queued" isn't
// its own step (it's the "nothing started yet" state before step 1), and
// "done"/"failed"/"partial" are end states shown via the status badge
// instead of as a step.
const PROGRESS_STEPS: { key: string; label: string }[] = [
  { key: "reading_sources", label: "Reading sources" },
  { key: "building_map", label: "Building map" },
  { key: "generating", label: "Generating" },
  { key: "reviewing_repetition", label: "Reviewing repetition" },
  { key: "reviewing", label: "Final rebuild" },
  { key: "exporting", label: "Exporting" },
];

// Short, jargon-free labels for the backend's error categories (see
// backend/app/generation/errors.py) - shown alongside error_message.
const ERROR_CATEGORY_LABELS: Record<string, string> = {
  rate_limit: "Rate limited",
  insufficient_quota: "Out of credits",
  timeout: "Timed out",
  provider_unavailable: "Provider unavailable",
  malformed_response: "Unusable response",
  context_too_long: "Content too long",
  unknown: "Unexpected error",
};

const STATUS_TONE: Record<GenerationJob["status"], StatusTone> = {
  pending: "neutral",
  running: "info",
  partial: "warning",
  failed: "danger",
  completed: "success",
};

/** Simple filled-circle/checkmark step row - no icon library, just text+dots. */
function ProgressSteps({ job }: { job: GenerationJob }) {
  const isDone = job.status === "completed" || job.current_stage === "done";
  const currentIndex = job.current_stage
    ? PROGRESS_STEPS.findIndex((step) => step.key === job.current_stage)
    : -1;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-y-2 text-xs">
      {PROGRESS_STEPS.map((step, index) => {
        const stepDone = isDone || index < currentIndex;
        const stepCurrent = !isDone && index === currentIndex;
        return (
          <div key={step.key} className="flex items-center">
            <span className="flex items-center gap-1.5">
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] leading-none ${
                  stepDone
                    ? "border-accent bg-accent text-accent-foreground"
                    : stepCurrent
                      ? "border-foreground text-foreground"
                      : "border-border text-muted"
                }`}
              >
                {stepDone ? "✓" : index + 1}
              </span>
              <span
                className={
                  stepCurrent
                    ? "font-medium text-foreground"
                    : stepDone
                      ? "text-foreground"
                      : "text-muted"
                }
              >
                {step.label}
              </span>
            </span>
            {index < PROGRESS_STEPS.length - 1 ? (
              <span className="mx-2 text-border">·</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export default function GeneratePanel({
  courseId,
  explanationLevel,
  latestSummary,
  onVersionCreated,
  onJobUpdate,
}: {
  courseId: number;
  explanationLevel: ExplanationLevel;
  latestSummary: string | null;
  onVersionCreated: () => void;
  /** Called whenever the local job state changes - the parent page's
   * Output panel uses this to show download/partial-status UI without
   * needing its own copy of the polling logic. */
  onJobUpdate?: (job: GenerationJob | null) => void;
}) {
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function updateJob(next: GenerationJob | null) {
    setJob(next);
    onJobUpdate?.(next);
  }

  function pollJob(jobId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const latest = await api.getJob(jobId);
        updateJob(latest);
        if (TERMINAL_STATUSES.has(latest.status)) {
          if (pollRef.current) clearInterval(pollRef.current);
          if (latest.status === "completed") onVersionCreated();
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 1500);
  }

  async function handleGenerate() {
    setStarting(true);
    setError(null);
    try {
      const started = await api.generateCourse(courseId);
      updateJob(started);
      if (TERMINAL_STATUSES.has(started.status)) {
        if (started.status === "completed") onVersionCreated();
      } else {
        pollJob(started.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start generation");
    } finally {
      setStarting(false);
    }
  }

  const isRunning = job ? !TERMINAL_STATUSES.has(job.status) : false;
  const justCompleted = job?.status === "completed";
  // A partial/failed job already exists - the primary button is now
  // explicitly a fresh restart, not a first run, per
  // POST /courses/{course_id}/generate always starting a brand-new job.
  const hasUnresolvedIssue = job ? job.status === "partial" || job.status === "failed" : false;
  const showStoppedInfo = job ? job.status === "partial" || job.status === "failed" : false;

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={handleGenerate}
        disabled={starting || isRunning}
        className="btn-primary w-fit"
      >
        {starting || isRunning
          ? "Generating..."
          : hasUnresolvedIssue
            ? "Regenerate from Scratch"
            : "Generate Final DOCX"}
      </button>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {job ? (
        <div className="rounded-lg bg-surface-muted p-4 text-sm">
          <div className="flex items-center gap-2">
            <StatusBadge label={job.status} tone={STATUS_TONE[job.status]} />
            {job.current_stage ? (
              <span className="text-muted">{STAGE_LABELS[job.current_stage] ?? job.current_stage}</span>
            ) : null}
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent transition-all"
              style={{ width: `${job.progress_percent}%` }}
            />
          </div>
          <ProgressSteps job={job} />
          {showStoppedInfo ? (
            <p className="mt-3 text-muted">
              Stopped after: {job.last_completed_step ?? "the very first step"} (
              {job.completed_modules_count} module(s), {job.completed_reels_count} reel(s)
              completed)
            </p>
          ) : null}
          {showStoppedInfo && job.error_message ? (
            <p className="mt-1 text-red-600 dark:text-red-400">
              {job.error_category
                ? `${ERROR_CATEGORY_LABELS[job.error_category] ?? job.error_category}: `
                : ""}
              {job.error_message}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Downloads live in the Output panel now (it can see this job via
          onJobUpdate above, plus the course's version history) - this
          panel stays focused on the run itself. */}

      {/* explanation_level controls what, if anything, shows beyond the
          DOCX itself - default (final_only) shows nothing extra here. */}
      {justCompleted && explanationLevel === "short_summary" && latestSummary ? (
        <div className="rounded-lg bg-surface-muted p-4 text-sm">
          <p className="mb-1 font-medium">Summary</p>
          <p className="text-muted">{latestSummary}</p>
        </div>
      ) : null}

      {justCompleted && explanationLevel === "full_report" ? (
        <p className="text-sm text-muted">
          See the <span className="font-medium text-foreground">Report</span> section below for a
          full breakdown.
        </p>
      ) : null}
    </div>
  );
}
