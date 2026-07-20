"use client";

import { useEffect, useRef } from "react";
import type { Priority, SourceCategory } from "@/lib/types";
import type { SourceIntentId } from "@/lib/sourceIntentOptions";
import { intentLabelForCategory } from "@/lib/sourceIntentOptions";
import ChatComposer from "@/components/ui/ChatComposer";
import SourceIntentPicker from "@/components/courses/new/SourceIntentPicker";
import EmptyState from "@/components/ui/EmptyState";

export type ChatMessage = {
  id: string;
  title: string;
  text: string;
  source_category: SourceCategory;
  priority: Priority;
  include_in_generation: boolean;
  restored?: boolean;
};

export default function NotesChatPanel({
  messages,
  disabled,
  draftText,
  draftTitle,
  pasteIntent,
  filePriority,
  includeGen,
  onDraftTextChange,
  onDraftTitleChange,
  onPasteIntentChange,
  onFilePriorityChange,
  onIncludeGenChange,
  onSend,
  onRemove,
  sectionId,
}: {
  messages: ChatMessage[];
  disabled?: boolean;
  draftText: string;
  draftTitle: string;
  pasteIntent: SourceIntentId;
  filePriority: Priority;
  includeGen: boolean;
  onDraftTextChange: (text: string) => void;
  onDraftTitleChange: (title: string) => void;
  onPasteIntentChange: (intent: SourceIntentId) => void;
  onFilePriorityChange: (priority: Priority) => void;
  onIncludeGenChange: (include: boolean) => void;
  onSend: () => void;
  onRemove: (id: string) => void;
  sectionId?: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  function handleRemove(id: string, title: string) {
    if (!confirm(`Remove "${title || "this source"}" from this course?`)) return;
    onRemove(id);
  }

  return (
    <section id={sectionId} className="flex flex-col gap-3">
      <div>
        <h3 className="text-sm font-semibold text-foreground">Paste source text</h3>
        <p className="text-xs text-muted">These sources belong only to this course — not the Course Standard.</p>
      </div>

      <div className="nc-chat-panel">
        <div ref={scrollRef} className="nc-chat-scroll">
          {messages.length === 0 ? (
            <EmptyState
              title="No pasted sources yet"
              description="Add PDFs, transcripts, old drafts, or notes for this course. You can also generate without sources if the brief is enough."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {messages.map((msg) => (
                <li key={msg.id} className="group flex flex-col items-end gap-1">
                  <div className="nc-source-card w-full max-w-full">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-foreground">
                          {msg.title || "Pasted source"}
                        </p>
                        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[0.65rem] font-medium text-accent">
                          Ready to upload
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-xs text-muted">
                        {msg.text}
                      </p>
                      <p className="mt-2 text-xs text-muted">
                        {intentLabelForCategory(msg.source_category)}
                        {msg.restored ? " · restored draft" : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => handleRemove(msg.id, msg.title)}
                      className="shrink-0 rounded-lg px-2 py-1 text-xs text-muted hover:bg-surface-muted hover:text-red-600"
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="nc-composer border-t border-border bg-surface-muted/30 p-3 sm:p-4">
          <input
            type="text"
            disabled={disabled}
            value={draftTitle}
            onChange={(e) => onDraftTitleChange(e.target.value)}
            placeholder="Optional title (e.g. Module 1 transcript)"
            className="mb-3 w-full rounded-xl border-0 bg-surface px-3 py-2 text-sm outline-none ring-1 ring-border focus:ring-accent/30"
          />
          <div className="mb-3 grid gap-3 lg:grid-cols-2">
            <SourceIntentPicker
              compact
              disabled={disabled}
              value={pasteIntent}
              onChange={onPasteIntentChange}
            />
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-sm">
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
              <label className="flex items-center gap-2 pb-2 text-xs text-muted">
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={includeGen}
                  onChange={(e) => onIncludeGenChange(e.target.checked)}
                />
                Use in generation
              </label>
            </div>
          </div>
          <ChatComposer
            value={draftText}
            onChange={onDraftTextChange}
            onSubmit={onSend}
            onClear={() => onDraftTextChange("")}
            disabled={disabled}
            submitLabel="Add source"
            placeholder="Paste a transcript, notes, or course material here…"
            helper="Enter to add · Shift+Enter for a new line"
            minRows={2}
            maxHeight={160}
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={disabled || !draftText.trim()}
              onClick={onSend}
            >
              Add source
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
