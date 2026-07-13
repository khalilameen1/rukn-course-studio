"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AdminKnowledgeItem } from "@/lib/types";
import KnowledgeItemForm, {
  type KnowledgeItemFormValues,
} from "@/components/admin/KnowledgeItemForm";
import KnowledgeItemTable from "@/components/admin/KnowledgeItemTable";

export default function AdminKnowledgePage() {
  const [items, setItems] = useState<AdminKnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<AdminKnowledgeItem | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listKnowledgeItems());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge items");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Standard fetch-on-mount; `refresh` is also reused by the mutation
    // handlers below, so it isn't inlined here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function handleSubmit(values: KnowledgeItemFormValues) {
    const payload = {
      key: values.key,
      title: values.title,
      item_type: values.item_type,
      content_text: values.item_type === "docx_template" ? null : values.content_text,
      file_path: values.item_type === "docx_template" ? values.file_path : null,
    };

    if (editingItem) {
      await api.updateKnowledgeItem(editingItem.id, payload);
      setEditingItem(null);
    } else {
      await api.createKnowledgeItem(payload);
    }
    await refresh();
  }

  async function handleDelete(item: AdminKnowledgeItem) {
    if (!confirm(`Delete "${item.title}"? This cannot be undone.`)) return;
    await api.deleteKnowledgeItem(item.id);
    if (editingItem?.id === item.id) setEditingItem(null);
    await refresh();
  }

  async function handleActivate(item: AdminKnowledgeItem) {
    await api.activateKnowledgeItem(item.id);
    await refresh();
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold">Admin Knowledge Center</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Fixed Rukn knowledge (structure, style, pedagogy, formatting rules,
          templates) that every course generation run is pinned to. Only one
          version per key is active at a time.
        </p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-zinc-500">Loading...</p>
      ) : (
        <KnowledgeItemTable
          items={items}
          onEdit={setEditingItem}
          onDelete={handleDelete}
          onActivate={handleActivate}
        />
      )}

      <KnowledgeItemForm
        key={editingItem?.id ?? "new"}
        editingItem={editingItem}
        onSubmit={handleSubmit}
        onCancel={() => setEditingItem(null)}
      />
    </div>
  );
}
