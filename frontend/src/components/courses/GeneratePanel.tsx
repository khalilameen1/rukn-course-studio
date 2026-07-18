"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { GenerationJob, GenerationQualityMode, MapPreviewStats } from "@/lib/types";
import StatusBadge from "@/components/ui/StatusBadge";
import WriterTestPanel from "@/components/courses/WriterTestPanel";
import {
  JOB_STATUS_LABEL,
  JOB_STATUS_TONE,
  JOB_TERMINAL_STATUSES,
} from "@/lib/jobStatusMaps";

const TERMINAL_STATUSES = JOB_TERMINAL_STATUSES;

const STAGE_LABELS: Record<string, string> = {
  queued: "Preparing course",
  reading_sources: "Reading sources",
  filling_gaps: "Filling knowledge gaps",
  synthesizing: "Synthesizing research",
  building_map: "Building course map",
  generating: "Writing lessons",
  reviewing_repetition: "Reviewing lessons",
  reviewing: "Finalizing course",
  exporting: "Exporting Teleprompter DOCX",
  done: "Done",
  failed: "Failed",
  partial: "Stopped early",
  paused: "Paused",
  canceled: "Canceled",
};

const PROGRESS_STEPS: { key: string; label: string }[] = [
  { key: "reading_sources", label: "Reading sources" },
  { key: "filling_gaps", label: "Filling knowledge gaps" },
  { key: "building_map", label: "Building course map" },
  { key: "generating", label: "Writing lessons" },
  { key: "reviewing", label: "Finalizing course" },
  { key: "exporting", label: "Exporting Teleprompter DOCX" },
];

const ERROR_CATEGORY_LABELS: Record<string, string> = {
  rate_limit: "Rate limited",
  insufficient_quota: "Out of credits",
  timeout: "Timed out",
  provider_unavailable: "Provider unavailable",
  malformed_response: "Unusable response",
  context_too_long: "Content too long",
  abandoned_run: "Previous run abandoned",
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
    hint: "Full agent mixture — research + quality reviews; longer run, teleprompter-ready DOCX",
  },
  {
    value: "preview",
    label: "Preview",
    hint: "Cheap Spark — faster direction test with lighter review; still teleprompter-ready",
  },
];

const POLL_BASE_MS = 1500;
const POLL_MAX_MS = 12000;

type MissionBrief = {
  headline?: string;
  promise?: string;
  grounding?: string;
  clarity_score?: number;
  confidence?: string;
  premium_recommended?: boolean;
  tighten_brief_suggestion?: string | null;
  one_liner?: string;
};

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

/** Current lesson label: never exceeds total (fixes "Lesson 114 of 113"). */
export function displayCurrentLessonNumber(
  completedLessons: number,
  totalLessons: number,
  isTerminal: boolean,
): number {
  if (totalLessons <= 0) return 0;
  if (isTerminal || completedLessons >= totalLessons) {
    return Math.min(Math.max(completedLessons, 0), totalLessons);
  }
  return Math.min(completedLessons + 1, totalLessons);
}

function progressStepIndex(stage: string | null | undefined): number {
  if (!stage) return -1;
  if (stage === "synthesizing") return PROGRESS_STEPS.findIndex((s) => s.key === "filling_gaps");
  if (stage === "reviewing_repetition") {
    return PROGRESS_STEPS.findIndex((s) => s.key === "reviewing");
  }
  return PROGRESS_STEPS.findIndex((s) => s.key === stage);
}

function AgentRoster({ job }: { job: GenerationJob }) {
  const roster =
    job.agent_roster ??
    [
      { id: "research", label: "Research", state: "idle" },
      { id: "map", label: "Map", state: "idle" },
      { id: "lessons", label: "Lessons", state: "idle" },
      { id: "quality", label: "Quality", state: "idle" },
      { id: "export", label: "Export", state: "idle" },
    ];

  return (
    <div className="mt-3 flex flex-wrap gap-2" aria-label="Agent roster">
      {roster.map((agent) => {
        const running = agent.state === "running";
        const done = agent.state === "done";
        return (
          <span
            key={agent.id}
            className={`rounded-md border px-2 py-1 text-[11px] ${
              done
                ? "border-accent/50 bg-accent/10 text-foreground"
                : running
                  ? "border-foreground text-foreground"
                  : "border-border text-muted"
            }`}
          >
            {done ? "✓ " : running ? "● " : "○ "}
            {agent.label}
          </span>
        );
      })}
    </div>
  );
}

