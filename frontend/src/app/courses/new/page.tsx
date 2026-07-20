"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { EMPTY_COURSE_VALUES, type CourseFormValues } from "@/components/courses/CourseForm";
import ActionError, { actionErrorFromUnknown } from "@/components/ui/ActionError";
import { api, ApiError, formatUploadErrorForDisplay } from "@/lib/api";
import BriefWorkspace from "@/components/courses/new/BriefWorkspace";
import CourseMapWorkspace from "@/components/courses/new/CourseMapWorkspace";
import NewCourseStepBar from "@/components/courses/new/NewCourseStepBar";
import NotesChatPanel, { type ChatMessage } from "@/components/courses/new/NotesChatPanel";
import PendingFilesPanel, { type PendingFileItem } from "@/components/courses/new/PendingFilesPanel";
import ReadinessPanel from "@/components/courses/new/ReadinessPanel";
import SourceDropzone from "@/components/courses/new/SourceDropzone";
import {
  categoryForIntent,
  type SourceIntentId,
} from "@/lib/sourceIntentOptions";
import type { Priority, SourceCategory } from "@/lib/types";
import {
  clearNewCourseDraft,
  draftHasUnsavedWork,
  loadNewCourseDraft,
  saveNewCourseDraft,
  type PendingPasteDraft,
} from "@/lib/newCourseDraft";

type PendingPaste = {
  id: string;
  kind: "paste";
  text: string;
  title: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
};

type PendingFile = PendingFileItem;

