"use client";

import type { CourseSource } from "@/lib/types";

export default function SourceTable({
  sources,
  onDelete,
}: {
  sources: CourseSource[];
  onDelete: (source: CourseSource) => void;
}) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No sources added yet. Sources are optional.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-black/10 text-zinc-500 dark:border-white/10">
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">Category</th>
            <th className="py-2 pr-4">Priority</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.id} className="border-b border-black/5 dark:border-white/5">
              <td className="py-2 pr-4">
                {source.original_filename ?? (
                  <span className="text-zinc-500 italic">
                    {source.extracted_text
                      ? source.extracted_text.slice(0, 40) +
                        (source.extracted_text.length > 40 ? "..." : "")
                      : "(note)"}
                  </span>
                )}
              </td>
              <td className="py-2 pr-4">{source.source_category.replace(/_/g, " ")}</td>
              <td className="py-2 pr-4">{source.priority}</td>
              <td className="py-2 pr-4">{source.status}</td>
              <td className="py-2 pr-4">
                <button
                  onClick={() => onDelete(source)}
                  className="text-red-600 hover:underline"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
