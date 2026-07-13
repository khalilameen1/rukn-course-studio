"use client";

export type CourseTab = "brief" | "sources" | "generate" | "versions" | "report";

const BASE_TABS: { id: CourseTab; label: string }[] = [
  { id: "brief", label: "Brief" },
  { id: "sources", label: "Sources" },
  { id: "generate", label: "Generate" },
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
    <div className="flex gap-1 border-b border-black/10 dark:border-white/10">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm ${
            active === tab.id
              ? "border-b-2 border-foreground font-medium"
              : "text-zinc-500 hover:text-foreground"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
