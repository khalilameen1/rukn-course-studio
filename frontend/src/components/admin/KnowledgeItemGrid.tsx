"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AdminKnowledgeItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";

const ITEM_TYPE_LABELS: Record<string, string> = {
  markdown: "Markdown",
  json: "JSON",
  docx_template: "DOCX template",
};

export type KnowledgeCatalogEntry = {
  key: string;
  title: string;
  description: string;
  required?: boolean;
  refreshable?: boolean;
  stable?: boolean;
};

export default function KnowledgeItemGrid({
  items,
  catalog,
  onEdit,
  onDelete,
  onActivate,
  actionBusy = null,
}: {
  items: AdminKnowledgeItem[];
  catalog: Record<string, KnowledgeCatalogEntry>;
  onEdit: (item: AdminKnowledgeItem) => void;
  onDelete: (item: AdminKnowledgeItem) => void;
  onActivate: (item: AdminKnowledgeItem) => void;
  actionBusy?: string | null;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const known = catalog[item.key];
        return (
          <Card key={item.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium">{known?.title ?? item.title}</p>
                <p className="mt-0.5 font-mono text-xs text-muted">{item.key}</p>
              </div>
              <StatusBadge
                label={item.is_active ? "active" : "inactive"}
                tone={item.is_active ? "success" : "neutral"}
              />
            </div>
            <p className="text-sm text-muted">{known?.description ?? item.title}</p>

            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="rounded-full border border-border px-2 py-0.5">
                {ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}
              </span>
              <span>v{item.version}</span>
              {known?.stable ? (
                <span className="rounded-full border border-border px-2 py-0.5">
                  high-trust
                </span>
              ) : null}
            </div>

            <div className="mt-1 flex gap-3 text-sm">
              <button
                onClick={() => onEdit(item)}
                disabled={Boolean(actionBusy)}
                className="hover:underline disabled:opacity-50"
              >
                Edit
              </button>
              {!item.is_active ? (
                <button
                  onClick={() => onActivate(item)}
                  disabled={Boolean(actionBusy)}
                  className="hover:underline disabled:opacity-50"
                >
                  {actionBusy === `activate-${item.id}` ? "Activating…" : "Activate"}
                </button>
              ) : null}
              <button
                onClick={() => onDelete(item)}
                disabled={Boolean(actionBusy)}
                className="text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
              >
                Delete
              </button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

/** Hook helper: load catalog keyed by key. */
export function useKnowledgeCatalog() {
  const [catalog, setCatalog] = useState<Record<string, KnowledgeCatalogEntry>>({});
  useEffect(() => {
    api
      .listKnowledgeCatalog()
      .then((rows) => {
        const map: Record<string, KnowledgeCatalogEntry> = {};
        for (const row of rows) map[row.key] = row;
        setCatalog(map);
      })
      .catch(() => setCatalog({}));
  }, []);
  return catalog;
}