function briefIsComplete(values: CourseFormValues): boolean {
  return Boolean(values.title.trim() && values.audience.trim() && values.outcome.trim());
}

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export default function NewCoursePage() {
  const router = useRouter();
  const pasteSectionRef = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<CourseFormValues>(EMPTY_COURSE_VALUES);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [savedMapText, setSavedMapText] = useState("");
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [pendingPastes, setPendingPastes] = useState<PendingPaste[]>([]);
  const [restoredPastes, setRestoredPastes] = useState<(PendingPasteDraft & { id: string })[]>([]);
  const [pasteText, setPasteText] = useState("");
  const [pasteTitle, setPasteTitle] = useState("");
  const [fileIntent, setFileIntent] = useState<SourceIntentId>("classify");
  const [pasteIntent, setPasteIntent] = useState<SourceIntentId>("knowledge");
  const [filePriority, setFilePriority] = useState<Priority>("medium");
  const [includeGen, setIncludeGen] = useState(true);
  const [mapStatus, setMapStatus] = useState<string | null>(null);
  const [error, setError] = useState<ReturnType<typeof actionErrorFromUnknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [allowLeave, setAllowLeave] = useState(false);
  const [draftSavedNotice, setDraftSavedNotice] = useState<string | null>(null);
  const stableRequestId = useId();
  const createIdempotencyKeyRef = useRef<string>(`new-course-${stableRequestId}`);

  useEffect(() => {
    const draft = loadNewCourseDraft();
    if (!draft) return;
    // Restore the one persisted client draft after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setValues(draft.values);
    setCourseId(draft.courseId);
    setSavedMapText(draft.values.manual_map_text ?? "");
    setRestoredPastes(
      draft.pendingPastes.map((item, i) => ({
        ...item,
        id: `restored-${i}-${item.title}`,
      })),
    );
  }, []);

  useEffect(() => {
    saveNewCourseDraft({
      values,
      courseId,
      pendingPastes: [
        ...restoredPastes.map((item) => ({
          kind: "paste" as const,
          text: item.text,
          title: item.title,
          source_category: item.source_category,
          priority: item.priority,
          include_in_generation: item.include_in_generation,
        })),
        ...pendingPastes.map((item) => ({
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
  }, [values, courseId, pendingPastes, restoredPastes]);

  useEffect(() => {
    const hasWork = draftHasUnsavedWork({
      values,
      courseId,
      pendingPastes: restoredPastes,
      pendingFilesCount: pendingFiles.length,
    });
    if (!hasWork || allowLeave) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [values, courseId, pendingFiles, restoredPastes, allowLeave]);

  const chatMessages: ChatMessage[] = useMemo(
    () => [
      ...restoredPastes.map((item) => ({
        id: item.id,
        title: item.title,
        text: item.text,
        source_category: item.source_category,
        priority: item.priority,
        include_in_generation: item.include_in_generation,
        restored: true,
      })),
      ...pendingPastes.map((item) => ({
        id: item.id,
        title: item.title,
        text: item.text,
        source_category: item.source_category,
        priority: item.priority,
        include_in_generation: item.include_in_generation,
      })),
    ],
    [restoredPastes, pendingPastes],
  );

  const sourcesCount = pendingFiles.length + chatMessages.length;
  const briefComplete = briefIsComplete(values);
  const canSubmit = briefComplete && !busy;
  const mapStarted = Boolean(values.manual_map_text.trim() || mapStatus);
  const mapUnsaved = values.manual_map_text.trim() !== savedMapText.trim();
  const mapSaved = Boolean(savedMapText.trim()) && !mapUnsaved;

  const nextStep = useMemo(() => {
    if (!briefComplete) return "Add a title, target learner, and course goal.";
    if (busy && mapStatus) return "Wait while the course map is being prepared.";
    if (mapUnsaved && values.manual_map_text.trim()) return "Save the course map or continue editing.";
    if (courseId) return "Open the course workspace to start generation.";
    return "Save draft or create the course to continue.";
  }, [briefComplete, busy, mapStatus, mapUnsaved, values.manual_map_text, courseId]);

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
        primary_course_family: values.primary_course_family,
        web_research_mode: values.web_research_mode,
        student_language: values.student_language,
        spoken_variety: values.spoken_variety,
        address_form: values.address_form,
      });
      return courseId;
    }
    const course = await api.createCourse(
      {
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
      },
      {
        idempotencyKey: createIdempotencyKeyRef.current,
      },
    );
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

    for (const item of pendingPastes) {
      await api.addNotesSource(id, {
        text: item.text,
        title: item.title || null,
        source_category: item.source_category,
        priority: item.priority,
        include_in_generation: item.include_in_generation,
      });
    }
    setPendingPastes([]);

    for (const item of pendingFiles) {
      try {
        await api.uploadSource(id, item.file, item.source_category, item.priority, {
          title: item.title || undefined,
          include_in_generation: item.include_in_generation,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          await api.uploadSource(id, item.file, item.source_category, item.priority, {
            title: item.title || undefined,
            include_in_generation: item.include_in_generation,
            force: true,
          });
        } else {
          throw err;
        }
      }
    }
    setPendingFiles([]);
  }

  async function handleSaveDraft() {
    setBusy(true);
    setError(null);
    try {
      if (!briefComplete) {
        throw new Error("Add a course title, target learner, and goal before saving.");
      }
      const id = await ensureCourse();
      await flushPendingSources(id);
      if (values.manual_map_text.trim()) {
        await api.updateCourse(id, { manual_map_text: values.manual_map_text });
        setSavedMapText(values.manual_map_text);
      }
      setDraftSavedNotice("Draft saved — you can leave and return later.");
    } catch (err) {
      setError(actionErrorFromUnknown(err, "Could not save draft"));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      if (!briefComplete) {
        throw new Error("Title, target learner, and course goal are required.");
      }
      const id = await ensureCourse();
      try {
        await flushPendingSources(id);
      } catch (sourceErr) {
        // Course row already exists — open the workspace so sources can be
        // re-uploaded. Surface the failure via query flag on the detail page.
        setAllowLeave(true);
        clearNewCourseDraft();
        const msg = formatUploadErrorForDisplay(sourceErr);
        router.push(
          `/courses/${id}?sources_failed=1&reason=${encodeURIComponent(msg.slice(0, 180))}`,
        );
        return;
      }
      if (values.manual_map_text.trim()) {
        await api.updateCourse(id, { manual_map_text: values.manual_map_text });
      }
      setAllowLeave(true);
      clearNewCourseDraft();
      router.push(`/courses/${id}`);
    } catch (err) {
      const details = actionErrorFromUnknown(err, "Could not open course");
      if (courseId) {
        setError({
          ...details,
          nextStep: `A draft course already exists (#${courseId}). Open it from Courses, upload sources there, then generate.`,
        });
      } else {
        setError(details);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveMap() {
    setBusy(true);
    setError(null);
    try {
      if (!briefComplete) throw new Error("Complete the brief before saving the map.");
      const id = await ensureCourse();
      await api.updateCourse(id, { manual_map_text: values.manual_map_text || null });
      setSavedMapText(values.manual_map_text);
      setDraftSavedNotice("Course map saved.");
    } catch (err) {
      setError(actionErrorFromUnknown(err, "Could not save course map"));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateMap() {
    setBusy(true);
    setError(null);
    try {
      if (!briefComplete) {
        throw new Error("Fill the Course Brief before generating a map.");
      }
      if (!courseId) setMapStatus("Creating draft course…");
      const id = await ensureCourse();
      setMapStatus("Reading course brief…");
      await flushPendingSources(id);
      setMapStatus("Checking course sources…");
      setMapStatus("Building course map…");
      const preview = await api.mapPreview(id, {
        generation_quality_mode: values.generation_quality_mode,
        web_research_mode: values.web_research_mode,
        address_form: values.address_form,
        presenter_language: values.student_language,
        presenter_dialect: values.spoken_variety,
      });
      setMapStatus("Reviewing map…");
      const map = preview.map_text ?? "";
      setValues((v) => ({ ...v, manual_map_text: map }));
      setSavedMapText(map);
      setMapStatus("Map ready to edit — review below before full generation.");
    } catch (err) {
      setError(actionErrorFromUnknown(err, "Could not generate course map"));
      setMapStatus(null);
    } finally {
      setBusy(false);
    }
  }

  function addFile(file: File) {
    setPendingFiles((prev) => [
      ...prev,
      {
        id: newId("file"),
        kind: "file",
        file,
        title: file.name,
        source_category: categoryForIntent(fileIntent),
        priority: filePriority,
        include_in_generation: includeGen,
      },
    ]);
  }

  function sendPaste() {
    if (!pasteText.trim()) return;
    setPendingPastes((prev) => [
      ...prev,
      {
        id: newId("paste"),
        kind: "paste",
        text: pasteText.trim(),
        title: pasteTitle.trim() || "Pasted source",
        source_category: categoryForIntent(pasteIntent),
        priority: filePriority,
        include_in_generation: includeGen,
      },
    ]);
    setPasteText("");
    setPasteTitle("");
  }

  function removeChatMessage(id: string) {
    setRestoredPastes((prev) => prev.filter((item) => item.id !== id));
    setPendingPastes((prev) => prev.filter((item) => item.id !== id));
  }

  function scrollToPaste() {
    pasteSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 pb-4">
      <header className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">Create course</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">New course workspace</h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Build your brief, add sources, shape the map, then open the course to generate a
            teleprompter DOCX.
          </p>
        </div>
        <NewCourseStepBar
          briefDone={briefComplete}
          sourcesCount={sourcesCount}
          mapStarted={mapStarted}
          readyToOpen={Boolean(courseId && briefComplete)}
        />
      </header>

      <div className="grid gap-6 lg:grid-cols-12 lg:items-start">
        <div className="flex flex-col gap-6 lg:col-span-4">
          <ReadinessPanel
            briefComplete={briefComplete}
            sourcesReady={sourcesCount}
            sourcesPending={pendingFiles.length + pendingPastes.length}
            mapStatus={
              !values.manual_map_text.trim()
                ? "empty"
                : mapUnsaved
                  ? "unsaved"
                  : mapStatus?.includes("ready")
                    ? "generated"
                    : "saved"
            }
            mapUnsaved={mapUnsaved}
            canCreate={canSubmit}
            nextStep={nextStep}
            disabledReason={!briefComplete ? "Add a course title first" : undefined}
          />
          <BriefWorkspace values={values} onChange={setValues} disabled={busy} />
        </div>

        <div className="flex flex-col gap-6 lg:col-span-8">
          <div className="rounded-2xl border border-border bg-surface p-5 shadow-[var(--shadow-sm)] sm:p-6">
            <SourceDropzone
              disabled={busy}
              fileIntent={fileIntent}
              filePriority={filePriority}
              includeGen={includeGen}
              onFileIntentChange={setFileIntent}
              onFilePriorityChange={setFilePriority}
              onIncludeGenChange={setIncludeGen}
              onFileSelected={addFile}
              onPasteInstead={scrollToPaste}
            />
            <div className="my-6 border-t border-border" />
            <PendingFilesPanel
              files={pendingFiles}
              disabled={busy}
              onRemove={(id) => setPendingFiles((prev) => prev.filter((f) => f.id !== id))}
            />
            <div className="my-6 border-t border-border" />
            <div ref={pasteSectionRef}>
              <NotesChatPanel
                sectionId="paste-sources"
                messages={chatMessages}
                disabled={busy}
                draftText={pasteText}
                draftTitle={pasteTitle}
                pasteIntent={pasteIntent}
                filePriority={filePriority}
                includeGen={includeGen}
                onDraftTextChange={setPasteText}
                onDraftTitleChange={setPasteTitle}
                onPasteIntentChange={setPasteIntent}
                onFilePriorityChange={setFilePriority}
                onIncludeGenChange={setIncludeGen}
                onSend={sendPaste}
                onRemove={removeChatMessage}
              />
            </div>
          </div>
        </div>
      </div>

      <CourseMapWorkspace
        mapText={values.manual_map_text}
        mapStatus={mapStatus}
        mapUnsaved={mapUnsaved}
        mapSaved={mapSaved}
        disabled={busy}
        canGenerate={canSubmit}
        busy={busy}
        onMapChange={(text) => setValues((v) => ({ ...v, manual_map_text: text }))}
        onGenerateMap={handleGenerateMap}
        onSaveMap={handleSaveMap}
        onClearMap={() => {
          setValues((v) => ({ ...v, manual_map_text: "" }));
          setSavedMapText("");
        }}
      />

      <div className="nc-action-bar flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          {error ? (
            <ActionError {...error} />
          ) : draftSavedNotice ? (
            <p className="text-sm text-accent">{draftSavedNotice}</p>
          ) : (
            <p className="text-sm text-muted">
              {courseId
                ? "Draft saved in this browser — course exists in the database."
                : "Draft auto-saves in this browser session."}
              {!briefComplete ? " Add a course title, learner, and goal to continue." : null}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/courses" className="btn-ghost text-sm">
            Cancel
          </Link>
          <button
            type="button"
            className="btn-secondary shrink-0"
            disabled={!briefComplete || busy}
            title={!briefComplete ? "Add a course title first" : undefined}
            onClick={handleSaveDraft}
          >
            {busy ? "Saving…" : "Save draft"}
          </button>
          <button
            type="button"
            className="btn-primary shrink-0 px-6"
            disabled={!canSubmit}
            title={!briefComplete ? "Add a course title first" : busy ? "Wait for the current action" : undefined}
            onClick={handleCreate}
          >
            {busy ? "Working…" : courseId ? "Open course" : "Create course"}
          </button>
        </div>
      </div>
    </div>
  );
}
