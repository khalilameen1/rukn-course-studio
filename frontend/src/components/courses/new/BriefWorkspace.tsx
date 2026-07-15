"use client";

import type { CourseFormValues } from "@/components/courses/CourseForm";
import ChatComposer from "@/components/ui/ChatComposer";
import type { GenerationPreset, GenerationQualityMode, StructureMode, TargetMarket } from "@/lib/types";
import {
  GENERATION_PRESET_HELPERS,
  GENERATION_PRESET_OPTIONS,
} from "@/lib/generationPresets";

export default function BriefWorkspace({
  values,
  onChange,
  disabled,
}: {
  values: CourseFormValues;
  onChange: (values: CourseFormValues) => void;
  disabled?: boolean;
}) {
  function update<K extends keyof CourseFormValues>(field: K, value: CourseFormValues[K]) {
    onChange({ ...values, [field]: value });
  }

  return (
    <section className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-5 shadow-[var(--shadow-sm)] sm:p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-accent">Step 1</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight">Course brief</h2>
        <p className="mt-1 text-sm text-muted">Define the promise and who it is for.</p>
      </div>

      <div>
        <label className="sr-only" htmlFor="nc-title">
          Course title
        </label>
        <input
          id="nc-title"
          required
          disabled={disabled}
          value={values.title}
          onChange={(e) => update("title", e.target.value)}
          placeholder="Course title — e.g. Meta Ads for Egyptian SMEs"
          className="nc-hero-input"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="nc-field-label" htmlFor="nc-audience">
            Target learner
          </label>
          <input
            id="nc-audience"
            required
            disabled={disabled}
            value={values.audience}
            onChange={(e) => update("audience", e.target.value)}
            placeholder="Who is this for?"
            className="field-input"
          />
        </div>
        <div>
          <label className="nc-field-label" htmlFor="nc-domain">
            Domain (optional)
          </label>
          <input
            id="nc-domain"
            disabled={disabled}
            value={values.course_domain}
            onChange={(e) => update("course_domain", e.target.value)}
            placeholder="e.g. meta ads, Excel"
            className="field-input"
          />
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-foreground">Course goal / promise</p>
        <ChatComposer
          id="nc-outcome"
          value={values.outcome}
          onChange={(text) => update("outcome", text)}
          disabled={disabled}
          showSend={false}
          minRows={2}
          maxHeight={200}
          placeholder="What will they be able to do after the course?"
          helper="Write naturally — this shapes the whole course."
        />
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-foreground">Special instructions (optional)</p>
        <ChatComposer
          id="nc-notes"
          value={values.special_notes}
          onChange={(text) => update("special_notes", text)}
          onClear={() => update("special_notes", "")}
          disabled={disabled}
          showSend={false}
          minRows={2}
          maxHeight={180}
          placeholder="Tone, market nuances, things to avoid…"
          helper="Your notes here are treated as direct instructions."
        />
      </div>

      <details className="group rounded-xl border border-border bg-surface-muted/40 px-4 py-3">
        <summary className="cursor-pointer list-none text-sm font-medium text-foreground marker:hidden [&::-webkit-details-marker]:hidden">
          <span className="flex items-center justify-between gap-2">
            Advanced settings
            <span className="text-xs font-normal text-muted group-open:hidden">Structure, preset, market</span>
            <span className="hidden text-xs font-normal text-muted group-open:inline">Hide</span>
          </span>
        </summary>
        <div className="mt-4 grid gap-4 border-t border-border pt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="nc-field-label" htmlFor="nc-market">
                Target market
              </label>
              <select
                id="nc-market"
                disabled={disabled}
                value={values.target_market}
                onChange={(e) => update("target_market", e.target.value as TargetMarket)}
                className="field-input"
              >
                <option value="egypt">Egypt (default)</option>
                <option value="arab_market">Arab market</option>
                <option value="global">Global</option>
                <option value="custom">Custom (follow special notes)</option>
              </select>
            </div>
            <div>
              <label className="nc-field-label" htmlFor="nc-quality">
                Generation quality
              </label>
              <select
                id="nc-quality"
                disabled={disabled}
                value={values.generation_quality_mode}
                onChange={(e) =>
                  update("generation_quality_mode", e.target.value as GenerationQualityMode)
                }
                className="field-input"
              >
                <option value="premium">Premium — full pipeline</option>
                <option value="preview">Preview — faster direction test</option>
              </select>
            </div>
          </div>
          <div>
            <label className="nc-field-label" htmlFor="nc-structure">
              Structure mode
            </label>
            <select
              id="nc-structure"
              disabled={disabled}
              value={values.structure_mode}
              onChange={(e) => update("structure_mode", e.target.value as StructureMode)}
              className="field-input"
            >
              <option value="connected_no_modules">Connected, no modules</option>
              <option value="connected_modules_with_bridge_projects">
                Connected modules with bridge projects
              </option>
            </select>
          </div>
          <div>
            <label className="nc-field-label" htmlFor="nc-preset">
              Generation preset
            </label>
            <select
              id="nc-preset"
              disabled={disabled}
              value={values.generation_preset}
              onChange={(e) => update("generation_preset", e.target.value as GenerationPreset)}
              className="field-input"
            >
              {GENERATION_PRESET_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} title={opt.helper}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="mt-1.5 text-xs text-muted">
              {GENERATION_PRESET_HELPERS[values.generation_preset]}
            </p>
          </div>
        </div>
      </details>
    </section>
  );
}
