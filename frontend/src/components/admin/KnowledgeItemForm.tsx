"use client";

import { useEffect, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { AdminKnowledgeItem, ItemType } from "@/lib/types";
import Card from "@/components/ui/Card";

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

const SYSTEM_JSON_KEYS = new Set([
  "rukn_forbidden_phrases",
  "rukn_quality_rubric",
  "rukn_generation_presets",
]);

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

function validateJsonContent(key: string, itemType: ItemType, content: string): string | null {
  if (itemType !== "json") return null;
  try {
    const parsed = JSON.parse(content);
    if (SYSTEM_JSON_KEYS.has(key)) {
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return "System JSON items must be a JSON object.";
      }
      if (key === "rukn_forbidden_phrases") {
        if (!Array.isArray(parsed.phrases) || parsed.phrases.length < 1) {
          return "forbidden_phrases requires a non-empty phrases array.";
        }
      }
      if (key === "rukn_quality_rubric") {
        if (!Array.isArray(parsed.checks) || parsed.checks.length < 1) {
          return "quality_rubric requires a non-empty checks array.";
        }
      }
      if (key === "rukn_generation_presets") {
        if (!Array.isArray(parsed.presets) || parsed.presets.length < 1) {
          return "generation_presets requires a non-empty presets array.";
        }
      }
    }
  } catch {
    return "Content is not valid JSON.";
  }
  return null;
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
  onActivateVersion,
}: {
  editingItem: AdminKnowledgeItem | null;
  onSubmit: (values: KnowledgeItemFormValues) => Promise<void>;
  onCancel: () => void;
  onActivateVersion?: (item: AdminKnowledgeItem) => Promise<void> | void;
}) {
  const [values, setValues] = useState<KnowledgeItemFormValues>(() =>
    toFormValues(editingItem),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jsonHint, setJsonHint] = useState<string | null>(null);
  const [versions, setVersions] = useState<AdminKnowledgeItem[]>([]);

  useEffect(() => {
    if (!editingItem?.key) {
      setVersions([]);
      return;
    }
    let cancelled = false;
    api
      .listKnowledgeVersions(editingItem.key)
      .then((rows) => {
        if (!cancelled) setVersions(rows);
      })
      .catch(() => {
        if (!cancelled) setVersions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [editingItem?.key]);

  function update<K extends keyof KnowledgeItemFormValues>(
    field: K,
    value: KnowledgeItemFormValues[K],
  ) {
    setValues((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "content_text" || field === "item_type" || field === "key") {
        setJsonHint(
          validateJsonContent(next.key, next.item_type, next.content_text),
        );
      }
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const local = validateJsonContent(values.key, values.item_type, values.content_text);
    if (local) {
      setError(local);
      setJsonHint(local);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(values);
      if (!editingItem) setValues(EMPTY_VALUES);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setSubmitting(false);
    }
  }

  const fieldClass =
    "rounded-md border border-border bg-transparent px-2 py-1 text-sm outline-none disabled:opacity-60";

  return (
    <Card>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <h3 className="font-medium">
          {editingItem ? `Edit "${editingItem.title}"` : "Add knowledge item"}
        </h3>
        {editingItem ? (
          <p className="text-xs text-muted">
            Saving creates a new version (v{(editingItem.version ?? 1) + 1}) and archives the
            current active row. Client JSON checks are UX only — the server schema is
            authoritative (422 on invalid content). High-trust keys ask for confirm first.
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Key
            <input
              required
              disabled={!!editingItem}
              value={values.key}
              onChange={(e) => update("key", e.target.value)}
              placeholder="e.g. structure_rules"
              className={fieldClass}
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              required
              value={values.title}
              onChange={(e) => update("title", e.target.value)}
              className={fieldClass}
            />
          </label>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          Type
          <select
            value={values.item_type}
            onChange={(e) => update("item_type", e.target.value as ItemType)}
            className={fieldClass}
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
              className={fieldClass}
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
              className={`${fieldClass} font-mono text-xs`}
            />
          </label>
        )}

        {jsonHint ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">{jsonHint}</p>
        ) : null}
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        {editingItem && versions.length > 1 ? (
          <div className="rounded-md border border-border p-3 text-sm">
            <p className="mb-2 font-medium">Version history ({versions.length})</p>
            <ul className="flex flex-col gap-1">
              {versions.map((v) => (
                <li
                  key={v.id}
                  className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted"
                >
                  <span>
                    v{v.version}
                    {v.is_active ? " · active" : " · archived"}
                    {v.id === editingItem.id ? " · editing" : ""}
                  </span>
                  {!v.is_active && onActivateVersion ? (
                    <button
                      type="button"
                      className="underline"
                      onClick={() => onActivateVersion(v)}
                    >
                      Activate
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex gap-2">
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Saving..." : editingItem ? "Save as new version" : "Add item"}
          </button>
          {editingItem ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-border px-4 py-1.5 text-sm hover:bg-surface-muted"
            >
              Cancel
            </button>
          ) : null}
        </div>
      </form>
    </Card>
  );
}
