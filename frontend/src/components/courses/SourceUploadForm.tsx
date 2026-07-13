"use client";

import { useState } from "react";
import type { Priority, SourceCategory } from "@/lib/types";

const CATEGORY_OPTIONS: { value: SourceCategory; label: string }[] = [
  { value: "main_content", label: "Main content" },
  { value: "supporting", label: "Supporting" },
  { value: "spoken_style", label: "Spoken style / transcript" },
  { value: "old_course", label: "Old course material" },
  { value: "notes", label: "Notes" },
];

const PRIORITY_OPTIONS: Priority[] = ["high", "medium", "low"];

export default function SourceUploadForm({
  onUpload,
}: {
  onUpload: (file: File, category: SourceCategory, priority: Priority) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<SourceCategory>("main_content");
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
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-black/10 p-4 dark:border-white/10"
    >
      <h3 className="font-medium">Upload a file</h3>
      <p className="text-xs text-zinc-500">Accepted: .docx, .pdf, .txt, .md</p>

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
            className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Priority
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
            className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
          >
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <button
        type="submit"
        disabled={!file || submitting}
        className="w-fit rounded-full bg-foreground px-4 py-1.5 text-sm text-background disabled:opacity-60"
      >
        {submitting ? "Uploading..." : "Upload"}
      </button>
    </form>
  );
}
