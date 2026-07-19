"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import type { AdminKnowledgeItem } from "@/lib/types";

export type KnowledgeCatalogEntry = {
  key: string;
  title: string;
  description: string;
  order: number;
  file_path: string;
  standard_version: string;
  standard_fingerprint: string;
  read_only: boolean;
};

export default function KnowledgeItemGrid({
  items,
  catalog,
}: {
  items: AdminKnowledgeItem[];
  catalog: Record<string, KnowledgeCatalogEntry>;
}) {
  const ordered = [...items].sort(
    (left, right) =>
      (catalog[left.key]?.order ?? Number.MAX_SAFE_INTEGER) -
      (catalog[right.key]?.order ?? Number.MAX_SAFE_INTEGER),
  );
  return (
    <div className="flex flex-col gap-4">
      {ordered.map((item, index) => {
        const known = catalog[item.key];
        return (
          <Card key={item.id} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">
                  File {known?.order ?? index + 1} of 14
                </p>
                <p className="mt-1 font-medium">{known?.title ?? item.title}</p>
                <p className="mt-1 font-mono text-xs text-muted">{item.key}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge label="canonical" tone="success" />
                <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted">
                  read-only
                </span>
              </div>
            </div>
            <p className="font-mono text-xs text-muted">
              {known?.file_path ?? item.file_path}
            </p>
            <details className="rounded-lg border border-border bg-background/50 p-3">
              <summary className="cursor-pointer text-sm font-medium">View source</summary>
              <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-6 text-muted">
                {item.content_text}
              </pre>
            </details>
          </Card>
        );
      })}
    </div>
  );
}

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
