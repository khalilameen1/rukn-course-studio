"use client";

import type { CourseVersion } from "@/lib/types";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";

export default function VersionTable({ versions }: { versions: CourseVersion[] }) {
  if (versions.length === 0) {
    return (
      <EmptyState
        title="No versions generated yet"
        description="Use Generate in the workspace above to create the first version."
      />
    );
  }

  const sorted = [...versions].sort((a, b) => b.version_number - a.version_number);

  return (
    <Card padding="none" className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted/70 text-muted">
            <th className="px-4 py-3 font-medium">Version</th>
            <th className="px-4 py-3 font-medium">Summary</th>
            <th className="px-4 py-3 font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((version) => (
            <tr key={version.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3">v{version.version_number}</td>
              <td className="px-4 py-3 text-muted">{version.summary_text ?? "-"}</td>
              <td className="px-4 py-3 text-muted">
                {new Date(version.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