function CostCockpit({ job }: { job: GenerationJob }) {
  const searches = job.web_searches_count ?? 0;
  const cache = job.research_memory_reuse_count ?? 0;
  if (!searches && !cache && !(job.research_tips?.length)) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
      {searches ? <span>{searches} web search(es)</span> : null}
      {cache ? <span>{cache} cache hit(s)</span> : null}
      {job.live_eta_summary ? <span>{job.live_eta_summary}</span> : null}
    </div>
  );
}

function ProgressSteps({ job }: { job: GenerationJob }) {
  const isDone = job.status === "completed" || job.current_stage === "done";
  const currentIndex = progressStepIndex(job.current_stage);

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

function RunSparkpage({
  job,
  onDownloadLatest,
}: {
  job: GenerationJob;
  onDownloadLatest?: () => void;
}) {
  const conf = job.grounding_confidence ?? "mixed";
  return (
    <div className="nc-progress-card animate-in fade-in duration-500 text-sm">
      <p className="text-xs uppercase tracking-wide text-muted">Run complete</p>
      <p className="mt-1 text-lg font-medium text-foreground">Teleprompter ready</p>
      {job.architecture_summary ? (
        <p className="mt-2 text-foreground">{job.architecture_summary}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="rounded-md border border-border px-2 py-1">
          Confidence: {conf}
        </span>
        {job.generation_quality_mode ? (
          <span className="rounded-md border border-border px-2 py-1">
            {job.generation_quality_mode === "preview" ? "Preview Spark" : "Premium mixture"}
          </span>
        ) : null}
      </div>
      {job.provenance_summary ? (
        <p className="mt-3 text-xs text-muted">{job.provenance_summary}</p>
      ) : null}
      {job.research_synthesis_summary ? (
        <p className="mt-1 text-xs text-muted">{job.research_synthesis_summary}</p>
      ) : null}
      <CostCockpit job={job} />
      {job.improve_next_tip ? (
        <p className="mt-3 text-xs text-foreground">
          Next run: {job.improve_next_tip}
        </p>
      ) : null}
      {onDownloadLatest ? (
        <button type="button" onClick={onDownloadLatest} className="btn-primary mt-4 w-fit">
          Download Teleprompter DOCX
        </button>
      ) : (
        <p className="mt-4 text-xs text-muted">
          Use Download DOCX in the Output panel — your Teleprompter is ready.
        </p>
      )}
    </div>
  );
}

function GenerationStatusPanel({
  job,
  onDownloadCompleted,
  onRetryFinalize,
  downloadingCompleted,
  finalizingSaved,
}: {
  job: GenerationJob;
  onDownloadCompleted?: () => void;
  onRetryFinalize?: () => void;
  downloadingCompleted?: boolean;
  finalizingSaved?: boolean;
}) {
  const showStoppedInfo =
    job.status === "partial" || job.status === "failed" || job.status === "canceled";
  const partialAvailable =
    job.partial_docx_available ?? Boolean(job.partial_docx_path);
  const canDownload =
    job.can_download_completed ?? Boolean(job.partial_docx_path || job.output_docx_path);
  const canFinalize =
    job.can_finalize_from_saved ??
    ((job.total_lessons_count ?? 0) > 0 &&
      (job.completed_lessons_count ?? job.completed_reels_count) >=
        (job.total_lessons_count ?? 0) &&
      !job.output_docx_path &&
      job.status !== "completed");
  const isTerminal = TERMINAL_STATUSES.has(job.status);
  const completedLessons =
    job.completed_lessons_count ?? job.completed_reels_count;
  const totalLessons = job.total_lessons_count ?? 0;
  const currentIndex = progressStepIndex(job.current_stage);
  const isDone = job.status === "completed" || job.current_stage === "done";
  const currentLabel =
    job.cancel_requested && job.status === "running"
      ? "Cancel requested. The current step may finish before the run stops."
      : job.last_progress_message ||
        job.public_stage_label ||
        (job.current_stage ? STAGE_LABELS[job.current_stage] ?? job.current_stage : "Preparing");

  const allLessonsSaved =
    totalLessons > 0 && completedLessons >= totalLessons && !job.output_docx_path;

  // When stage is partial/failed, progressStepIndex is -1 — infer completed
  // steps from lesson counts so the UI does not look like "stopped at start".
  let completedSteps = PROGRESS_STEPS.filter((_, i) => isDone || i < currentIndex).map(
    (s) => s.label,
  );
  if (isTerminal && !isDone && completedLessons > 0) {
    const throughKey = allLessonsSaved || canFinalize ? "reviewing" : "generating";
    const inferred = PROGRESS_STEPS.findIndex((s) => s.key === throughKey);
    completedSteps = PROGRESS_STEPS.filter((_, i) => i <= inferred).map((s) => s.label);
  }
  const inProgressStep =
    !isDone && currentIndex >= 0 ? PROGRESS_STEPS[currentIndex]?.label : currentLabel;

  const stoppedStepLabel =
    job.stopped_after_label ||
    (allLessonsSaved ? "All lessons saved" : null) ||
    (completedLessons > 0 ? "Saving lessons" : "an early step");
  const tips = job.research_tips ?? [];

  if (isDone) {
    return <RunSparkpage job={job} onDownloadLatest={onDownloadCompleted} />;
  }

  return (
    <div className="nc-progress-card text-sm">
      <p className="font-medium text-foreground">Generating course</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <StatusBadge label={JOB_STATUS_LABEL[job.status]} tone={JOB_STATUS_TONE[job.status]} />
        {job.generation_quality_mode ? (
          <span className="text-xs text-muted">
            {job.generation_quality_mode === "preview" ? "Preview Spark" : "Premium mixture"}
          </span>
        ) : null}
        {job.architecture_summary ? (
          <span className="text-xs text-muted">{job.architecture_summary}</span>
        ) : null}
      </div>
      <AgentRoster job={job} />
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${job.progress_percent}%` }}
        />
      </div>
      <CostCockpit job={job} />
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="nc-progress-section-title">Current step</p>
          <p className="mt-1 text-foreground">{currentLabel}</p>
          {job.live_eta_summary ? (
            <p className="mt-1 text-xs text-muted">{job.live_eta_summary}</p>
          ) : null}
          {totalLessons > 0 ? (
            <p className="mt-1 text-xs text-muted">
              Lesson{" "}
              {displayCurrentLessonNumber(completedLessons, totalLessons, isTerminal)} of{" "}
              {totalLessons}
            </p>
          ) : null}
        </div>
        <div>
          <p className="nc-progress-section-title">Saved progress</p>
          <p className="mt-1 text-xs text-muted">
            {completedLessons} lesson(s) saved · last update {formatSavedAt(job.last_saved_at)}
          </p>
        </div>
      </div>
      {(job.estimated_usage_summary ||
        job.budget_warning ||
        job.sources_run_summary ||
        job.provenance_summary ||
        job.research_synthesis_summary ||
        tips.length > 0) && (
        <div className="mt-4 rounded-md border border-border bg-surface-muted/40 px-3 py-2 text-xs">
          <p className="nc-progress-section-title">Run signals</p>
          {job.estimated_usage_summary ? (
            <p className="mt-1 text-foreground">{job.estimated_usage_summary}</p>
          ) : null}
          {job.estimated_duration_summary ? (
            <p className="mt-1 text-muted">{job.estimated_duration_summary}</p>
          ) : null}
          {job.sources_run_summary ? (
            <p className="mt-1 text-foreground">Sources: {job.sources_run_summary}</p>
          ) : null}
          {job.research_synthesis_summary ? (
            <p className="mt-1 text-foreground">{job.research_synthesis_summary}</p>
          ) : null}
          {job.provenance_summary ? (
            <p className="mt-1 text-foreground">Provenance: {job.provenance_summary}</p>
          ) : null}
          {job.budget_warning ? (
            <p className="mt-1 text-amber-700 dark:text-amber-400">{job.budget_warning}</p>
          ) : null}
          {tips.map((w) => (
            <p key={w} className="mt-1 text-muted">
              {w}
            </p>
          ))}
        </div>
      )}
      {completedSteps.length > 0 ? (
        <div className="mt-4">
          <p className="nc-progress-section-title">Completed</p>
          <ul className="mt-1 space-y-1 text-xs text-foreground">
            {completedSteps.map((label) => (
              <li key={label}>✓ {label}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {!isTerminal && inProgressStep ? (
        <div className="mt-3">
          <p className="nc-progress-section-title">In progress</p>
          <p className="mt-1 text-xs text-foreground">{inProgressStep}</p>
        </div>
      ) : null}
      <ProgressSteps job={job} />
      <dl className="mt-3 grid gap-1.5 text-xs text-muted sm:grid-cols-2">
        <div>
          <dt className="inline text-foreground">Elapsed: </dt>
          <dd className="inline">
            {formatElapsed(job.created_at, isTerminal ? job.updated_at : null)}
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Partial DOCX: </dt>
          <dd className="inline">{partialAvailable ? "Available" : "Not yet"}</dd>
        </div>
      </dl>
      {showStoppedInfo ? (
        <div className="mt-4 rounded-md border border-border bg-surface-muted/30 px-3 py-3">
          <p className="text-sm font-medium text-foreground">
            {canFinalize ? "Lessons saved — finish without regenerating" : "Run stopped early"}
          </p>
          <p className="mt-1 text-xs text-muted">
            Stopped after: {stoppedStepLabel} · {completedLessons}
            {totalLessons > 0 ? `/${totalLessons}` : ""} lesson(s) saved.
            {canFinalize
              ? " All Final Master scripts are on disk. Finish export uses zero AI tokens."
              : canDownload
                ? " Download what completed, or start a new generation for the rest."
                : " Start a new generation when you are ready."}
          </p>
          {job.error_message ? (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {job.error_category
                ? `${ERROR_CATEGORY_LABELS[job.error_category] ?? job.error_category}: `
                : ""}
              {job.error_message}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {canDownload && onDownloadCompleted ? (
              <button
                type="button"
                className="btn-secondary w-fit"
                disabled={Boolean(downloadingCompleted || finalizingSaved)}
                onClick={onDownloadCompleted}
              >
                {downloadingCompleted
                  ? "Downloading…"
                  : job.output_docx_path
                    ? "Download Teleprompter DOCX"
                    : "Download completed lessons"}
              </button>
            ) : null}
            {canFinalize && onRetryFinalize ? (
              <button
                type="button"
                className="btn-primary w-fit"
                disabled={Boolean(finalizingSaved || downloadingCompleted)}
                onClick={onRetryFinalize}
              >
                {finalizingSaved ? "Finishing…" : "Finish & export Teleprompter"}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
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
  const [finalizingSaved, setFinalizingSaved] = useState(false);
  const [downloadingCompleted, setDownloadingCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qualityMode, setQualityMode] = useState<GenerationQualityMode>("premium");
  const [mission, setMission] = useState<MissionBrief | null>(null);
  const [showTighten, setShowTighten] = useState(false);
  const [mapPreview, setMapPreview] = useState<MapPreviewStats | null>(null);
  const [previewingMap, setPreviewingMap] = useState(false);
  const [mapConfirmed, setMapConfirmed] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollDelayRef = useRef(POLL_BASE_MS);

  function clearPoll() {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }

  useEffect(() => {
    return () => clearPoll();
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getCourseReadiness(courseId)
      .then((r) => {
        if (!cancelled && r.mission_brief) setMission(r.mission_brief);
      })
      .catch(() => {
        /* readiness optional for idle panel */
      });
    api
      .getLatestJob(courseId)
      .then((latest) => {
        if (cancelled) return;
        updateJob(latest);
        if (!TERMINAL_STATUSES.has(latest.status)) pollJob(latest.id);
      })
      .catch(() => {
        /* No run yet */
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
    clearPoll();
    pollDelayRef.current = POLL_BASE_MS;
    let consecutiveFailures = 0;

    const tick = async () => {
      try {
        const latest = await api.getJob(courseId, jobId);
        consecutiveFailures = 0;
        pollDelayRef.current = POLL_BASE_MS;
        updateJob(latest);
        if (TERMINAL_STATUSES.has(latest.status)) {
          clearPoll();
          if (latest.status === "completed") onVersionCreated();
          return;
        }
      } catch {
        consecutiveFailures += 1;
        pollDelayRef.current = Math.min(
          POLL_MAX_MS,
          Math.floor(pollDelayRef.current * 1.6),
        );
        if (consecutiveFailures >= 4) {
          clearPoll();
          setError(
            "Connection to status updates was interrupted. The run may still be continuing on the server. Refresh to restore the latest status.",
          );
          return;
        }
      }
      const jitter = Math.floor(Math.random() * 400);
      pollTimerRef.current = setTimeout(tick, pollDelayRef.current + jitter);
    };

    pollTimerRef.current = setTimeout(tick, pollDelayRef.current);
  }

  async function handleCancel() {
    if (!job) return;
    if (
      !confirm(
        "Stop this generation run? Work already saved may still be available as a partial DOCX.",
      )
    ) {
      return;
    }
    setCanceling(true);
    setError(null);
    try {
      const canceled = await api.cancelGeneration(courseId, job.id);
      updateJob(canceled);
      if (!TERMINAL_STATUSES.has(canceled.status)) {
        pollJob(canceled.id);
      }
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setCanceling(false);
    }
  }

  async function handleDownloadCompleted() {
    if (!job) return;
    setDownloadingCompleted(true);
    setError(null);
    try {
      if (job.output_docx_path || job.status === "completed") {
        await api.downloadLatestDocx(courseId, `course_${courseId}_teleprompter.docx`);
      } else {
        await api.downloadPartialDocx(
          courseId,
          job.id,
          `course_${courseId}_job_${job.id}_completed.docx`,
        );
      }
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setDownloadingCompleted(false);
    }
  }

  async function handleRetryFinalize() {
    if (!job) return;
    setFinalizingSaved(true);
    setError(null);
    try {
      const finished = await api.finalizeSavedJob(courseId, job.id);
      updateJob(finished);
      if (finished.status === "completed") {
        onVersionCreated();
      }
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setFinalizingSaved(false);
    }
  }

  async function handleMapPreview() {
    setPreviewingMap(true);
    setError(null);
    setMapConfirmed(false);
    try {
      const stats = await api.mapPreview(courseId, {
        generation_quality_mode: qualityMode,
      });
      setMapPreview(stats);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setPreviewingMap(false);
    }
  }

  async function handleGenerate() {
    setStarting(true);
    setError(null);
    setShowTighten(false);
    try {
      if (!mapPreview) {
        setError("عاين الخريطة والتكلفة أولًا قبل بدء التوليد الكامل.");
        return;
      }
      if (!mapPreview.can_start_full_generation) {
        setError(
          (mapPreview.warnings ?? []).join(" ") ||
            "الخريطة فيها مشاكل جودة — لا يمكن بدء التوليد الكامل.",
        );
        return;
      }
      if (!mapConfirmed) {
        setError("أكد معاينة الخريطة قبل بدء التوليد الكامل.");
        return;
      }

      const readiness = await api.getCourseReadiness(courseId);
      if (readiness.mission_brief) setMission(readiness.mission_brief);
      if (!readiness.can_start) {
        setError(
          (readiness.blockers ?? []).join(" ") ||
            "Generation is not ready. Check AI provider configuration.",
        );
        return;
      }

      const clarityLow =
        readiness.premium_recommended === false ||
        (readiness.brief_clarity?.clarity_score ?? 100) < 55;
      if (clarityLow && qualityMode === "premium") {
        setShowTighten(true);
        const tip =
          readiness.mission_brief?.tighten_brief_suggestion ||
          readiness.brief_clarity?.message ||
          "Brief clarity is low for Premium.";
        const choice = confirm(
          `${tip}\n\nOK = switch to Preview Spark and start\nCancel = stay and edit the brief first`,
        );
        if (!choice) {
          return;
        }
        setQualityMode("preview");
      }

      const notes: string[] = [...(readiness.warnings ?? [])];
      if (readiness.mission_brief?.one_liner) {
        notes.unshift(readiness.mission_brief.one_liner);
      }
      if (readiness.source_ranking_tips?.length) {
        notes.push(
          `Source ranking:\n${readiness.source_ranking_tips.slice(0, 8).join("\n")}`,
        );
      }
      if (notes.length > 0) {
        if (!confirm(`${notes.join("\n")}\n\nStart generation anyway?`)) {
          return;
        }
      }

      const modeToUse =
        clarityLow && qualityMode === "premium" ? "preview" : qualityMode;

      const started = await api.generateCourse(courseId, {
        generation_quality_mode: modeToUse,
        map_preview_confirmed: true,
        web_research_mode: "disabled",
        approved_snapshot_fingerprint: mapPreview.snapshot_fingerprint,
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
  const canFinalizeSaved =
    Boolean(job?.can_finalize_from_saved) ||
    Boolean(
      job &&
        (job.total_lessons_count ?? 0) > 0 &&
        (job.completed_lessons_count ?? job.completed_reels_count) >=
          (job.total_lessons_count ?? 0) &&
        !job.output_docx_path &&
        job.status !== "completed",
    );
  const hasUnresolvedIssue = job
    ? job.status === "partial" || job.status === "failed" || job.status === "canceled"
    : false;
  const justCompleted = job?.status === "completed";
  // Prefer Finish export over a full regenerate when every lesson is already saved.
  const showFullRegenerate = !canFinalizeSaved;

  return (
    <div className="flex flex-col gap-4">
      {mission && !isRunning ? (
        <div className="rounded-md border border-border bg-surface-muted/30 px-3 py-3 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted">Mission</p>
          <p className="mt-1 font-medium text-foreground">{mission.headline}</p>
          <p className="mt-1 text-xs text-muted">{mission.promise}</p>
          <p className="mt-1 text-xs text-muted">{mission.grounding}</p>
          <p className="mt-2 text-xs text-foreground">
            Clarity {mission.clarity_score ?? "—"}/100 · {mission.confidence ?? "—"}
            {mission.premium_recommended === false ? " · Premium not recommended yet" : ""}
          </p>
          {(showTighten || mission.tighten_brief_suggestion) && mission.tighten_brief_suggestion ? (
            <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
              Tighten: {mission.tighten_brief_suggestion}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        <label className="text-sm text-foreground">
          Generation quality
          <select
            className="mt-1 block w-full max-w-xs rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={qualityMode}
            disabled={starting || isRunning || finalizingSaved}
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

      <div className="rounded-md border border-border px-3 py-3 space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-secondary w-fit"
            disabled={previewingMap || starting || isRunning}
            onClick={handleMapPreview}
          >
            {previewingMap ? "Building map preview…" : "Preview map & cost"}
          </button>
          {mapPreview ? (
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={mapConfirmed}
                disabled={!mapPreview.can_start_full_generation}
                onChange={(e) => setMapConfirmed(e.target.checked)}
              />
              Confirm map before full generation
            </label>
          ) : null}
        </div>
        {mapPreview ? (
          <ul className="text-xs text-muted space-y-1">
            <li>
              {mapPreview.module_count} modules · {mapPreview.lesson_count} lessons · ~
              {mapPreview.estimated_minutes} min · {mapPreview.project_count} projects
            </li>
            <li>
              Theory/practice ~{Math.round(mapPreview.theory_ratio_estimate * 100)}%/
              {Math.round(mapPreview.practice_ratio_estimate * 100)}% · ≈
              {mapPreview.approx_tokens} tokens / ~${mapPreview.approx_cost_usd}
            </li>
            {mapPreview.adapter_id ? (
              <li>
                Domain adapter: {mapPreview.adapter_id}
                {mapPreview.snapshot_fingerprint
                  ? ` · snapshot ${mapPreview.snapshot_fingerprint.slice(0, 8)}`
                  : ""}
              </li>
            ) : null}
            {Object.entries(mapPreview.delivery_mode_counts || {}).map(([k, v]) => (
              <li key={k}>
                {k}: {v}
              </li>
            ))}
            {(mapPreview.warnings || []).map((w) => (
              <li key={w} className="text-amber-800 dark:text-amber-300">
                {w}
              </li>
            ))}
            {!mapPreview.can_start_full_generation ? (
              <li className="text-red-600">Full generation blocked until map issues are fixed.</li>
            ) : null}
          </ul>
        ) : (
          <p className="text-xs text-muted">
            Generate Thesis + compressed Course Map first. Full lesson generation stays off until you
            confirm.
          </p>
        )}
      </div>

      <WriterTestPanel courseId={courseId} />

      <div className="flex flex-wrap items-center gap-3">
        {showFullRegenerate ? (
          <button
            onClick={handleGenerate}
            disabled={
              starting ||
              isRunning ||
              canceling ||
              finalizingSaved ||
              !mapPreview?.can_start_full_generation ||
              !mapConfirmed
            }
            className="btn-primary w-fit"
          >
            {starting || isRunning
              ? "Generating…"
              : hasUnresolvedIssue
                ? "Start generation again"
                : justCompleted
                  ? "Run again"
                  : "Start full course generation"}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleRetryFinalize}
            disabled={finalizingSaved || starting || canceling}
            className="btn-primary w-fit"
          >
            {finalizingSaved ? "Finishing…" : "Finish & export Teleprompter"}
          </button>
        )}
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
        {canFinalizeSaved && showFullRegenerate === false ? (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={starting || isRunning || canceling || finalizingSaved}
            className="btn-secondary w-fit"
          >
            Start new generation instead
          </button>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {!job && !starting && !error ? (
        <p className="text-sm text-muted">
          Start generation to produce the Teleprompter DOCX. Progress updates live while the run is
          active.
        </p>
      ) : null}

      {job ? (
        <GenerationStatusPanel
          job={job}
          onDownloadCompleted={handleDownloadCompleted}
          onRetryFinalize={handleRetryFinalize}
          downloadingCompleted={downloadingCompleted}
          finalizingSaved={finalizingSaved}
        />
      ) : null}
    </div>
  );
}
