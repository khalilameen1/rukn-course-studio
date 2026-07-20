"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type {
  Course,
  CourseSource,
  CourseVersion,
  DiagnosticsResponse,
  GenerationJob,
  Priority,
  SourceCategory,
} from "@/lib/types";
import CourseTabs, { type CourseTab } from "@/components/courses/CourseTabs";
import CourseForm, {
  courseToFormValues,
  type CourseFormValues,
} from "@/components/courses/CourseForm";
import SourceUploadForm from "@/components/courses/SourceUploadForm";
import NotesSourceForm from "@/components/courses/NotesSourceForm";
import SourceTable from "@/components/courses/SourceTable";
import GeneratePanel from "@/components/courses/GeneratePanel";
import VersionTable from "@/components/courses/VersionTable";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import SectionPanel from "@/components/ui/SectionPanel";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  COURSE_DISPLAY_STATUS_LABEL,
  COURSE_DISPLAY_STATUS_TONE,
  deriveCourseDisplayStatus,
} from "@/lib/courseDisplayStatus";
import { SOURCE_CATEGORY_LABELS } from "@/lib/sourceCategories";
import { GENERATION_PRESET_LABELS } from "@/lib/generationPresets";

const STRUCTURE_MODE_LABELS: Record<string, string> = {
  connected_no_modules: "Connected, no modules",
  connected_modules_with_bridge_projects: "Connected + bridge projects",
};

