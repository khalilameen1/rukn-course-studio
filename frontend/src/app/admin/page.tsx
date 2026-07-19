"use client";

import { useCallback, useEffect, useState } from "react";
import KnowledgeItemGrid, {
  useKnowledgeCatalog,
} from "@/components/admin/KnowledgeItemGrid";
import PageHeader from "@/components/ui/PageHeader";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type {
  AdminKnowledgeItem,
  CourseStandardManifest,
} from "@/lib/types";

export default function AdminKnowledgePage() {
  const [items, setItems] = useState<AdminKnowledgeItem[]>([]);
  const [manifest, setManifest] = useState<CourseStandardManifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const catalog = useKnowledgeCatalog();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rows, packageManifest] = await Promise.all([
        api.listKnowledgeItems(),
        api.getKnowledgeManifest(),
      ]);
      setItems(rows);
      setManifest(packageManifest);
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Standard fetch-on-mount; refresh is also reused after a confirmed reset.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleReset() {
    if (resetting) return;
    if (
      !confirm(
        "Reset to the shipped RUKN v1.3 package? This permanently deletes " +
          "all non-canonical rows, retired versions, and old Admin Knowledge snapshots.",
      )
    ) {
      return;
    }
    setResetting(true);
    setError(null);
    try {
      await api.resetKnowledgeStandard();
      await refresh();
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="RUKN Course Standard"
        description="The immutable control system used by every course-generation stage."
      />

      <section className="rounded-xl border border-border bg-surface-muted/50 p-4">
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <p className="text-muted">Standard version</p>
            <p className="mt-1 font-mono text-foreground">
              {manifest?.standard_version ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-muted">Canonical files</p>
            <p className="mt-1 font-medium text-foreground">
              {manifest ? `${items.length}/${manifest.file_count}` : "—"}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-muted">Fingerprint</p>
            <p className="mt-1 truncate font-mono text-xs text-foreground" title={manifest?.fingerprint}>
              {manifest?.fingerprint ?? "—"}
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
          <p className="max-w-2xl text-sm text-muted">
            Read-only by design. Custom knowledge, inactive archives, and parallel rule paths are disabled.
          </p>
          <button
            type="button"
            className="btn-secondary"
            disabled={resetting}
            onClick={handleReset}
          >
            {resetting ? "Resetting…" : "Reset canonical package"}
          </button>
        </div>
      </section>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-muted">Loading canonical package…</p>
      ) : (
        <KnowledgeItemGrid items={items} catalog={catalog} />
      )}
    </div>
  );
}
