import Link from "next/link";
import BackendStatus from "@/components/BackendStatus";

const SECTIONS = [
  {
    href: "/admin",
    title: "Admin Knowledge Center",
    description: "Manage the fixed Rukn knowledge used by every course generation run.",
  },
  {
    href: "/courses",
    title: "Courses",
    description:
      "Create a course brief, upload sources, and generate the final DOCX.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold">Rukn Course Studio</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Internal tool for generating Rukn practical-skill courses as a final DOCX file.
        </p>
      </div>

      <BackendStatus />

      <ul className="flex flex-col gap-4">
        {SECTIONS.map((section) => (
          <li key={section.href}>
            <Link
              href={section.href}
              className="block rounded-lg border border-black/10 p-4 transition-colors hover:bg-black/[.03] dark:border-white/10 dark:hover:bg-white/[.05]"
            >
              <h2 className="font-medium">{section.title}</h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {section.description}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
