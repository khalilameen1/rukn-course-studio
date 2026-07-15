"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { GenerationJob, GenerationQualityMode } from "@/lib/types";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  JOB_STATUS_LABEL,
  JOB_STATUS_TONE,
  JOB_TERMINAL_STATUSES,
} from "@/lib/jobStatusMaps";

const TERMINAL_STATUSES = JOB_TERMINAL_STATUSES;

const STAGE_LABELS: Record<string, string> = {
  queued: "Preparing course",
  reading_sources: "Building course map",
  building_map: "Building course map",
  generating: "Writing lessons",
  reviewing_repetition: "Running specialist critic",
  reviewing: "Rewriting final master version",
  exporting: "Exporting Teleprompter DOCX",
  done: "Done",
  failed: "Failed",
  partial: "Stopped early",
  paused: "Paused",
  canceled: "Canceled",
};

const PROGRESS_STEPS: { key: string; label: string }[] = [
  { key: "reading_sources", label: "Building course map" },
  { key: "building_map", label: "Building / rebuilding course map" },
  { key: "generating", label: "Draft → reviews → final master" },
  { key: "reviewing_repetition", label: "Specialist critic" },
  { key: "reviewing", label: "Final master" },
  { key: "exporting", label: "Exporting Teleprompter DOCX" },
];

const ERROR_CATEGORY_LABELS: Record<string, string> = {
  rate_limit: "Rate limited",
  insufficient_quota: "Out of credits",
  timeout: "Timed out",
  provider_unavailable: "Provider unavailable",
  malformed_response: "Unusable response",
  context_too_long: "Content too long",
  unknown: "Unexpected error",
};

const QUALITY_MODE_OPTIONS: {
  value: GenerationQualityMode;
  label: string;
  hint: string;
}[] = [
  {
    value: "premium",
    label: "Premium",
    hint: "Creator draft → student / critic / mentor review → Creator final master",
  },
  {
    value: "preview",
    label: "Preview",
    hint: "Faster direction test; simplified review; still teleprompter-ready",
  },
];

