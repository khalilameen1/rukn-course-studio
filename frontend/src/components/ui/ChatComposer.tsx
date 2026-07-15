"use client";

import { useEffect, useRef, type ReactNode } from "react";

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ChatComposer({
  value,
  onChange,
  onSubmit,
  onClear,
  placeholder,
  helper,
  disabled,
  submitLabel = "Send",
  showSend = true,
  minRows = 1,
  maxHeight = 160,
  id,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  onClear?: () => void;
  placeholder: string;
  helper?: string;
  disabled?: boolean;
  submitLabel?: string;
  showSend?: boolean;
  minRows?: number;
  maxHeight?: number;
  id?: string;
  children?: ReactNode;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, maxHeight)}px`;
  }, [value, maxHeight]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!onSubmit) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSubmit();
    }
  }

  return (
    <div className="nc-composer-card">
      {children ? <div className="nc-composer-card-tools">{children}</div> : null}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          id={id}
          disabled={disabled}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={minRows}
          className="nc-composer-input flex-1"
        />
        {showSend && onSubmit ? (
          <button
            type="button"
            disabled={disabled || !value.trim()}
            onClick={onSubmit}
            aria-label={submitLabel}
            title={submitLabel}
            className="nc-composer-send"
          >
            <SendIcon />
          </button>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        {helper ? <p className="text-xs text-muted">{helper}</p> : <span />}
        {onClear && value.trim() ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onClear}
            className="text-xs text-muted hover:text-foreground"
          >
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
