"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type {
  AddressForm,
  GenerationJob,
  GenerationQualityMode,
  MapPreviewStats,
  WebResearchMode,
} from "@/lib/types";
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

function RunSparkpage({ job }: { job: GenerationJob }) {
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
      {job.improve_next_tip ? (
        <p className="mt-3 text-xs text-foreground">Next run: {job.improve_next_tip}</p>
      ) : null}
      <p className="mt-4 text-xs text-muted">
        Download the Teleprompter DOCX from the Output panel on the right.
      </p>
    </div>
  );
}

function GenerationStatusPanel({ job }: { job: GenerationJob }) {
  const showStoppedInfo =
    job.status === "partial" || job.status === "failed" || job.status === "canceled";
  const partialAvailable =
    job.partial_docx_available ?? Boolean(job.partial_docx_path);
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
  const isDone = job.status === "completed" || job.current_stage === "done";
  const currentLabel =
    job.cancel_requested && job.status === "running"
      ? "Cancel requested. The current step may finish before the run stops."
      : job.last_progress_message ||
        job.public_stage_label ||
        (job.current_stage ? STAGE_LABELS[job.current_stage] ?? job.current_stage : "Preparing");

  const allLessonsSaved =
    totalLessons > 0 && completedLessons >= totalLessons && !job.output_docx_path;
  const stoppedStepLabel =
    job.stopped_after_label ||
    (allLessonsSaved ? "All lessons saved" : null) ||
    (completedLessons > 0 ? "Saving lessons" : "an early step");
  const tips = job.research_tips ?? [];

  if (isDone) {
    return <RunSparkpage job={job} />;
  }

  return (
    <div className="nc-progress-card text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={JOB_STATUS_LABEL[job.status]} tone={JOB_STATUS_TONE[job.status]} />
        <span className="text-xs text-muted">{job.progress_percent}%</span>
        {job.generation_quality_mode ? (
          <span className="text-xs text-muted">
            {job.generation_quality_mode === "preview" ? "Preview" : "Premium"}
          </span>
        ) : null}
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${job.progress_percent}%` }}
        />
      </div>
      <p className="mt-3 font-medium text-foreground">{currentLabel}</p>
      {totalLessons > 0 ? (
        <p className="mt-1 text-xs text-muted">
          Lesson {displayCurrentLessonNumber(completedLessons, totalLessons, isTerminal)} of{" "}
          {totalLessons}
          {" · "}
          {completedLessons} saved · {formatElapsed(job.created_at, isTerminal ? job.updated_at : null)}
          {job.live_eta_summary ? ` · ${job.live_eta_summary}` : ""}
        </p>
      ) : (
        <p className="mt-1 text-xs text-muted">
          Elapsed {formatElapsed(job.created_at, isTerminal ? job.updated_at : null)}
          {job.live_eta_summary ? ` · ${job.live_eta_summary}` : ""}
        </p>
      )}
      <CostCockpit job={job} />
      {showStoppedInfo ? (
        <div className="mt-3 rounded-md border border-border bg-surface-muted/30 px-3 py-2 text-xs">
          <p className="font-medium text-foreground">
            {canFinalize
              ? "All lessons saved — finish export above (no AI tokens)."
              : `Stopped after ${stoppedStepLabel} · ${completedLessons}${
                  totalLessons > 0 ? `/${totalLessons}` : ""
                } saved.`}
          </p>
          {partialAvailable ? (
            <p className="mt-1 text-muted">Partial DOCX is available in the Output panel.</p>
          ) : null}
          {job.error_message ? (
            <p className="mt-2 text-red-600 dark:text-red-400">
              {job.error_category
                ? `${ERROR_CATEGORY_LABELS[job.error_category] ?? job.error_category}: `
                : ""}
              {job.error_message}
            </p>
          ) : null}
        </div>
      ) : null}
      <details className="mt-3 text-xs text-muted">
        <summary className="cursor-pointer font-medium text-foreground">Run details</summary>
        <div className="mt-2 space-y-3">
          <AgentRoster job={job} />
          <ProgressSteps job={job} />
          {job.estimated_usage_summary ? (
            <p className="text-foreground">{job.estimated_usage_summary}</p>
          ) : null}
          {job.sources_run_summary ? <p>Sources: {job.sources_run_summary}</p> : null}
          {job.budget_warning ? (
            <p className="text-amber-700 dark:text-amber-400">{job.budget_warning}</p>
          ) : null}
          {tips.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      </details>
    </div>
  );
}

export default function GeneratePanel({
  courseId,
  onVersionCreated,
  onJobUpdate,
  initialQualityMode = "premium",
  initialWebResearchMode = "autonomous_gap_fill",
  addressForm = "masculine",
  presenterLanguage = "ar",
  presenterDialect = "egyptian",
}: {
  courseId: number;
  onVersionCreated: () => void;
  onJobUpdate?: (job: GenerationJob | null) => void;
  initialQualityMode?: GenerationQualityMode;
  initialWebResearchMode?: WebResearchMode;
  addressForm?: AddressForm;
  presenterLanguage?: string;
  presenterDialect?: string;
}) {
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [finalizingSaved, setFinalizingSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qualityMode, setQualityMode] = useState<GenerationQualityMode>(initialQualityMode);
  const [webResearchMode, setWebResearchMode] =
    useState<WebResearchMode>(initialWebResearchMode);
  const [humanOverrideHardLimits, setHumanOverrideHardLimits] = useState(false);
  const [mission, setMission] = useState<MissionBrief | null>(null);
  const [showTighten, setShowTighten] = useState(false);
  const [mapPreview, setMapPreview] = useState<MapPreviewStats | null>(null);
  const [previewingMap, setPreviewingMap] = useState(false);
  const [mapConfirmed, setMapConfirmed] = useState(false);
  const [pendingStart, setPendingStart] = useState<{
    resumeIncomplete: boolean;
    notes: string[];
    clarityLow: boolean;
    tip?: string;
  } | null>(null);
  const [showMoreActions, setShowMoreActions] = useState(false);
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
        web_research_mode: webResearchMode,
        human_override_hard_limits: humanOverrideHardLimits,
        address_form: addressForm,
        presenter_language: presenterLanguage,
        presenter_dialect: presenterDialect,
      });
      setMapPreview(stats);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setPreviewingMap(false);
    }
  }

  async function requestGenerate(opts?: { resumeIncomplete?: boolean }) {
    setError(null);
    setShowTighten(false);
    setPendingStart(null);
    try {
      if (!mapPreview) {
        setError("Preview and confirm the course map before starting full generation.");
        return;
      }
      if (!mapPreview.can_start_full_generation) {
        setError(
          (mapPreview.warnings ?? []).join(" ") ||
            "Map quality issues block full generation.",
        );
        return;
      }
      if (!mapConfirmed) {
        setError("Confirm the map preview before starting full generation.");
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
      const tip =
        readiness.mission_brief?.tighten_brief_suggestion ||
        readiness.brief_clarity?.message ||
        undefined;

      const notes: string[] = [...(readiness.warnings ?? [])];
      if (readiness.mission_brief?.one_liner) {
        notes.unshift(readiness.mission_brief.one_liner);
      }
      if (readiness.source_ranking_tips?.length) {
        notes.push(
          `Source ranking: ${readiness.source_ranking_tips.slice(0, 4).join(" · ")}`,
        );
      }
      if (opts?.resumeIncomplete) {
        notes.push(
          "Continue reuses saved lessons and spends API tokens only on the missing ones.",
        );
      } else if (
        job &&
        (job.status === "partial" || job.status === "failed" || job.status === "canceled")
      ) {
        notes.push(
          "Full regenerate starts from scratch and spends tokens again.",
        );
      }

      if (notes.length > 0 || (clarityLow && qualityMode === "premium")) {
        if (clarityLow && qualityMode === "premium") setShowTighten(true);
        setPendingStart({
          resumeIncomplete: Boolean(opts?.resumeIncomplete),
          notes,
          clarityLow: clarityLow && qualityMode === "premium",
          tip,
        });
        return;
      }

      await runGenerate({
        resumeIncomplete: Boolean(opts?.resumeIncomplete),
        forcePreview: false,
      });
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    }
  }

  async function runGenerate(opts: {
    resumeIncomplete: boolean;
    forcePreview: boolean;
  }) {
    if (!mapPreview) return;
    setStarting(true);
    setError(null);
    setPendingStart(null);
    try {
      const modeToUse = opts.forcePreview ? "preview" : qualityMode;
      if (opts.forcePreview) setQualityMode("preview");

      const started = await api.generateCourse(courseId, {
        generation_quality_mode: modeToUse,
        map_preview_confirmed: true,
        web_research_mode: webResearchMode,
        human_override_hard_limits: humanOverrideHardLimits,
        approved_snapshot_fingerprint: mapPreview.snapshot_fingerprint,
        resume_incomplete: opts.resumeIncomplete,
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
  const canResumeIncomplete =
    Boolean(job?.can_resume_incomplete) ||
    Boolean(
      job &&
        hasUnresolvedIssue &&
        (job.total_lessons_count ?? 0) > 0 &&
        (job.completed_lessons_count ?? job.completed_reels_count) > 0 &&
        (job.completed_lessons_count ?? job.completed_reels_count) <
          (job.total_lessons_count ?? 0),
    );

  return (
    <div className="flex flex-col gap-4">
      {mission && !isRunning ? (
        <div className="rounded-md border border-border bg-surface-muted/30 px-3 py-2 text-sm">
          <p className="font-medium text-foreground">{mission.headline}</p>
          <p className="mt-1 text-xs text-muted">
            Clarity {mission.clarity_score ?? "—"}/100
            {mission.premium_recommended === false ? " · Premium not recommended yet" : ""}
          </p>
          {(showTighten || mission.tighten_brief_suggestion) && mission.tighten_brief_suggestion ? (
            <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
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
            onChange={(e) => {
              setQualityMode(e.target.value as GenerationQualityMode);
              setMapPreview(null);
              setMapConfirmed(false);
            }}
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

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm text-foreground">
          Research choice
          <select
            className="mt-1 block w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={webResearchMode}
            disabled={starting || isRunning || finalizingSaved}
            onChange={(e) => {
              setWebResearchMode(e.target.value as WebResearchMode);
              setMapPreview(null);
              setMapConfirmed(false);
            }}
          >
            <option value="autonomous_gap_fill">Fill evidence gaps from the web</option>
            <option value="disabled">Disabled — supplied sources only</option>
          </select>
        </label>
        <div className="rounded-md border border-border bg-surface-muted/30 px-3 py-2 text-xs text-muted">
          <p className="font-medium text-foreground">Delivery language</p>
          <p className="mt-1">
            {presenterLanguage} · {presenterDialect} · {addressForm} address
          </p>
          <p className="mt-1">Edit these values in the Course brief before previewing.</p>
        </div>
      </div>

      <label className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
        <span className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={humanOverrideHardLimits}
            disabled={starting || isRunning || finalizingSaved}
            onChange={(e) => {
              setHumanOverrideHardLimits(e.target.checked);
              setMapPreview(null);
              setMapConfirmed(false);
            }}
          />
          <span>
            <span className="block font-medium">Human hard-limit override</span>
            <span className="mt-1 block text-xs">
              Warning: this permits a map beyond canonical duration or lesson limits. Your
              confirmation is recorded; semantic quality and export gates still cannot be bypassed.
            </span>
          </span>
        </span>
      </label>

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

      <details className="rounded-md border border-border px-3 py-2 text-sm">
        <summary className="cursor-pointer font-medium text-foreground">
          Advanced: Writer Test (3 sample lessons)
        </summary>
        <div className="mt-3">
          <WriterTestPanel courseId={courseId} />
        </div>
      </details>

      {pendingStart ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-medium">Confirm before starting</p>
          {pendingStart.clarityLow ? (
            <p className="mt-2 text-xs">
              {pendingStart.tip || "Brief clarity is low for Premium."} You can switch to
              Preview Spark, or keep Premium.
            </p>
          ) : null}
          {pendingStart.notes.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs">
              {pendingStart.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {pendingStart.clarityLow ? (
              <button
                type="button"
                className="btn-primary w-fit"
                disabled={starting}
                onClick={() =>
                  runGenerate({
                    resumeIncomplete: pendingStart.resumeIncomplete,
                    forcePreview: true,
                  })
                }
              >
                Switch to Preview & start
              </button>
            ) : null}
            <button
              type="button"
              className={pendingStart.clarityLow ? "btn-secondary w-fit" : "btn-primary w-fit"}
              disabled={starting}
              onClick={() =>
                runGenerate({
                  resumeIncomplete: pendingStart.resumeIncomplete,
                  forcePreview: false,
                })
              }
            >
              {pendingStart.clarityLow ? "Keep Premium & start" : "Start now"}
            </button>
            <button
              type="button"
              className="btn-secondary w-fit"
              disabled={starting}
              onClick={() => setPendingStart(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          {canFinalizeSaved ? (
            <button
              type="button"
              onClick={handleRetryFinalize}
              disabled={finalizingSaved || starting || canceling || isRunning}
              className="btn-primary w-fit"
            >
              {finalizingSaved ? "Finishing…" : "Finish & export Teleprompter"}
            </button>
          ) : canResumeIncomplete ? (
            <button
              type="button"
              onClick={() => requestGenerate({ resumeIncomplete: true })}
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
              {starting || isRunning ? "Generating…" : "Continue from saved lessons"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => requestGenerate({ resumeIncomplete: false })}
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
                : justCompleted
                  ? "Run again"
                  : "Start full course generation"}
            </button>
          )}
          {isRunning ? (
            <button
              type="button"
              onClick={handleCancel}
              disabled={canceling || starting}
              className="btn-secondary w-fit"
            >
              {canceling ? "Stopping…" : "Stop"}
            </button>
          ) : null}
          {!isRunning && (canResumeIncomplete || canFinalizeSaved || hasUnresolvedIssue) ? (
            <button
              type="button"
              className="text-xs text-muted underline-offset-2 hover:underline"
              onClick={() => setShowMoreActions((v) => !v)}
            >
              {showMoreActions ? "Hide other actions" : "Other actions"}
            </button>
          ) : null}
        </div>
        {showMoreActions && !isRunning ? (
          <div className="flex flex-wrap gap-2">
            {(canResumeIncomplete || canFinalizeSaved || hasUnresolvedIssue) ? (
              <button
                type="button"
                onClick={() => requestGenerate({ resumeIncomplete: false })}
                disabled={
                  starting ||
                  finalizingSaved ||
                  !mapPreview?.can_start_full_generation ||
                  !mapConfirmed
                }
                className="btn-secondary w-fit"
              >
                Regenerate from scratch
              </button>
            ) : null}
          </div>
        ) : null}
        {!mapConfirmed && (canResumeIncomplete || !canFinalizeSaved) && !isRunning ? (
          <p className="text-xs text-muted">
            Preview & confirm the map once, then use the primary action above.
          </p>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {!job && !starting && !error ? (
        <p className="text-sm text-muted">
          Preview the map, then start generation. Progress updates live while the run is active.
        </p>
      ) : null}

      {job ? <GenerationStatusPanel job={job} /> : null}
    </div>
  );
}
