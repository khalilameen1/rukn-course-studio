"use client";

import { useState } from "react";
import type { Priority, SourceCategory } from "@/lib/types";

const PRIORITY_OPTIONS: Priority[] = ["high", "medium", "low"];

export default function NotesSourceForm({
  onAdd,
}: {
  onAdd: (text: string, category: SourceCategory, priority: Priority) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAdd(text, "notes", priority);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-black/10 p-4 dark:border-white/10"
    >
      <h3 className="font-medium">Add a note</h3>

      <textarea
        required
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Anything useful for generation that isn't a file - e.g. terminology to avoid, key points to emphasize."
        className="rounded border border-black/15 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
      />

      <label className="flex w-fit flex-col gap-1 text-sm">
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

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <button
        type="submit"
        disabled={!text.trim() || submitting}
        className="w-fit rounded-full bg-foreground px-4 py-1.5 text-sm text-background disabled:opacity-60"
      >
        {submitting ? "Adding..." : "Add note"}
      </button>
    </form>
  );
}
