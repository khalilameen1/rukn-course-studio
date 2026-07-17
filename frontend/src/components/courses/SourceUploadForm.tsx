"use client";

import { useState } from "react";
import type { Priority, SourceCategory } from "@/lib/types";
import Card from "@/components/ui/Card";
import { SOURCE_CATEGORY_HELPERS, SOURCE_CATEGORY_OPTIONS } from "@/lib/sourceCategories";
import { formatUploadErrorForDisplay } from "@/lib/api";

const PRIORITY_OPTIONS: Priority[] = ["high", "medium", "low"];

const FIELD_CLASS = "rounded-md border border-border bg-transparent px-2 py-1 text-sm outline-none";

export default function SourceUploadForm({
  onUpload,
}: {
  onUpload: (file: File, category: SourceCategory, priority: Priority) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<SourceCategory>("scientific_reference");
  const [priority, setPriority] = useState<Priority>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setSubmitting(true);
    setError(null);
    try {
      await onUpload(file, category, priority);
      setFile(null);
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      setError(formatUploadErrorForDisplay(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <h3 className="font-medium">Upload a file</h3>
        <p className="text-xs text-muted">Accepted: .docx, .pdf, .txt, .md</p>

        <input
          type="file"
          required
          accept=".docx,.pdf,.txt,.md"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Category
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SourceCategory)}
              className={FIELD_CLASS}
            >
              {SOURCE_CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} title={opt.helper}>
                  {opt.label}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted">{SOURCE_CATEGORY_HELPERS[category]}</span>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Priority
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
              className={FIELD_CLASS}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        <button
          type="submit"
          disabled={!file || submitting}
          className="btn-primary w-fit"
        >
          {submitting ? "Uploading..." : "Upload"}
        </button>
        {!file && !submitting ? (
          <p className="text-xs text-muted">Choose a file above to enable Upload.</p>
        ) : null}
      </form>
    </Card>
  );
}
