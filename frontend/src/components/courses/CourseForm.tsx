"use client";

import { useState } from "react";
import type { Course, ExplanationLevel, StructureMode } from "@/lib/types";

export interface CourseFormValues {
  title: string;
  audience: string;
  outcome: string;
  special_notes: string;
  structure_mode: StructureMode;
  manual_map_text: string;
  explanation_level: ExplanationLevel;
}

export function courseToFormValues(course: Course): CourseFormValues {
  return {
    title: course.title,
    audience: course.audience,
    outcome: course.outcome,
    special_notes: course.special_notes ?? "",
    structure_mode: course.structure_mode,
    manual_map_text: course.manual_map_text ?? "",
    explanation_level: course.explanation_level,
  };
}

const EMPTY_VALUES: CourseFormValues = {
  title: "",
  audience: "",
  outcome: "",
  special_notes: "",
  structure_mode: "connected_no_modules",
  manual_map_text: "",
  explanation_level: "final_only",
};

export default function CourseForm({
  initialValues,
  submitLabel = "Create Course",
  onSubmit,
}: {
  initialValues?: CourseFormValues;
  submitLabel?: string;
  onSubmit: (values: CourseFormValues) => Promise<void>;
}) {
  const [values, setValues] = useState<CourseFormValues>(initialValues ?? EMPTY_VALUES);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof CourseFormValues>(field: K, value: CourseFormValues[K]) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(values);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        Title
        <input
          required
          value={values.title}
          onChange={(e) => update("title", e.target.value)}
          placeholder="e.g. Intro to Excel Formulas"
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Audience
        <input
          required
          value={values.audience}
          onChange={(e) => update("audience", e.target.value)}
          placeholder="e.g. New hires with no spreadsheet experience"
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Outcome
        <input
          required
          value={values.outcome}
          onChange={(e) => update("outcome", e.target.value)}
          placeholder="e.g. Can build a basic budget sheet using formulas"
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Special notes (optional)
        <textarea
          rows={3}
          value={values.special_notes}
          onChange={(e) => update("special_notes", e.target.value)}
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Structure mode
        <select
          value={values.structure_mode}
          onChange={(e) => update("structure_mode", e.target.value as StructureMode)}
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        >
          <option value="connected_no_modules">Connected, no modules</option>
          <option value="connected_modules_with_bridge_projects">
            Connected modules with bridge projects
          </option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Manual course map (optional)
        <textarea
          rows={4}
          value={values.manual_map_text}
          onChange={(e) => update("manual_map_text", e.target.value)}
          placeholder="Leave empty to let the system build the course map"
          className="rounded border border-black/15 px-2 py-1 font-mono text-xs dark:border-white/20 dark:bg-transparent"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        Explanation level
        <select
          value={values.explanation_level}
          onChange={(e) => update("explanation_level", e.target.value as ExplanationLevel)}
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        >
          <option value="final_only">Final only (just the DOCX)</option>
          <option value="short_summary">Short summary</option>
          <option value="full_report">Full report</option>
        </select>
      </label>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <button
        type="submit"
        disabled={submitting}
        className="w-fit rounded-full bg-foreground px-5 py-2 text-sm text-background disabled:opacity-60"
      >
        {submitting ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
