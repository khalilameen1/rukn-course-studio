"use client";

import { useState } from "react";
import type { Priority, SourceCategory } from "@/lib/types";
import Card from "@/components/ui/Card";
import { SOURCE_CATEGORY_HELPERS, SOURCE_CATEGORY_OPTIONS } from "@/lib/sourceCategories";

const PRIORITY_OPTIONS: Priority[] = ["high", "medium", "low"];

const FIELD_CLASS = "rounded-md border border-border bg-transparent px-2 py-1 text-sm outline-none";

export default function NotesSourceForm({
  onAdd,
}: {
  onAdd: (text: string, category: SourceCategory, priority: Priority) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState<SourceCategory>("user_notes");
  const [priority, setPriority] = useState<Priority>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAdd(text, category, priority);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <h3 className="font-medium">Add a note</h3>

        <textarea
          required
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Anything useful for generation that isn't a file - e.g. terminology to avoid, key points to emphasize."
          className={`${FIELD_CLASS} text-sm`}
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
          disabled={!text.trim() || submitting}
          className="btn-primary w-fit"
        >
          {submitting ? "Adding..." : "Add note"}
        </button>
      </form>
    </Card>
  );
}