const EXPLANATION_LEVEL_LABELS: Record<string, string> = {
  final_only: "Final DOCX only",
  short_summary: "Short summary",
  full_report: "Full report",
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="text-sm whitespace-pre-wrap">{value}</p>
    </div>
  );
}

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const courseId = Number(params.id);
  const invalidId = !Number.isFinite(courseId) || courseId <= 0;

  const [course, setCourse] = useState<Course | null>(null);
  const [sources, setSources] = useState<CourseSource[]>([]);
  const [versions, setVersions] = useState<CourseVersion[]>([]);
  const [activeKnowledgeCount, setActiveKnowledgeCount] = useState<number | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null);
  const [tab, setTab] = useState<CourseTab>("sources");
  const [editingBrief, setEditingBrief] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFlushNotice, setSourceFlushNotice] = useState<string | null>(null);
  // Mirrors GeneratePanel's own job state via onJobUpdate - the Output
  // panel below is the canonical place for download/partial-status UI, so
  // it needs to see the current run without duplicating the polling logic.
  const [currentJob, setCurrentJob] = useState<GenerationJob | null>(null);
  const [downloadingLatest, setDownloadingLatest] = useState(false);
  const [downloadingPartial, setDownloadingPartial] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [courseUsage, setCourseUsage] = useState<{ cost: number; events: number } | null>(null);

  const loadAll = useCallback(async () => {
    if (invalidId) {
      setLoading(false);
      setError("Invalid course link.");
      return;
    }
    setError(null);
    try {
      const [courseData, sourcesData, versionsData] = await Promise.all([
        api.getCourse(courseId),
        api.listSources(courseId),
        api.listVersions(courseId),
      ]);
      setCourse(courseData);
      setSources(sourcesData);
      setVersions(versionsData);
      try {
        const usage = await api.getCourseAIUsage(courseId);
        setCourseUsage({ cost: usage.estimated_cost_usd, events: usage.event_count });
      } catch {
        // optional signal
      }
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setLoading(false);
    }
  }, [courseId, invalidId]);

  useEffect(() => {
    // Standard fetch-on-mount; `loadAll` is also reused after mutations
    // (brief edits, generation completing), so it isn't inlined here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get("sources_failed") !== "1") return;
    const reason = sp.get("reason")?.trim();
    // This state mirrors a one-time redirect query flag.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSourceFlushNotice(
      reason
        ? `Sources from the create form could not be saved (${reason}). Upload them again below, then start generation.`
        : "Sources from the create form could not be saved. Upload them again below, then start generation.",
    );
    setTab("sources");
  }, []);

  useEffect(() => {
    if (invalidId) return;
    // Lightweight Inputs/Output panel signals - failures here shouldn't
    // block the rest of the workspace from loading.
    api
      .getCourseReadiness(courseId)
      .then((r) => setActiveKnowledgeCount(r.active_rule_key_count))
      .catch(() => setActiveKnowledgeCount(null));

    api
      .diagnosticsFull()
      .then(setDiagnostics)
      .catch(() => setDiagnostics(null));

    api
      .getCourseAIUsage(courseId)
      .then((usage) => setCourseUsage({ cost: usage.estimated_cost_usd, events: usage.event_count }))
      .catch(() => setCourseUsage(null));
  }, [courseId, invalidId]);

  async function handleBriefSubmit(values: CourseFormValues) {
    const updated = await api.updateCourse(courseId, {
      title: values.title,
      audience: values.audience,
      outcome: values.outcome,
      special_notes: values.special_notes || null,
      course_domain: values.course_domain || null,
      structure_mode: values.structure_mode,
      manual_map_text: values.manual_map_text || null,
      explanation_level: values.explanation_level,
      generation_preset: values.generation_preset,
      generation_quality_mode: values.generation_quality_mode,
      target_market: values.target_market,
      primary_course_family: values.primary_course_family,
      web_research_mode: values.web_research_mode,
      student_language: values.student_language,
      spoken_variety: values.spoken_variety,
      address_form: values.address_form,
    });
    setCourse(updated);
    setEditingBrief(false);
  }

  async function handleUpload(
    file: File,
    category: SourceCategory,
    priority: Priority,
    opts?: { password?: string; force?: boolean },
  ) {
    const created = await api.uploadSource(courseId, file, category, priority, opts);
    setSources((prev) => [...prev, created]);
  }

  async function handleAddNote(text: string, category: SourceCategory, priority: Priority) {
    const created = await api.addNotesSource(courseId, {
      text,
      source_category: category,
      priority,
    });
    setSources((prev) => [...prev, created]);
  }

  async function handleDeleteSource(source: CourseSource) {
    const name = source.original_filename || source.display_title || source.title || `source-${source.id}`;
    if (!confirm(`Delete source "${name}"?\n\nType confirmation is sent as the exact name.`)) return;
    await api.deleteSource(courseId, source.id, name);
    setSources((prev) => prev.filter((s) => s.id !== source.id));
  }

  async function handleSourceCategoryChange(source: CourseSource, category: SourceCategory) {
    const updated = await api.patchSource(courseId, source.id, {
      source_category: category,
    });
    setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  async function handleSourceIncludeChange(source: CourseSource, include: boolean) {
    const updated = await api.patchSource(courseId, source.id, {
      include_in_generation: include,
    });
    setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  async function handleSourceReprocess(source: CourseSource, password?: string) {
    const updated = await api.reprocessSource(courseId, source.id, password);
    setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  async function handleSourcePreview(source: CourseSource) {
    const preview = await api.getSourceAnalysis(courseId, source.id);
    return {
      summary: preview.source_summary,
      keyPoints: preview.key_points ?? [],
    };
  }

  async function handleDownloadLatest(version: CourseVersion) {
    setDownloadError(null);
    setDownloadingLatest(true);
    try {
      await api.downloadLatestDocx(courseId, `course_${courseId}_v${version.version_number}.docx`);
    } catch (err) {
      setDownloadError(formatApiErrorForDisplay(err));
    } finally {
      setDownloadingLatest(false);
    }
  }

  async function handleDownloadPartial(jobId: number) {
    setDownloadError(null);
    setDownloadingPartial(true);
    try {
      await api.downloadPartialDocx(
        courseId,
        jobId,
        `course_${courseId}_job_${jobId}_partial.docx`,
      );
    } catch (err) {
      setDownloadError(formatApiErrorForDisplay(err));
    } finally {
      setDownloadingPartial(false);
    }
  }

  if (invalidId) {
    return <p className="text-sm text-red-600 dark:text-red-400">Invalid course link.</p>;
  }

  if (loading) {
    return <p className="text-sm text-muted">Loading...</p>;
  }

  if (error || !course) {
    return <p className="text-sm text-red-600 dark:text-red-400">{error ?? "Course not found"}</p>;
  }

  const latestVersion =
    versions.length > 0
      ? versions.reduce((latest, v) => (v.version_number > latest.version_number ? v : latest))
      : null;
  const showReportTab = false; // V1: Teleprompter DOCX only — no report surface

  const providerNeedsAttention = diagnostics?.ai_provider === "anthropic" && !diagnostics.ai_provider_ready;
  const providerLabel =
    diagnostics?.ai_provider === "anthropic"
      ? diagnostics.ai_provider_ready
        ? "Anthropic"
        : "Anthropic (not fully configured)"
      : "Fake provider";

  const sourceCategoryCounts = sources.reduce<Record<SourceCategory, number>>((acc, source) => {
    acc[source.source_category] = (acc[source.source_category] ?? 0) + 1;
    return acc;
  }, {} as Record<SourceCategory, number>);
  const sourceCategorySummary = Object.entries(sourceCategoryCounts)
    .map(([category, count]) => `${count} ${SOURCE_CATEGORY_LABELS[category as SourceCategory]}`)
    .join(", ");

  const displayStatus = deriveCourseDisplayStatus(
    versions.length > 0,
    currentJob?.status ?? null,
  );

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={course.title} description={course.audience} />
        <StatusBadge
          label={COURSE_DISPLAY_STATUS_LABEL[displayStatus]}
          tone={COURSE_DISPLAY_STATUS_TONE[displayStatus]}
        />
      </div>

      {sourceFlushNotice ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm" role="alert">
          <p className="font-medium text-foreground">Sources need attention</p>
          <p className="mt-1 text-foreground">{sourceFlushNotice}</p>
          <button
            type="button"
            className="btn-ghost mt-2 text-xs"
            onClick={() => setSourceFlushNotice(null)}
          >
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <SectionPanel label="Inputs" description="Brief, sources, rules, preset" framed>
          <Card className="flex flex-col gap-4">
            {editingBrief ? (
              <>
                <CourseForm
                  initialValues={courseToFormValues(course)}
                  submitLabel="Save changes"
                  onSubmit={handleBriefSubmit}
                />
                <button
                  onClick={() => setEditingBrief(false)}
                  className="w-fit rounded-full border border-border px-4 py-1.5 text-sm hover:bg-surface-muted"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <div className="flex flex-col gap-3">
                  <Field label="Outcome" value={course.outcome} />
                  {course.special_notes ? (
                    <Field label="Special notes" value={course.special_notes} />
                  ) : null}
                  <Field
                    label="Structure"
                    value={STRUCTURE_MODE_LABELS[course.structure_mode] ?? course.structure_mode}
                  />
                  {course.manual_map_text ? (
                    <Field label="Manual course map" value={course.manual_map_text} />
                  ) : null}
                  <Field
                    label="Output level"
                    value={
                      EXPLANATION_LEVEL_LABELS[course.explanation_level] ?? course.explanation_level
                    }
                  />
                  <div>
                    <p className="text-xs text-muted">Sources</p>
                    <p className="text-sm">
                      {sources.length === 0
                        ? "None added yet"
                        : `${sources.length} added (${sourceCategorySummary})`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted">Admin knowledge</p>
                    <p className="text-sm">
                      {activeKnowledgeCount === null
                        ? "-"
                        : `${activeKnowledgeCount} active rule set${activeKnowledgeCount === 1 ? "" : "s"}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted">Generation preset</p>
                    <p className="text-sm">{GENERATION_PRESET_LABELS[course.generation_preset]}</p>
                  </div>
                </div>
                <button
                  onClick={() => setEditingBrief(true)}
                  className="btn-secondary w-fit"
                >
                  Edit brief
                </button>
              </>
            )}
          </Card>
        </SectionPanel>

        <SectionPanel label="Generate" description="Work / status only" framed>
          <Card className="flex flex-col gap-4">
            <GeneratePanel
              key={`${course.id}:${course.updated_at}`}
              courseId={courseId}
              onVersionCreated={loadAll}
              onJobUpdate={setCurrentJob}
              initialQualityMode={course.generation_quality_mode ?? "premium"}
              initialWebResearchMode={
                course.web_research_mode ?? "autonomous_gap_fill"
              }
              addressForm={course.address_form}
              presenterLanguage={course.student_language}
              presenterDialect={course.spoken_variety}
            />
            {currentJob?.provenance_summary ? (
              <details className="rounded-md border border-border bg-surface-muted/30 px-3 py-2 text-xs text-muted">
                <summary className="cursor-pointer font-medium text-foreground">
                  This run used (provenance)
                </summary>
                <p className="mt-2 text-foreground">{currentJob.provenance_summary}</p>
                {currentJob.sources_run_summary ? (
                  <p className="mt-1">Sources: {currentJob.sources_run_summary}</p>
                ) : null}
                {currentJob.generation_quality_mode ? (
                  <p className="mt-1">
                    Mode: {currentJob.generation_quality_mode}
                    {currentJob.web_research_mode
                      ? ` · research ${currentJob.web_research_mode}`
                      : ""}
                  </p>
                ) : null}
              </details>
            ) : null}
          </Card>
        </SectionPanel>

        <SectionPanel label="Output" description="Teleprompter DOCX" framed>
          <Card
            className={`flex flex-col gap-4 ${
              currentJob?.status === "completed" && latestVersion
                ? "ring-1 ring-accent/40"
                : ""
            }`}
          >
            {latestVersion ? (
              <>
                {currentJob?.status === "completed" ? (
                  <p className="text-xs uppercase tracking-wide text-muted">
                    Presentation ready
                  </p>
                ) : null}
                <StatusBadge label="DOCX ready" tone="success" />
                {currentJob?.architecture_summary ? (
                  <p className="text-sm text-foreground">{currentJob.architecture_summary}</p>
                ) : null}
                {currentJob?.grounding_confidence ? (
                  <p className="text-xs text-muted">
                    Grounding confidence: {currentJob.grounding_confidence}
                    {currentJob.improve_next_tip
                      ? ` · ${currentJob.improve_next_tip}`
                      : ""}
                  </p>
                ) : null}
                <Field label="Last generated" value={new Date(latestVersion.created_at).toLocaleString()} />
                <button
                  onClick={() => handleDownloadLatest(latestVersion)}
                  disabled={
                    downloadingLatest || currentJob?.current_stage === "exporting"
                  }
                  className="btn-primary w-fit text-base"
                >
                  {currentJob?.current_stage === "exporting"
                    ? "Exporting… download when ready"
                    : downloadingLatest
                      ? "Preparing download..."
                      : "Download Teleprompter DOCX"}
                </button>
              </>
            ) : (
              <EmptyState
                title="No DOCX generated yet"
                description="Use Generate in the center panel to create the first version."
              />
            )}

            {currentJob?.partial_docx_path ? (
              <div className="flex flex-col gap-2 border-t border-border pt-4">
                <StatusBadge label="Partial draft available" tone="warning" />
                <button
                  onClick={() => handleDownloadPartial(currentJob.id)}
                  disabled={
                    downloadingPartial || currentJob?.current_stage === "exporting"
                  }
                  className="btn-secondary w-fit"
                >
                  {downloadingPartial ? "Preparing download..." : "Download Partial DOCX"}
                </button>
              </div>
            ) : currentJob &&
              (currentJob.status === "partial" || currentJob.status === "failed") ? (
              <p className="border-t border-border pt-4 text-xs text-muted">
                No partial draft was saved for this run.
              </p>
            ) : null}

            {downloadError ? <p className="text-sm text-red-700">{downloadError}</p> : null}

            <div className="flex items-center gap-2">
              <Field label="Provider" value={providerLabel} />
              {providerNeedsAttention ? (
                <StatusBadge label="Needs configuration" tone="warning" />
              ) : null}
            </div>

            {courseUsage ? (
              <Field
                label="Estimated course usage"
                value={
                  courseUsage.events === 0
                    ? "No usage events yet"
                    : `$${courseUsage.cost.toFixed(4)} · ${courseUsage.events} request(s)`
                }
              />
            ) : null}

            <p className="text-xs text-muted">
              Final DOCX is a teleprompter-ready lecturer script - spoken script only, no internal
              notes in the export.
            </p>
          </Card>
        </SectionPanel>
      </div>

      <div className="flex flex-col gap-4">
        <CourseTabs active={tab} onChange={setTab} showReportTab={showReportTab} />

        {tab === "sources" ? (
          <div className="flex flex-col gap-4">
            <SourceTable
              sources={sources}
              onDelete={handleDeleteSource}
              onCategoryChange={handleSourceCategoryChange}
              onIncludeChange={handleSourceIncludeChange}
              onReprocess={handleSourceReprocess}
              onPreview={handleSourcePreview}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <SourceUploadForm onUpload={handleUpload} />
              <NotesSourceForm onAdd={handleAddNote} />
            </div>
          </div>
        ) : null}

        {tab === "versions" ? <VersionTable versions={versions} /> : null}

        {tab === "report" ? (
          latestVersion?.report_text ? (
            <Card>
              <pre className="text-sm whitespace-pre-wrap font-sans">{latestVersion.report_text}</pre>
            </Card>
          ) : (
            <EmptyState
              title="No report yet"
              description="Generate the course first to see a full report here."
            />
          )
        ) : null}
      </div>
    </div>
  );
}
