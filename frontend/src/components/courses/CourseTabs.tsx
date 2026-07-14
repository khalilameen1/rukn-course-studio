"use client";

export type CourseTab = "sources" | "versions" | "report";

const BASE_TABS: { id: CourseTab; label: string }[] = [
  { id: "sources", label: "Sources" },
  { id: "versions", label: "Versions" },
];

export default function CourseTabs({
  active,
  onChange,
  showReportTab = false,
}: {
  active: CourseTab;
  onChange: (tab: CourseTab) => void;
  /** Only courses with explanation_level "full_report" get a Report tab. */
  showReportTab?: boolean;
}) {
  const tabs = showReportTab
    ? [...BASE_TABS, { id: "report" as const, label: "Report" }]
    : BASE_TABS;

  return (
    <div className="overflow-x-auto">
      <div className="flex w-max min-w-full gap-1 rounded-full border border-border bg-surface-muted p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`shrink-0 rounded-full px-4 py-1.5 text-sm whitespace-nowrap transition-colors ${
              active === tab.id
                ? "bg-surface font-medium shadow-sm"
                : "text-muted hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
