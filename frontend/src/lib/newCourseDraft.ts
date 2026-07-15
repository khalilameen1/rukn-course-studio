import type { CourseFormValues } from "@/components/courses/CourseForm";
import { EMPTY_COURSE_VALUES } from "@/components/courses/CourseForm";
import type { Priority, SourceCategory } from "@/lib/types";

const DRAFT_KEY = "rokn_new_course_draft_v1";

export type PendingFileDraft = {
  kind: "file";
  name: string;
  size: number;
  lastModified: number;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
  title: string;
};

export type PendingPasteDraft = {
  kind: "paste";
  text: string;
  title: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
};

export type NewCourseDraft = {
  values: CourseFormValues;
  courseId: number | null;
  pendingPastes: PendingPasteDraft[];
  savedAt: string;
};

export function loadNewCourseDraft(): NewCourseDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as NewCourseDraft;
    if (!parsed?.values) return null;
    return {
      ...parsed,
      values: { ...EMPTY_COURSE_VALUES, ...parsed.values },
      pendingPastes: parsed.pendingPastes ?? [],
    };
  } catch {
    return null;
  }
}

export function saveNewCourseDraft(draft: NewCourseDraft): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // Quota exceeded or private mode — ignore.
  }
}

export function clearNewCourseDraft(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(DRAFT_KEY);
}

export function draftHasUnsavedWork(draft: {
  values: CourseFormValues;
  courseId: number | null;
  pendingPastes: PendingPasteDraft[];
  pendingFilesCount: number;
}): boolean {
  const v = draft.values;
  return Boolean(
    draft.courseId ||
      draft.pendingPastes.length > 0 ||
      draft.pendingFilesCount > 0 ||
      v.title.trim() ||
      v.audience.trim() ||
      v.outcome.trim() ||
      v.special_notes?.trim() ||
      v.manual_map_text?.trim(),
  );
}
