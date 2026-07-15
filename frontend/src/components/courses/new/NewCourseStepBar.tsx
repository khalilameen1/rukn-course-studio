"use client";

export default function NewCourseStepBar({
  briefDone,
  sourcesCount,
  mapStarted,
  readyToOpen,
}: {
  briefDone: boolean;
  sourcesCount: number;
  mapStarted: boolean;
  readyToOpen: boolean;
}) {
  const sourcesDone = sourcesCount > 0;

  return (
    <nav aria-label="Course creation progress" className="flex flex-wrap items-center gap-2">
      <span className="nc-step-pill" data-active={!briefDone} data-done={briefDone}>
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[0.65rem] font-bold text-accent">
          1
        </span>
        Brief
      </span>
      <span className="text-muted" aria-hidden>
        →
      </span>
      <span className="nc-step-pill" data-active={briefDone && !sourcesDone} data-done={sourcesDone}>
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[0.65rem] font-bold text-accent">
          2
        </span>
        Sources{sourcesCount > 0 ? ` (${sourcesCount})` : ""}
      </span>
      <span className="text-muted" aria-hidden>
        →
      </span>
      <span className="nc-step-pill" data-active={sourcesDone && !mapStarted} data-done={mapStarted}>
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[0.65rem] font-bold text-accent">
          3
        </span>
        Map
      </span>
      <span className="text-muted" aria-hidden>
        →
      </span>
      <span className="nc-step-pill" data-active={briefDone && !readyToOpen} data-done={readyToOpen}>
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[0.65rem] font-bold text-accent">
          4
        </span>
        Open
      </span>
    </nav>
  );
}
