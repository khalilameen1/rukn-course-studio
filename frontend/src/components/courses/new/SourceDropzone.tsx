"use client";

import { useCallback, useRef, useState } from "react";
import type { Priority } from "@/lib/types";
import type { SourceIntentId } from "@/lib/sourceIntentOptions";
import SourceIntentPicker from "@/components/courses/new/SourceIntentPicker";

const ACCEPT = ".docx,.pdf,.txt,.md";
const FORMATS = ["PDF", "DOCX", "TXT", "MD"];
const ALLOWED_EXTENSIONS = new Set([".docx", ".pdf", ".txt", ".md"]);

function UploadIcon() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden className="text-accent">
      <path
        d="M12 16V4m0 0l4 4m-4-4L8 8"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 14v2a2 2 0 002 2h12a2 2 0 002-2v-2"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function SourceDropzone({
  disabled,
  fileIntent,
  filePriority,
  includeGen,
  onFileIntentChange,
  onFilePriorityChange,
  onIncludeGenChange,
  onFileSelected,
  onPasteInstead,
}: {
  disabled?: boolean;
  fileIntent: SourceIntentId;
  filePriority: Priority;
  includeGen: boolean;
  onFileIntentChange: (intent: SourceIntentId) => void;
  onFilePriorityChange: (priority: Priority) => void;
  onIncludeGenChange: (include: boolean) => void;
  onFileSelected: (file: File) => void;
  onPasteInstead?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [pickError, setPickError] = useState<string | null>(null);

  const pickFile = useCallback(
    (file: File | null) => {
      if (!file || disabled) return;
      setPickError(null);
      const ext = file.name.includes(".")
        ? `.${file.name.split(".").pop()?.toLowerCase()}`
        : "";
      if (!ALLOWED_EXTENSIONS.has(ext)) {
        setPickError(
          ext === ".doc"
            ? "Classic .doc is not supported. Save as .docx, .pdf, .txt, or .md."
            : `Unsupported file type${ext ? ` (${ext})` : ""}. Allowed: .docx, .pdf, .txt, .md.`,
        );
        return;
      }
      onFileSelected(file);
    },
    [disabled, onFileSelected],
  );

  return (
    <section className="flex flex-col gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-accent">Step 2</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight">Course sources</h2>
        <p className="mt-1 text-sm text-muted">Upload references for this course only.</p>
      </div>

      <div
        role="button"
        tabIndex={0}
        data-active={dragActive}
        className="nc-dropzone"
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!disabled) setDragActive(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!disabled) setDragActive(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragActive(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragActive(false);
          pickFile(e.dataTransfer.files?.[0] ?? null);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            pickFile(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        <UploadIcon />
        <div>
          <p className="text-sm font-medium text-foreground">Upload course sources</p>
          <p className="mt-1 text-xs text-muted">Drag and drop here, or click to browse</p>
        </div>
        <div className="flex flex-wrap justify-center gap-1.5">
          {FORMATS.map((fmt) => (
            <span
              key={fmt}
              className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-[0.6875rem] font-medium text-muted"
            >
              {fmt}
            </span>
          ))}
        </div>
        {pickError ? (
          <p className="text-center text-xs text-red-600 dark:text-red-400">{pickError}</p>
        ) : null}
        {onPasteInstead ? (
          <button
            type="button"
            className="btn-ghost text-xs"
            onClick={(e) => {
              e.stopPropagation();
              onPasteInstead();
            }}
          >
            Paste text instead
          </button>
        ) : null}
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-surface-muted/30 p-4">
        <SourceIntentPicker
          disabled={disabled}
          value={fileIntent}
          onChange={onFileIntentChange}
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="w-32 text-sm">
            <span className="nc-field-label">Priority</span>
            <select
              disabled={disabled}
              value={filePriority}
              onChange={(e) => onFilePriorityChange(e.target.value as Priority)}
              className="field-input text-sm"
            >
              <option value="high">High</option>
              <option value="medium">Normal</option>
              <option value="low">Low</option>
            </select>
          </label>
          <label className="flex items-center gap-2 pb-2 text-sm text-muted">
            <input
              type="checkbox"
              disabled={disabled}
              checked={includeGen}
              onChange={(e) => onIncludeGenChange(e.target.checked)}
              className="rounded border-border text-accent"
            />
            Use in generation
          </label>
        </div>
      </div>
    </section>
  );
}
