"use client";

export default function ReadinessPanel({
  briefComplete,
  sourcesReady,
  sourcesPending,
  mapStatus,
  mapUnsaved,
  canCreate,
  nextStep,
  disabledReason,
}: {
  briefComplete: boolean;
  sourcesReady: number;
  sourcesPending: number;
  mapStatus: "empty" | "saved" | "unsaved" | "generated";
  mapUnsaved: boolean;
  canCreate: boolean;
  nextStep: string;
  disabledReason?: string | null;
}) {
  function briefLine() {
    return briefComplete ? "Complete" : "Add title, learner, and goal";
  }

  function sourcesLine() {
    if (sourcesReady === 0 && sourcesPending === 0) return "None added (optional)";
    const parts: string[] = [];
    if (sourcesReady > 0) parts.push(`${sourcesReady} ready`);
    if (sourcesPending > 0) parts.push(`${sourcesPending} waiting to upload`);
    return parts.join(", ");
  }

  function mapLine() {
    if (mapStatus === "empty") return "Not started (optional)";
    if (mapUnsaved || mapStatus === "unsaved") return "Unsaved changes";
    if (mapStatus === "generated") return "Generated — review before full run";
    return "Saved";
  }

  return (
    <aside className="nc-readiness-panel" aria-label="Course readiness">
      <p className="text-sm font-semibold text-foreground">Course readiness</p>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Brief</dt>
          <dd className={briefComplete ? "text-foreground" : "text-amber-700"}>{briefLine()}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Sources</dt>
          <dd className="text-foreground">{sourcesLine()}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Course map</dt>
          <dd className="text-foreground">{mapLine()}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Next</dt>
          <dd className="font-medium text-accent">{canCreate ? "Open course workspace" : "Complete brief"}</dd>
        </div>
      </dl>
      <div className="mt-4 rounded-xl border border-border bg-surface-muted/40 px-3 py-2.5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Next step</p>
        <p className="mt-1 text-sm text-foreground">{nextStep}</p>
        {disabledReason && !canCreate ? (
          <p className="mt-1.5 text-xs text-muted">{disabledReason}</p>
        ) : null}
      </div>
    </aside>
  );
}
