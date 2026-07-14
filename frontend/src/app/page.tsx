import Link from "next/link";
import BackendStatus from "@/components/BackendStatus";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";

const WORKFLOW = ["Inputs", "Generate", "Teleprompter-ready DOCX"] as const;

const SECTIONS = [
  {
    href: "/admin",
    title: "Admin Knowledge Center",
    description: "Fixed Rukn rules used by every generation run.",
  },
  {
    href: "/courses",
    title: "Courses",
    description: "Create a brief, upload sources, generate the final DOCX.",
  },
  {
    href: "/ai-usage",
    title: "AI Usage / Operations",
    description: "Provider status and estimated app usage (not account balance).",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Rukn Course Studio"
        description="Internal workspace for teleprompter-ready lecturer scripts."
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {WORKFLOW.map((step, index) => (
          <div key={step} className="flex items-center gap-2">
            {index > 0 ? <span className="text-muted">→</span> : null}
            <span className="rounded-full border border-border bg-surface px-3 py-1 text-foreground shadow-[var(--shadow-sm)]">
              {step}
            </span>
          </div>
        ))}
      </div>

      <BackendStatus />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SECTIONS.map((section) => (
          <Link key={section.href} href={section.href} className="block">
            <Card interactive className="h-full">
              <h2 className="font-medium text-foreground">{section.title}</h2>
              <p className="mt-1.5 text-sm text-muted">{section.description}</p>
              <p className="mt-4 text-xs font-medium text-accent">Open →</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
