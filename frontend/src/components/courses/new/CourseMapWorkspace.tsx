"use client";

import ChatComposer from "@/components/ui/ChatComposer";

const MAP_PLACEHOLDER = `Write or paste the course map here…

Example:
Module 1: Foundations
  Lesson 1: Hook and promise
  Lesson 2: Core concept
Module 2: Application
  Lesson 1: First campaign setup`;

export default function CourseMapWorkspace({
  mapText,
  mapStatus,
  mapUnsaved,
  mapSaved,
  disabled,
  canGenerate,
  busy,
  onMapChange,
  onGenerateMap,
  onSaveMap,
  onClearMap,
}: {
  mapText: string;
  mapStatus: string | null;
  mapUnsaved: boolean;
  mapSaved: boolean;
  disabled?: boolean;
  canGenerate: boolean;
  busy?: boolean;
  onMapChange: (text: string) => void;
  onGenerateMap: () => void;
  onSaveMap: () => void;
  onClearMap: () => void;
}) {
  const generateDisabledReason = !canGenerate
    ? "Add a course title, target learner, and goal first"
    : busy
      ? "Wait for the current action to finish"
      : null;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5 shadow-[var(--shadow-sm)] sm:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">Step 3</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight">Course map</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Optional outline for modules and lessons. Generate from your brief and sources, or write
            it yourself.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-secondary shrink-0"
            disabled={!canGenerate || disabled || busy}
            title={generateDisabledReason ?? undefined}
            onClick={onGenerateMap}
          >
            {busy && mapStatus ? "Generating map…" : "Generate Course Map"}
          </button>
          <button
            type="button"
            className="btn-ghost shrink-0 text-sm"
            disabled={disabled || busy || !mapText.trim()}
            onClick={onSaveMap}
          >
            Save map
          </button>
        </div>
      </div>

      {generateDisabledReason && !canGenerate ? (
        <p className="text-xs text-muted">{generateDisabledReason}</p>
      ) : null}

      {mapStatus ? (
        <div className="flex items-center gap-2 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2 text-sm text-accent">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
          {mapStatus}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        {mapText.trim() ? (
          mapUnsaved ? (
            <span className="rounded-full bg-amber-50 px-2.5 py-0.5 font-medium text-amber-800 ring-1 ring-amber-200">
              Unsaved changes
            </span>
          ) : mapSaved ? (
            <span className="rounded-full bg-accent-soft px-2.5 py-0.5 font-medium text-accent">
              Saved
            </span>
          ) : null
        ) : (
          <p className="text-sm text-muted">No course map yet — write below or generate from your brief.</p>
        )}
      </div>

      <div className="nc-map-workspace">
        <ChatComposer
          value={mapText}
          onChange={onMapChange}
          onClear={mapText.trim() ? onClearMap : undefined}
          disabled={disabled || busy}
          showSend={false}
          minRows={12}
          maxHeight={480}
          placeholder={MAP_PLACEHOLDER}
          helper="Comfortable editor for long outlines — edit freely before full generation."
        />
      </div>

      {mapText.trim() ? (
        <div className="flex justify-end">
          <button
            type="button"
            className="btn-ghost text-xs text-muted hover:text-red-600"
            disabled={disabled || busy}
            onClick={() => {
              if (confirm("Clear the course map? You can still regenerate it later.")) onClearMap();
            }}
          >
            Clear map
          </button>
        </div>
      ) : null}
    </section>
  );
}
