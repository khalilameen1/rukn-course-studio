"use client";

import type { CourseVersion } from "@/lib/types";

export default function VersionTable({ versions }: { versions: CourseVersion[] }) {
  if (versions.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No versions generated yet. Use the Generate tab to create one.
      </p>
    );
  }

  const sorted = [...versions].sort((a, b) => b.version_number - a.version_number);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-black/10 text-zinc-500 dark:border-white/10">
            <th className="py-2 pr-4">Version</th>
            <th className="py-2 pr-4">Summary</th>
            <th className="py-2 pr-4">Created</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((version) => (
            <tr key={version.id} className="border-b border-black/5 dark:border-white/5">
              <td className="py-2 pr-4">v{version.version_number}</td>
              <td className="py-2 pr-4">{version.summary_text ?? "-"}</td>
              <td className="py-2 pr-4">{new Date(version.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
