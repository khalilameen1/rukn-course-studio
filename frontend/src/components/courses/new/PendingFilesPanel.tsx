"use client";

import type { Priority, SourceCategory } from "@/lib/types";
import { intentLabelForCategory } from "@/lib/sourceIntentOptions";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";

export type PendingFileItem = {
  id: string;
  kind: "file";
  file: File;
  title: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
};

function fileIcon(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "PDF";
  if (ext === "docx" || ext === "doc") return "DOC";
  if (ext === "md") return "MD";
  return "TXT";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PendingFilesPanel({
  files,
  disabled,
  onRemove,
}: {
  files: PendingFileItem[];
  disabled?: boolean;
  onRemove: (id: string) => void;
}) {
  if (files.length === 0) {
    return (
      <EmptyState
        title="No files queued"
        description="Uploaded files appear here as source cards before you save the course."
      />
    );
  }

  function handleRemove(item: PendingFileItem) {
    if (!confirm(`Remove "${item.file.name}" from this course?`)) return;
    onRemove(item.id);
  }

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Source cards</h3>
        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
          {files.length}
        </span>
      </div>
      <ul className="grid gap-2">
        {files.map((item) => (
          <li key={item.id} className="nc-source-card">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-xs font-bold text-accent"
              aria-hidden
            >
              {fileIcon(item.file.name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-sm font-medium text-foreground">{item.file.name}</p>
                <StatusBadge label="Uploaded" tone="info" />
              </div>
              <p className="mt-0.5 text-xs text-muted">
                {formatSize(item.file.size)} · {intentLabelForCategory(item.source_category)}
              </p>
              <p className="mt-0.5 text-xs text-muted">
                {item.include_in_generation ? "Will be used in generation" : "Saved but excluded from generation"}
              </p>
            </div>
            <button
              type="button"
              disabled={disabled}
              onClick={() => handleRemove(item)}
              className="shrink-0 rounded-lg px-2 py-1 text-xs text-muted hover:bg-surface-muted hover:text-red-600"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
