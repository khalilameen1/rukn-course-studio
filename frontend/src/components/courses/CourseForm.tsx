"use client";

import { useState } from "react";
import type { Course, ExplanationLevel, GenerationPreset, StructureMode } from "@/lib/types";
import SectionPanel from "@/components/ui/SectionPanel";
import { DEFAULT_GENERATION_PRESET, GENERATION_PRESET_HELPERS, GENERATION_PRESET_OPTIONS } from "@/lib/generationPresets";

export interface CourseFormValues {
  title: string;
  audience: string;
  outcome: string;
  special_notes: string;
  structure_mode: StructureMode;
  manual_map_text: string;
  explanation_level: ExplanationLevel;
  generation_preset: GenerationPreset;
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
    generation_preset: course.generation_preset,
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
  generation_preset: DEFAULT_GENERATION_PRESET,
};

const FIELD_CLASS = "field-input";

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
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <SectionPanel label="Course basics">
        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            required
            value={values.title}
            onChange={(e) => update("title", e.target.value)}
            placeholder="e.g. Intro to Excel Formulas"
            className={FIELD_CLASS}
          />
        </label>
      </SectionPanel>

      <SectionPanel label="Target learner">
        <label className="flex flex-col gap-1 text-sm">
          Audience
          <input
            required
            value={values.audience}
            onChange={(e) => update("audience", e.target.value)}
            placeholder="e.g. New hires with no spreadsheet experience"
            className={FIELD_CLASS}
          />
        </label>
      </SectionPanel>

      <SectionPanel label="Desired outcome">
        <label className="flex flex-col gap-1 text-sm">
          Outcome
          <input
            required
            value={values.outcome}
            onChange={(e) => update("outcome", e.target.value)}
            placeholder="e.g. Can build a basic budget sheet using formulas"
            className={FIELD_CLASS}
          />
        </label>
      </SectionPanel>

      <SectionPanel label="Optional notes">
        <label className="flex flex-col gap-1 text-sm">
          Special notes
          <textarea
            rows={3}
            value={values.special_notes}
            onChange={(e) => update("special_notes", e.target.value)}
            className={FIELD_CLASS}
          />
        </label>
      </SectionPanel>

      <SectionPanel label="Structure & map">
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Structure mode
            <select
              value={values.structure_mode}
              onChange={(e) => update("structure_mode", e.target.value as StructureMode)}
              className={FIELD_CLASS}
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
              className={`${FIELD_CLASS} font-mono text-xs`}
            />
          </label>
        </div>
      </SectionPanel>

      <SectionPanel label="Output">
        <label className="flex flex-col gap-1 text-sm">
          Explanation level
          <select
            value={values.explanation_level}
            onChange={(e) => update("explanation_level", e.target.value as ExplanationLevel)}
            className={FIELD_CLASS}
          >
            <option value="final_only">Final only (just the DOCX)</option>
            <option value="short_summary">Short summary</option>
            <option value="full_report">Full report</option>
          </select>
          <span className="text-xs text-muted">
            The exported DOCX is a teleprompter-ready lecturer script.
          </span>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Generation preset
          <select
            value={values.generation_preset}
            onChange={(e) => update("generation_preset", e.target.value as GenerationPreset)}
            className={FIELD_CLASS}
          >
            {GENERATION_PRESET_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} title={opt.helper}>
                {opt.label}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted">
            {GENERATION_PRESET_HELPERS[values.generation_preset]}
          </span>
        </label>
      </SectionPanel>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <button
        type="submit"
        disabled={submitting}
        className="btn-primary w-fit disabled:opacity-60"
      >
        {submitting ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
