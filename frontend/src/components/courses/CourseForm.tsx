"use client";

import { useState } from "react";
import type {
  Course,
  ExplanationLevel,
  GenerationPreset,
  GenerationQualityMode,
  StructureMode,
  TargetMarket,
} from "@/lib/types";
import SectionPanel from "@/components/ui/SectionPanel";
import {
  DEFAULT_GENERATION_PRESET,
  GENERATION_PRESET_HELPERS,
  GENERATION_PRESET_OPTIONS,
} from "@/lib/generationPresets";

export interface CourseFormValues {
  title: string;
  audience: string;
  outcome: string;
  course_domain: string;
  special_notes: string;
  structure_mode: StructureMode;
  manual_map_text: string;
  explanation_level: ExplanationLevel;
  generation_preset: GenerationPreset;
  generation_quality_mode: GenerationQualityMode;
  target_market: TargetMarket;
}

export function courseToFormValues(course: Course): CourseFormValues {
  return {
    title: course.title,
    audience: course.audience,
    outcome: course.outcome,
    course_domain: course.course_domain ?? "",
    special_notes: course.special_notes ?? "",
    structure_mode: course.structure_mode,
    manual_map_text: course.manual_map_text ?? "",
    explanation_level: course.explanation_level,
    generation_preset: course.generation_preset,
    generation_quality_mode: course.generation_quality_mode ?? "premium",
    target_market: course.target_market ?? "egypt",
  };
}

export const EMPTY_COURSE_VALUES: CourseFormValues = {
  title: "",
  audience: "",
  outcome: "",
  course_domain: "",
  special_notes: "",
  structure_mode: "connected_no_modules",
  manual_map_text: "",
  explanation_level: "final_only",
  generation_preset: DEFAULT_GENERATION_PRESET,
  generation_quality_mode: "premium",
  target_market: "egypt",
};

const FIELD_CLASS = "field-input";

/** Course Brief section only — sources and map live on New Course page. */
export default function CourseForm({
  initialValues,
  values,
  onChange,
  submitLabel = "Save Course",
  onSubmit,
  hideMap = false,
  hideSubmit = false,
}: {
  initialValues?: CourseFormValues;
  values?: CourseFormValues;
  onChange?: (values: CourseFormValues) => void;
  submitLabel?: string;
  onSubmit?: (values: CourseFormValues) => Promise<void>;
  hideMap?: boolean;
  hideSubmit?: boolean;
}) {
  const [internal, setInternal] = useState<CourseFormValues>(
    values ?? initialValues ?? EMPTY_COURSE_VALUES,
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = values ?? internal;

  function setValues(next: CourseFormValues) {
    if (onChange) onChange(next);
    else setInternal(next);
  }

  function update<K extends keyof CourseFormValues>(field: K, value: CourseFormValues[K]) {
    setValues({ ...current, [field]: value });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!onSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(current);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <SectionPanel label="A. Course Brief">
        <p className="mb-3 text-xs text-muted">
          Basic information for this course. Global ROKN rules live in Admin Knowledge —
          not here.
        </p>
        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            required
            value={current.title}
            onChange={(e) => update("title", e.target.value)}
            placeholder="e.g. Intro to Excel Formulas"
            className={FIELD_CLASS}
          />
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Target learner
          <input
            required
            value={current.audience}
            onChange={(e) => update("audience", e.target.value)}
            placeholder="e.g. New hires with no spreadsheet experience"
            className={FIELD_CLASS}
          />
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Course goal / promise
          <input
            required
            value={current.outcome}
            onChange={(e) => update("outcome", e.target.value)}
            placeholder="e.g. Can build a basic budget sheet using formulas"
            className={FIELD_CLASS}
          />
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Course domain
          <input
            value={current.course_domain}
            onChange={(e) => update("course_domain", e.target.value)}
            placeholder="e.g. meta_ads, excel, copywriting"
            className={FIELD_CLASS}
          />
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Target market
          <select
            value={current.target_market}
            onChange={(e) => update("target_market", e.target.value as TargetMarket)}
            className={FIELD_CLASS}
          >
            <option value="egypt">Egypt (default)</option>
            <option value="arab_market">Arab market</option>
            <option value="global">Global</option>
            <option value="custom">Custom (follow special notes)</option>
          </select>
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Generation quality
          <select
            value={current.generation_quality_mode}
            onChange={(e) =>
              update("generation_quality_mode", e.target.value as GenerationQualityMode)
            }
            className={FIELD_CLASS}
          >
            <option value="premium">Premium (full quality pipeline)</option>
            <option value="preview">Preview (cheaper direction test)</option>
          </select>
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Structure mode
          <select
            value={current.structure_mode}
            onChange={(e) => update("structure_mode", e.target.value as StructureMode)}
            className={FIELD_CLASS}
          >
            <option value="connected_no_modules">Connected, no modules</option>
            <option value="connected_modules_with_bridge_projects">
              Connected modules with bridge projects
            </option>
          </select>
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Special notes
          <textarea
            rows={3}
            value={current.special_notes}
            onChange={(e) => update("special_notes", e.target.value)}
            className={FIELD_CLASS}
          />
        </label>
        <label className="mt-4 flex flex-col gap-1 text-sm">
          Generation preset
          <select
            value={current.generation_preset}
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
            {GENERATION_PRESET_HELPERS[current.generation_preset]}
          </span>
        </label>
      </SectionPanel>

      {!hideMap ? (
        <SectionPanel label="C. Course Map">
          <p className="mb-3 text-xs text-muted">
            Write the course map yourself, or generate it from the course brief and course
            sources. This map belongs only to this course.
          </p>
          <label className="flex flex-col gap-1 text-sm">
            Course map
            <textarea
              rows={10}
              value={current.manual_map_text}
              onChange={(e) => update("manual_map_text", e.target.value)}
              placeholder="Leave empty to auto-build during full course generation"
              className={`${FIELD_CLASS} font-mono text-xs`}
            />
          </label>
        </SectionPanel>
      ) : null}

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {!hideSubmit && onSubmit ? (
        <button
          type="submit"
          disabled={submitting}
          className="btn-primary w-fit disabled:opacity-60"
        >
          {submitting ? "Saving..." : submitLabel}
        </button>
      ) : null}
    </form>
  );
}
