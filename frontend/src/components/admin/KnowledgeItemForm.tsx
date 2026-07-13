"use client";

import { useState } from "react";
import type { AdminKnowledgeItem, ItemType } from "@/lib/types";

export interface KnowledgeItemFormValues {
  key: string;
  title: string;
  item_type: ItemType;
  content_text: string;
  file_path: string;
}

const EMPTY_VALUES: KnowledgeItemFormValues = {
  key: "",
  title: "",
  item_type: "markdown",
  content_text: "",
  file_path: "",
};

function toFormValues(item: AdminKnowledgeItem | null): KnowledgeItemFormValues {
  if (!item) return EMPTY_VALUES;
  return {
    key: item.key,
    title: item.title,
    item_type: item.item_type,
    content_text: item.content_text ?? "",
    file_path: item.file_path ?? "",
  };
}

/**
 * Renders create/edit form. The parent is expected to pass a `key` prop that
 * changes with `editingItem` (e.g. `editingItem?.id ?? "new"`) so this
 * component remounts - and its state re-initializes from `editingItem` -
 * instead of needing an effect to sync local state from a prop.
 */
export default function KnowledgeItemForm({
  editingItem,
  onSubmit,
  onCancel,
}: {
  editingItem: AdminKnowledgeItem | null;
  onSubmit: (values: KnowledgeItemFormValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<KnowledgeItemFormValues>(() =>
    toFormValues(editingItem),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof KnowledgeItemFormValues>(
    field: K,
    value: KnowledgeItemFormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(values);
      if (!editingItem) setValues(EMPTY_VALUES);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-black/10 p-4 dark:border-white/10"
    >
      <h3 className="font-medium">
        {editingItem ? `Edit "${editingItem.title}"` : "Add knowledge item"}
      </h3>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          Key
          <input
            required
            disabled={!!editingItem}
            value={values.key}
            onChange={(e) => update("key", e.target.value)}
            placeholder="e.g. structure_rules"
            className="rounded border border-black/15 px-2 py-1 disabled:opacity-60 dark:border-white/20 dark:bg-transparent"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            required
            value={values.title}
            onChange={(e) => update("title", e.target.value)}
            className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm">
        Type
        <select
          value={values.item_type}
          onChange={(e) => update("item_type", e.target.value as ItemType)}
          className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
        >
          <option value="markdown">Markdown</option>
          <option value="json">JSON</option>
          <option value="docx_template">DOCX template</option>
        </select>
      </label>

      {values.item_type === "docx_template" ? (
        <label className="flex flex-col gap-1 text-sm">
          Template file path (placeholder - upload not implemented yet)
          <input
            value={values.file_path}
            onChange={(e) => update("file_path", e.target.value)}
            placeholder="storage/templates/..."
            className="rounded border border-black/15 px-2 py-1 dark:border-white/20 dark:bg-transparent"
          />
        </label>
      ) : (
        <label className="flex flex-col gap-1 text-sm">
          Content ({values.item_type})
          <textarea
            required
            rows={6}
            value={values.content_text}
            onChange={(e) => update("content_text", e.target.value)}
            className="rounded border border-black/15 px-2 py-1 font-mono text-xs dark:border-white/20 dark:bg-transparent"
          />
        </label>
      )}

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-foreground px-4 py-1.5 text-sm text-background disabled:opacity-60"
        >
          {submitting ? "Saving..." : editingItem ? "Save changes" : "Add item"}
        </button>
        {editingItem ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-black/15 px-4 py-1.5 text-sm dark:border-white/20"
          >
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );
}
