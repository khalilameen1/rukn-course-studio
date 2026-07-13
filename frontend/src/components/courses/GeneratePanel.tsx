"use client";

import { useEffect, useRef, useState } from "react";
import { api, latestDownloadUrl } from "@/lib/api";
import type { ExplanationLevel, GenerationJob } from "@/lib/types";

const TERMINAL_STATUSES = new Set<GenerationJob["status"]>(["completed", "failed"]);

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
};

export default function GeneratePanel({
  courseId,
  hasVersion,
  explanationLevel,
  latestSummary,
  onVersionCreated,
}: {
  courseId: number;
  hasVersion: boolean;
  explanationLevel: ExplanationLevel;
  latestSummary: string | null;
  onVersionCreated: () => void;
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

  function pollJob(jobId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const latest = await api.getJob(jobId);
        setJob(latest);
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
      setJob(started);
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

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={handleGenerate}
        disabled={starting || isRunning}
        className="w-fit rounded-full bg-foreground px-5 py-2 text-sm text-background disabled:opacity-60"
      >
        {starting || isRunning ? "Generating..." : "Generate Final DOCX"}
      </button>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {job ? (
        <div className="rounded-lg border border-black/10 p-4 text-sm dark:border-white/10">
          <p>
            Status: <span className="font-medium">{job.status}</span>
            {job.current_stage ? (
              <span className="text-zinc-500">
                {" "}
                ({STAGE_LABELS[job.current_stage] ?? job.current_stage})
              </span>
            ) : null}
          </p>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
            <div
              className="h-full rounded-full bg-foreground transition-all"
              style={{ width: `${job.progress_percent}%` }}
            />
          </div>
          {job.status === "failed" && job.error_message ? (
            <p className="mt-2 text-red-600">{job.error_message}</p>
          ) : null}
        </div>
      ) : null}

      {hasVersion ? (
        <a
          href={latestDownloadUrl(courseId)}
          className="w-fit rounded-full border border-black/15 px-5 py-2 text-sm hover:bg-black/[.03] dark:border-white/20 dark:hover:bg-white/[.05]"
        >
          Download Latest DOCX
        </a>
      ) : (
        <p className="text-sm text-zinc-500">No DOCX generated yet.</p>
      )}

      {/* explanation_level controls what, if anything, shows beyond the
          DOCX itself - default (final_only) shows nothing extra here. */}
      {justCompleted && explanationLevel === "short_summary" && latestSummary ? (
        <div className="rounded-lg border border-black/10 bg-black/[.02] p-4 text-sm dark:border-white/10 dark:bg-white/[.03]">
          <p className="mb-1 font-medium">Summary</p>
          <p className="text-zinc-600 dark:text-zinc-400">{latestSummary}</p>
        </div>
      ) : null}

      {justCompleted && explanationLevel === "full_report" ? (
        <p className="text-sm text-zinc-500">
          See the <span className="font-medium">Report</span> tab for a full breakdown.
        </p>
      ) : null}
    </div>
  );
}
