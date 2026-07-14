"use client";

import { useState } from "react";
import type { CourseSource, SourceCategory } from "@/lib/types";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";
import { SOURCE_CATEGORY_HELPERS, SOURCE_CATEGORY_LABELS, SOURCE_CATEGORY_OPTIONS } from "@/lib/sourceCategories";

export default function SourceTable({
  sources,
  onDelete,
  onCategoryChange,
}: {
  sources: CourseSource[];
  onDelete: (source: CourseSource) => void;
  onCategoryChange: (source: CourseSource, category: SourceCategory) => Promise<void>;
}) {
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  async function handleCategoryChange(source: CourseSource, category: SourceCategory) {
    if (category === source.source_category) return;
    setSavingId(source.id);
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[source.id];
      return next;
    });
    try {
      await onCategoryChange(source, category);
    } catch (err) {
      setRowErrors((prev) => ({
        ...prev,
        [source.id]: err instanceof Error ? err.message : "Failed to update type",
      }));
    } finally {
      setSavingId(null);
    }
  }

  if (sources.length === 0) {
    return (
      <EmptyState
        title="No sources added yet"
        description="Sources are optional - add a file or note below if you have one."
      />
    );
  }

  return (
    <Card padding="none" className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted/70 text-muted">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Category</th>
            <th className="px-4 py-3 font-medium">Priority</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3">
                {source.original_filename ?? (
                  <span className="text-muted italic">
                    {source.extracted_text
                      ? source.extracted_text.slice(0, 40) +
                        (source.extracted_text.length > 40 ? "..." : "")
                      : "(note)"}
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <span title={SOURCE_CATEGORY_HELPERS[source.source_category]}>
                  <StatusBadge label={SOURCE_CATEGORY_LABELS[source.source_category]} tone="neutral" />
                </span>
              </td>
              <td className="px-4 py-3 text-muted">{source.priority}</td>
              <td className="px-4 py-3">
                <StatusBadge label={source.status} tone="neutral" />
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <select
                    value={source.source_category}
                    disabled={savingId === source.id}
                    onChange={(e) =>
                      handleCategoryChange(source, e.target.value as SourceCategory)
                    }
                    title="Change source type"
                    aria-label="Change source type"
                    className="rounded-md border border-border bg-transparent px-1.5 py-0.5 text-xs outline-none disabled:opacity-60"
                  >
                    {SOURCE_CATEGORY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value} title={opt.helper}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => onDelete(source)}
                    className="text-red-600 hover:underline dark:text-red-400"
                  >
                    Delete
                  </button>
                </div>
                {rowErrors[source.id] ? (
                  <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                    {rowErrors[source.id]}
                  </p>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
