"use client";

import { useState } from "react";
import type { CourseSource, SourceCategory } from "@/lib/types";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";
import { SOURCE_CATEGORY_HELPERS, SOURCE_CATEGORY_LABELS, SOURCE_CATEGORY_OPTIONS } from "@/lib/sourceCategories";
import { sourceStatusLabel } from "@/lib/sourceStatusMaps";
import { formatApiErrorForDisplay } from "@/lib/api";

const RETRYABLE = new Set([
  "password_required",
  "failed",
  "processing_failed",
  "extraction_blocked",
  "scanned_no_text",
  "poor_extraction",
  "uploaded",
]);

export default function SourceTable({
  sources,
  onDelete,
  onCategoryChange,
  onIncludeChange,
  onReprocess,
  onPreview,
}: {
  sources: CourseSource[];
  onDelete: (source: CourseSource) => void;
  onCategoryChange: (source: CourseSource, category: SourceCategory) => Promise<void>;
  onIncludeChange: (source: CourseSource, include: boolean) => Promise<void>;
  onReprocess: (source: CourseSource, password?: string) => Promise<void>;
  onPreview: (source: CourseSource) => Promise<{ summary?: string | null; keyPoints: string[] }>;
}) {
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [passwords, setPasswords] = useState<Record<number, string>>({});
  const [previews, setPreviews] = useState<
    Record<number, { summary?: string | null; keyPoints: string[] } | "loading" | "hidden">
  >({});

  async function runRowAction(sourceId: number, action: () => Promise<void>) {
    setSavingId(sourceId);
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[sourceId];
      return next;
    });
    try {
      await action();
    } catch (err) {
      setRowErrors((prev) => ({
        ...prev,
        [sourceId]: formatApiErrorForDisplay(err),
      }));
    } finally {
      setSavingId(null);
    }
  }

  async function handleCategoryChange(source: CourseSource, category: SourceCategory) {
    if (category === source.source_category) return;
    if (category === "flow_reference") {
      const ok = confirm(
        "Natural spoken language sample is for colloquial flow only — not facts, hooks, structure, or examples. Continue?",
      );
      if (!ok) return;
    }
    await runRowAction(source.id, () => onCategoryChange(source, category));
  }

  async function handleIncludeToggle(source: CourseSource) {
    const next = !(source.include_in_generation ?? true);
    if (next && source.status === "poor_extraction") {
      const ok = confirm(
        "This extract looks weak. Include it in generation anyway?",
      );
      if (!ok) return;
    }
    await runRowAction(source.id, () => onIncludeChange(source, next));
  }

  async function handleRetry(source: CourseSource) {
    const password =
      source.status === "password_required"
        ? (passwords[source.id] || "").trim() || undefined
        : undefined;
    if (source.status === "password_required" && !password) {
      setRowErrors((prev) => ({
        ...prev,
        [source.id]: "Enter the PDF password, then click Unlock.",
      }));
      return;
    }
    await runRowAction(source.id, () => onReprocess(source, password));
  }

  async function handlePreview(source: CourseSource) {
    const current = previews[source.id];
    if (current && current !== "loading" && current !== "hidden") {
      setPreviews((prev) => ({ ...prev, [source.id]: "hidden" }));
      return;
    }
    setPreviews((prev) => ({ ...prev, [source.id]: "loading" }));
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[source.id];
      return next;
    });
    try {
      const data = await onPreview(source);
      setPreviews((prev) => ({ ...prev, [source.id]: data }));
    } catch (err) {
      setPreviews((prev) => ({ ...prev, [source.id]: "hidden" }));
      setRowErrors((prev) => ({
        ...prev,
        [source.id]: formatApiErrorForDisplay(err),
      }));
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
            <th className="px-4 py-3 font-medium">Include</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => {
            const busy = savingId === source.id;
            const preview = previews[source.id];
            const canRetry = Boolean(source.file_path) && RETRYABLE.has(source.status);
            const needsPassword = source.status === "password_required";

            return (
              <tr key={source.id} className="border-b border-border last:border-0 align-top">
                <td className="px-4 py-3">
                  <div>
                    {source.original_filename ?? (
                      <span className="text-muted italic">
                        {source.display_title ||
                          source.title ||
                          (source.has_extracted_text
                            ? `(note · ${source.extract_char_count ?? 0} chars)`
                            : "(note)")}
                      </span>
                    )}
                  </div>
                  {source.status_message ? (
                    <p className="mt-1 max-w-xs text-xs text-muted">{source.status_message}</p>
                  ) : null}
                  {preview === "loading" ? (
                    <p className="mt-2 text-xs text-muted">Loading preview…</p>
                  ) : null}
                  {preview && preview !== "loading" && preview !== "hidden" ? (
                    <div className="mt-2 max-w-sm rounded-md border border-border bg-surface-muted/40 px-2 py-1.5 text-xs">
                      <p className="font-medium text-foreground">Understanding preview</p>
                      {preview.summary ? (
                        <p className="mt-1 text-muted">{preview.summary}</p>
                      ) : (
                        <p className="mt-1 text-muted">No summary stored yet.</p>
                      )}
                      {preview.keyPoints.length > 0 ? (
                        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted">
                          {preview.keyPoints.map((point) => (
                            <li key={point}>{point}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  <span title={SOURCE_CATEGORY_HELPERS[source.source_category]}>
                    <StatusBadge label={SOURCE_CATEGORY_LABELS[source.source_category]} tone="neutral" />
                  </span>
                  <p className="mt-1 text-xs text-muted">{source.priority}</p>
                </td>
                <td className="px-4 py-3">
                  <label className="inline-flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={source.include_in_generation ?? true}
                      disabled={busy}
                      onChange={() => handleIncludeToggle(source)}
                    />
                    In generation
                  </label>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge label={sourceStatusLabel(source)} tone="neutral" />
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-col items-stretch gap-2">
                    <select
                      value={source.source_category}
                      disabled={busy}
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
                    {needsPassword ? (
                      <input
                        type="password"
                        value={passwords[source.id] ?? ""}
                        onChange={(e) =>
                          setPasswords((prev) => ({ ...prev, [source.id]: e.target.value }))
                        }
                        placeholder="PDF password"
                        className="rounded-md border border-border bg-transparent px-1.5 py-0.5 text-xs outline-none"
                        disabled={busy}
                      />
                    ) : null}
                    <div className="flex flex-wrap items-center gap-3">
                      {canRetry ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleRetry(source)}
                          className="text-accent hover:underline disabled:opacity-60"
                        >
                          {needsPassword ? "Unlock" : "Retry"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => handlePreview(source)}
                        className="text-muted hover:underline disabled:opacity-60"
                      >
                        {preview && preview !== "loading" && preview !== "hidden"
                          ? "Hide preview"
                          : "Preview"}
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(source)}
                        className="text-red-600 hover:underline dark:text-red-400"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {rowErrors[source.id] ? (
                    <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                      {rowErrors[source.id]}
                    </p>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