function formatElapsed(fromIso: string, toIso?: string | null): string {
  const start = new Date(fromIso).getTime();
  const end = toIso ? new Date(toIso).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "—";
  const sec = Math.floor((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem}s`;
}

function formatSavedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return "—";
  }
}

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

function GenerationStatusPanel({ job }: { job: GenerationJob }) {
  const showStoppedInfo =
    job.status === "partial" || job.status === "failed" || job.status === "canceled";
  const partialAvailable =
    job.partial_docx_available ?? Boolean(job.partial_docx_path);
  const isTerminal = TERMINAL_STATUSES.has(job.status);
  const completedLessons =
    job.completed_lessons_count ?? job.completed_reels_count;
  const totalLessons = job.total_lessons_count ?? 0;

  return (
    <div className="rounded-lg bg-surface-muted p-4 text-sm">
      <p className="mb-2 font-medium text-foreground">Generation Status</p>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={JOB_STATUS_LABEL[job.status]} tone={JOB_STATUS_TONE[job.status]} />
        {job.generation_quality_mode ? (
          <span className="text-xs text-muted">
            {job.generation_quality_mode === "preview" ? "Preview" : "Premium"}
          </span>
        ) : null}
        <span className="text-muted">
          {job.last_progress_message ||
            (job.current_stage ? STAGE_LABELS[job.current_stage] ?? job.current_stage : "—")}
        </span>
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${job.progress_percent}%` }}
        />
      </div>
      <ProgressSteps job={job} />
      <dl className="mt-3 grid gap-1.5 text-xs text-muted sm:grid-cols-2">
        <div>
          <dt className="inline text-foreground">Current step: </dt>
          <dd className="inline">
            {job.last_progress_message ||
              (job.current_stage ? STAGE_LABELS[job.current_stage] ?? job.current_stage : "—")}
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Module / lesson: </dt>
          <dd className="inline">
            {job.current_module_index != null
              ? `M${job.current_module_index}${
                  job.current_lesson_index != null ? ` · L${job.current_lesson_index}` : ""
                }`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Completed: </dt>
          <dd className="inline">
            {completedLessons}
            {totalLessons ? ` / ${totalLessons}` : ""} lesson(s)
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Last saved: </dt>
          <dd className="inline">{formatSavedAt(job.last_saved_at)}</dd>
        </div>
        <div>
          <dt className="inline text-foreground">Elapsed: </dt>
          <dd className="inline">
            {formatElapsed(job.created_at, isTerminal ? job.updated_at : null)}
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Estimated duration: </dt>
          <dd className="inline">{job.estimated_duration_summary || "—"}</dd>
        </div>
        <div>
          <dt className="inline text-foreground">Estimated usage: </dt>
          <dd className="inline">{job.estimated_usage_summary || "—"}</dd>
        </div>
        <div>
          <dt className="inline text-foreground">Partial DOCX available: </dt>
          <dd className="inline">{partialAvailable ? "Yes" : "No"}</dd>
        </div>
      </dl>
      {showStoppedInfo ? (
        <p className="mt-3 text-muted">
          Stopped after: {job.last_completed_step ?? "the very first step"} (
          {completedLessons} lesson(s) completed). You can download partial output if available,
          then regenerate.
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
      {/* Critic / student / mentor notes and drafts are never shown here. */}
    </div>
  );
}

export default function GeneratePanel({
  courseId,
  onVersionCreated,
  onJobUpdate,
}: {
  courseId: number;
  onVersionCreated: () => void;
  onJobUpdate?: (job: GenerationJob | null) => void;
}) {
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qualityMode, setQualityMode] = useState<GenerationQualityMode>("premium");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    // Restore the latest run after a page refresh so an in-flight
    // generation is visible again (and polling resumes) instead of the
    // panel silently pretending nothing ever ran. 404 = never generated.
    let cancelled = false;
    api
      .getLatestJob(courseId)
      .then((latest) => {
        if (cancelled) return;
        updateJob(latest);
        if (!TERMINAL_STATUSES.has(latest.status)) pollJob(latest.id);
      })
      .catch(() => {
        // No run yet - normal empty state.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId]);

  function updateJob(next: GenerationJob | null) {
    setJob(next);
    onJobUpdate?.(next);
  }

  function pollJob(jobId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    // Tolerate transient network blips: only stop polling after several
    // consecutive failures, and tell the user instead of spinning forever.
    let consecutiveFailures = 0;
    pollRef.current = setInterval(async () => {
      try {
        const latest = await api.getJob(jobId);
        consecutiveFailures = 0;
        updateJob(latest);
        if (TERMINAL_STATUSES.has(latest.status)) {
          if (pollRef.current) clearInterval(pollRef.current);
          if (latest.status === "completed") onVersionCreated();
        }
      } catch (err) {
        consecutiveFailures += 1;
        if (consecutiveFailures >= 4) {
          if (pollRef.current) clearInterval(pollRef.current);
          setError(
            "Lost connection while checking generation progress. The run continues on the server — refresh the page to see the latest status."
          );
        }
      }
    }, 1500);
  }

  async function handleCancel() {
    if (!job) return;
    if (!confirm("Stop this generation run? Work already saved may still be available as a partial DOCX.")) {
      return;
    }
    setCanceling(true);
    setError(null);
    try {
      const canceled = await api.cancelGeneration(courseId, job.id);
      if (pollRef.current) clearInterval(pollRef.current);
      updateJob(canceled);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setCanceling(false);
    }
  }

  async function handleGenerate() {
    setStarting(true);
    setError(null);
    try {
      const started = await api.generateCourse(courseId, {
        generation_quality_mode: qualityMode,
      });
      updateJob(started);
      if (TERMINAL_STATUSES.has(started.status)) {
        if (started.status === "completed") onVersionCreated();
      } else {
        pollJob(started.id);
      }
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setStarting(false);
    }
  }

  const isRunning = job ? !TERMINAL_STATUSES.has(job.status) : false;
  const hasUnresolvedIssue = job
    ? job.status === "partial" || job.status === "failed" || job.status === "canceled"
    : false;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="text-sm text-foreground">
          Generation quality
          <select
            className="mt-1 block w-full max-w-xs rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={qualityMode}
            disabled={starting || isRunning}
            onChange={(e) => setQualityMode(e.target.value as GenerationQualityMode)}
          >
            {QUALITY_MODE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-muted">
          {QUALITY_MODE_OPTIONS.find((o) => o.value === qualityMode)?.hint}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={starting || isRunning || canceling}
          className="btn-primary w-fit"
        >
          {starting || isRunning
            ? "Generating..."
            : hasUnresolvedIssue
              ? "Regenerate from Scratch"
              : "Generate Final DOCX"}
        </button>
        {isRunning ? (
          <button
            type="button"
            onClick={handleCancel}
            disabled={canceling || starting}
            className="btn-secondary w-fit"
          >
            {canceling ? "Stopping…" : "Stop generation"}
          </button>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {job ? <GenerationStatusPanel job={job} /> : null}

      {/* V1: Teleprompter DOCX only — no summary/report panels. */}
    </div>
  );
}
