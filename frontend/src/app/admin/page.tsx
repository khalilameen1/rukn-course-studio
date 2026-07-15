"use client";

import { useCallback, useEffect, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { AdminKnowledgeItem } from "@/lib/types";
import KnowledgeItemForm, {
  type KnowledgeItemFormValues,
} from "@/components/admin/KnowledgeItemForm";
import KnowledgeItemGrid from "@/components/admin/KnowledgeItemGrid";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import DeployDiagnostics from "@/components/admin/DeployDiagnostics";

export default function AdminKnowledgePage() {
  const [items, setItems] = useState<AdminKnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<AdminKnowledgeItem | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listKnowledgeItems({ includeInactive: showInactive }));
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function handleCleanup() {
    if (actionBusy) return;
    setActionBusy("cleanup");
    try {
      const preview = await api.cleanupKnowledgeDuplicates({ dryRun: true, confirm: false });
      const count =
        preview.would_deactivate_count ?? preview.deactivated_count ?? 0;
      if (
        !confirm(
          `${preview.message}\n\nApply and deactivate ${count} duplicate(s)? ` +
            "A JSON backup snapshot will be written first.",
        )
      ) {
        return;
      }
      const report = await api.cleanupKnowledgeDuplicates({
        dryRun: false,
        confirm: true,
      });
      alert(report.message);
      await refresh();
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setActionBusy(null);
    }
  }

  async function handleSubmit(values: KnowledgeItemFormValues) {
    if (actionBusy) return;
    setActionBusy(editingItem ? `save-${editingItem.id}` : "create");
    try {
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
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setActionBusy(null);
    }
  }

  async function handleDelete(item: AdminKnowledgeItem) {
    if (actionBusy) return;
    if (
      !confirm(
        `Archive "${item.title}" (deactivate)? The row is kept as inactive. ` +
          "Permanent purge is CLI-only with confirm+purge.",
      )
    ) {
      return;
    }
    setActionBusy(`delete-${item.id}`);
    try {
      await api.deleteKnowledgeItem(item.id, {
        confirm: true,
        dryRun: false,
        purge: false,
      });
      if (editingItem?.id === item.id) setEditingItem(null);
      await refresh();
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setActionBusy(null);
    }
  }

  async function handleActivate(item: AdminKnowledgeItem) {
    if (actionBusy) return;
    setActionBusy(`activate-${item.id}`);
    try {
      await api.activateKnowledgeItem(item.id);
      await refresh();
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setActionBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Admin Knowledge"
        description="Global ROKN behavior for every course — writing rules, quality gates, and teleprompter contract. Do not upload course PDFs, transcripts, or maps here; add those on each course’s Sources tab."
      />

      <DeployDiagnostics />

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2 text-muted">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Show inactive / archived versions
        </label>
        <button
          type="button"
          className="btn-secondary"
          disabled={Boolean(actionBusy)}
          onClick={handleCleanup}
        >
          {actionBusy === "cleanup" ? "Working…" : "Clean duplicate active items"}
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Loading...</p>
      ) : items.length === 0 ? (
        <EmptyState
          title="Admin knowledge not seeded yet"
          description="This normally seeds automatically when the backend starts. If it's still empty, run `python -m app.seed_admin_knowledge` from backend/, or restart the backend - or add an item manually below."
        />
      ) : (
        <KnowledgeItemGrid
          items={items}
          onEdit={setEditingItem}
          onDelete={handleDelete}
          onActivate={handleActivate}
          actionBusy={actionBusy}
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
