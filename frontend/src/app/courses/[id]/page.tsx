"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Course, CourseSource, CourseVersion, Priority, SourceCategory } from "@/lib/types";
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

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="whitespace-pre-wrap">{value}</p>
    </div>
  );
}

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const courseId = Number(params.id);

  const [course, setCourse] = useState<Course | null>(null);
  const [sources, setSources] = useState<CourseSource[]>([]);
  const [versions, setVersions] = useState<CourseVersion[]>([]);
  const [tab, setTab] = useState<CourseTab>("brief");
  const [editingBrief, setEditingBrief] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load course");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    // Standard fetch-on-mount; `loadAll` is also reused after mutations
    // (brief edits, generation completing), so it isn't inlined here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
  }, [loadAll]);

  async function handleBriefSubmit(values: CourseFormValues) {
    const updated = await api.updateCourse(courseId, {
      title: values.title,
      audience: values.audience,
      outcome: values.outcome,
      special_notes: values.special_notes || null,
      structure_mode: values.structure_mode,
      manual_map_text: values.manual_map_text || null,
      explanation_level: values.explanation_level,
    });
    setCourse(updated);
    setEditingBrief(false);
  }

  async function handleUpload(file: File, category: SourceCategory, priority: Priority) {
    const created = await api.uploadSource(courseId, file, category, priority);
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
    if (!confirm("Delete this source?")) return;
    await api.deleteSource(courseId, source.id);
    setSources((prev) => prev.filter((s) => s.id !== source.id));
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 text-sm text-zinc-500">Loading...</div>
    );
  }

  if (error || !course) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 text-sm text-red-600">
        {error ?? "Course not found"}
      </div>
    );
  }

  const latestVersion =
    versions.length > 0
      ? versions.reduce((latest, v) => (v.version_number > latest.version_number ? v : latest))
      : null;
  const showReportTab = course.explanation_level === "full_report";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold">{course.title}</h1>
        <p className="mt-1 text-sm text-zinc-500">{course.audience}</p>
      </div>

      <CourseTabs active={tab} onChange={setTab} showReportTab={showReportTab} />

      {tab === "brief" ? (
        editingBrief ? (
          <CourseForm
            initialValues={courseToFormValues(course)}
            submitLabel="Save changes"
            onSubmit={handleBriefSubmit}
          />
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <Field label="Outcome" value={course.outcome} />
            <Field label="Special notes" value={course.special_notes ?? "-"} />
            <Field label="Structure mode" value={course.structure_mode} />
            <Field
              label="Manual course map"
              value={course.manual_map_text ?? "(none - system will build one)"}
            />
            <Field label="Explanation level" value={course.explanation_level} />
            <Field label="Status" value={course.status} />
            <button
              onClick={() => setEditingBrief(true)}
              className="w-fit rounded-full border border-black/15 px-4 py-1.5 dark:border-white/20"
            >
              Edit brief
            </button>
          </div>
        )
      ) : null}

      {tab === "sources" ? (
        <div className="flex flex-col gap-6">
          <SourceTable sources={sources} onDelete={handleDeleteSource} />
          <div className="grid gap-4 sm:grid-cols-2">
            <SourceUploadForm onUpload={handleUpload} />
            <NotesSourceForm onAdd={handleAddNote} />
          </div>
        </div>
      ) : null}

      {tab === "generate" ? (
        <GeneratePanel
          courseId={courseId}
          hasVersion={versions.length > 0}
          explanationLevel={course.explanation_level}
          latestSummary={latestVersion?.summary_text ?? null}
          onVersionCreated={loadAll}
        />
      ) : null}

      {tab === "versions" ? <VersionTable versions={versions} /> : null}

      {tab === "report" ? (
        <div className="flex flex-col gap-2 text-sm">
          {latestVersion?.report_text ? (
            <pre className="whitespace-pre-wrap rounded-lg border border-black/10 p-4 font-sans dark:border-white/10">
              {latestVersion.report_text}
            </pre>
          ) : (
            <p className="text-zinc-500">
              No report yet - generate the course first to see a full report here.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
