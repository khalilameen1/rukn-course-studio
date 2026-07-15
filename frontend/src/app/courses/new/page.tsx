"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import CourseForm, {
  EMPTY_COURSE_VALUES,
  type CourseFormValues,
} from "@/components/courses/CourseForm";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import SectionPanel from "@/components/ui/SectionPanel";
import type { Priority, SourceCategory } from "@/lib/types";
import { SOURCE_CATEGORY_HELPERS, SOURCE_CATEGORY_OPTIONS } from "@/lib/sourceCategories";
import {
  clearNewCourseDraft,
  draftHasUnsavedWork,
  loadNewCourseDraft,
  saveNewCourseDraft,
  type PendingPasteDraft,
} from "@/lib/newCourseDraft";

type PendingFile = {
  kind: "file";
  file: File;
  title: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
};

type PendingPaste = {
  kind: "paste";
  text: string;
  title: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
};

type PendingSource = PendingFile | PendingPaste;

const FIELD = "field-input";

function briefIsComplete(values: CourseFormValues): boolean {
  return Boolean(values.title.trim() && values.audience.trim() && values.outcome.trim());
}

export default function NewCoursePage() {
  const router = useRouter();
  const [values, setValues] = useState<CourseFormValues>(EMPTY_COURSE_VALUES);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingSource[]>([]);
  const [restoredPastes, setRestoredPastes] = useState<PendingPasteDraft[]>([]);
  const [pasteText, setPasteText] = useState("");
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteCategory, setPasteCategory] = useState<SourceCategory>("transcript");
  const [fileCategory, setFileCategory] = useState<SourceCategory>("raw_material");
  const [filePriority, setFilePriority] = useState<Priority>("medium");
  const [includeGen, setIncludeGen] = useState(true);
  const [mapStatus, setMapStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [allowLeave, setAllowLeave] = useState(false);

  useEffect(() => {
    const draft = loadNewCourseDraft();
    if (!draft) return;
    setValues(draft.values);
    setCourseId(draft.courseId);
    setRestoredPastes(draft.pendingPastes);
  }, []);

  useEffect(() => {
    saveNewCourseDraft({
      values,
      courseId,
      pendingPastes: [
        ...restoredPastes,
        ...pending
          .filter((item): item is PendingPaste => item.kind === "paste")
          .map((item) => ({
            kind: "paste" as const,
            text: item.text,
            title: item.title,
            source_category: item.source_category,
            priority: item.priority,
            include_in_generation: item.include_in_generation,
          })),
      ],
      savedAt: new Date().toISOString(),
    });
  }, [values, courseId, pending, restoredPastes]);

  useEffect(() => {
    const hasWork = draftHasUnsavedWork({
      values,
      courseId,
      pendingPastes: restoredPastes,
      pendingFilesCount: pending.filter((item) => item.kind === "file").length,
    });
    if (!hasWork || allowLeave) return;

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [values, courseId, pending, restoredPastes, allowLeave]);

  async function ensureCourse(): Promise<number> {
    if (courseId != null) {
      await api.updateCourse(courseId, {
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
      });
      return courseId;
    }
    const course = await api.createCourse({
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
    });
    setCourseId(course.id);
    return course.id;
  }

  async function flushPendingSources(id: number) {
    for (const item of restoredPastes) {
      await api.addNotesSource(id, {
        text: item.text,
        title: item.title || null,
        source_category: item.source_category,
        priority: item.priority,
        include_in_generation: item.include_in_generation,
      });
    }
    setRestoredPastes([]);

    for (const item of pending) {
      if (item.kind === "file") {
        await api.uploadSource(
          id,
          item.file,
          item.source_category,
          item.priority,
          { title: item.title || undefined, include_in_generation: item.include_in_generation },
        );
      } else {
        await api.addNotesSource(id, {
          text: item.text,
          title: item.title || null,
          source_category: item.source_category,
          priority: item.priority,
          include_in_generation: item.include_in_generation,
        });
      }
    }
    setPending([]);
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      if (!briefIsComplete(values)) {
        throw new Error("Title, target learner, and course goal are required.");
      }
      const id = await ensureCourse();
      await flushPendingSources(id);
      if (values.manual_map_text.trim()) {
        await api.updateCourse(id, { manual_map_text: values.manual_map_text });
      }
      setAllowLeave(true);
      clearNewCourseDraft();
      router.push(`/courses/${id}`);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateMap() {
    setBusy(true);
    setError(null);
    setMapStatus("Saving brief and sources…");
    try {
      if (!briefIsComplete(values)) {
        throw new Error("Fill the Course Brief before generating a map.");
      }
      const id = await ensureCourse();
      await flushPendingSources(id);
      setMapStatus("Building course map (Creator → review → Final Map)…");
      const updated = await api.generateCourseMap(id);
      setValues((v) => ({ ...v, manual_map_text: updated.manual_map_text ?? "" }));
      setMapStatus("Map ready — edit below if needed, then create the course.");
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
      setMapStatus(null);
    } finally {
      setBusy(false);
    }
  }

  function addFile(file: File | null) {
    if (!file) return;
    setPending((p) => [
      ...p,
      {
        kind: "file",
        file,
        title: file.name,
        source_category: fileCategory,
        priority: filePriority,
        include_in_generation: includeGen,
      },
    ]);
  }

  function addPaste() {
    if (!pasteText.trim()) return;
    setPending((p) => [
      ...p,
      {
        kind: "paste",
        text: pasteText,
        title: pasteTitle || "Transcript",
        source_category: pasteCategory,
        priority: filePriority,
        include_in_generation: includeGen,
      },
    ]);
    setPasteText("");
    setPasteTitle("");
  }

  const canSubmit = briefIsComplete(values) && !busy;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader
        title="New Course"
        description="Course Brief, course-specific sources, and an optional Course Map. Final export stays Teleprompter DOCX only."
      />

      <Card>
        <CourseForm
          values={values}
          onChange={setValues}
          hideMap
          hideSubmit
        />
      </Card>

      <Card>
        <SectionPanel label="B. Course Sources / Transcripts">
          <p className="mb-3 text-xs text-muted">
            Upload or paste sources for this specific course. These are never saved into
            Admin Knowledge.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              Upload file (PDF / DOCX / TXT / MD)
              <input
                type="file"
                accept=".docx,.pdf,.txt,.md"
                onChange={(e) => {
                  addFile(e.target.files?.[0] ?? null);
                  e.target.value = "";
                }}
                className="text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              File source type
              <select
                value={fileCategory}
                onChange={(e) => setFileCategory(e.target.value as SourceCategory)}
                className={FIELD}
              >
                {SOURCE_CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <span className="text-xs text-muted">{SOURCE_CATEGORY_HELPERS[fileCategory]}</span>
            </label>
          </div>

          <label className="mt-4 flex flex-col gap-1 text-sm">
            Paste transcript / text
            <input
              value={pasteTitle}
              onChange={(e) => setPasteTitle(e.target.value)}
              placeholder="Source title"
              className={`mb-2 ${FIELD}`}
            />
            <textarea
              rows={4}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              className={FIELD}
              placeholder="Paste transcript or notes…"
            />
          </label>
          <div className="mt-2 flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm">
              Paste source type
              <select
                value={pasteCategory}
                onChange={(e) => setPasteCategory(e.target.value as SourceCategory)}
                className={FIELD}
              >
                {SOURCE_CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Priority
              <select
                value={filePriority}
                onChange={(e) => setFilePriority(e.target.value as Priority)}
                className={FIELD}
              >
                <option value="high">High</option>
                <option value="medium">Normal</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeGen}
                onChange={(e) => setIncludeGen(e.target.checked)}
              />
              Include in generation
            </label>
            <button type="button" className="btn-secondary" onClick={addPaste}>
              Add pasted source
            </button>
          </div>

          {restoredPastes.length + pending.length > 0 ? (
            <ul className="mt-4 space-y-1 text-sm text-muted">
              {restoredPastes.map((item, i) => (
                <li key={`restored-${i}`} className="flex items-center justify-between gap-2">
                  <span>
                    {item.title} · {item.source_category} · {item.priority} · restored draft
                  </span>
                  <button
                    type="button"
                    className="text-xs text-red-600"
                    onClick={() => setRestoredPastes((p) => p.filter((_, j) => j !== i))}
                  >
                    Remove
                  </button>
                </li>
              ))}
              {pending.map((item, i) => (
                <li key={i} className="flex items-center justify-between gap-2">
                  <span>
                    {item.kind === "file" ? item.file.name : item.title} · {item.source_category} ·{" "}
                    {item.priority}
                  </span>
                  <button
                    type="button"
                    className="text-xs text-red-600"
                    onClick={() => setPending((p) => p.filter((_, j) => j !== i))}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </SectionPanel>
      </Card>

      <Card>
        <SectionPanel label="C. Course Map">
          <p className="mb-3 text-xs text-muted">
            Write the course map yourself, or generate it from the course brief and sources.
            This map belongs only to this course.
          </p>
          <textarea
            rows={12}
            value={values.manual_map_text}
            onChange={(e) => setValues((v) => ({ ...v, manual_map_text: e.target.value }))}
            placeholder="Leave empty to auto-build the map during full course generation"
            className={`${FIELD} font-mono text-xs`}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn-secondary"
              disabled={!canSubmit}
              onClick={handleGenerateMap}
            >
              {busy && mapStatus ? "Working…" : "Generate Course Map"}
            </button>
            {mapStatus ? <span className="text-xs text-muted">{mapStatus}</span> : null}
          </div>
        </SectionPanel>
      </Card>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <button
        type="button"
        className="btn-primary w-fit disabled:opacity-60"
        disabled={!canSubmit}
        onClick={handleCreate}
      >
        {busy ? "Saving…" : courseId ? "Save & open course" : "Create Course"}
      </button>
    </div>
  );
}
