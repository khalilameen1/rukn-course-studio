"use client";

import type { SourceIntentId } from "@/lib/sourceIntentOptions";
import { SOURCE_INTENT_OPTIONS } from "@/lib/sourceIntentOptions";

export default function SourceIntentPicker({
  value,
  onChange,
  disabled,
  compact,
}: {
  value: SourceIntentId;
  onChange: (intent: SourceIntentId) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  const selected = SOURCE_INTENT_OPTIONS.find((o) => o.id === value);

  if (compact) {
    return (
      <label className="block text-sm">
        <span className="nc-field-label">How should ROKN use this source?</span>
        <select
          disabled={disabled}
          value={value}
          onChange={(e) => onChange(e.target.value as SourceIntentId)}
          className="field-input text-sm"
        >
          {SOURCE_INTENT_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
        {selected ? <p className="mt-1.5 text-xs text-muted">{selected.description}</p> : null}
      </label>
    );
  }

  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="text-sm font-medium text-foreground">How should ROKN use this source?</legend>
      <div className="grid gap-2">
        {SOURCE_INTENT_OPTIONS.map((opt) => {
          const active = opt.id === value;
          return (
            <label
              key={opt.id}
              className={`nc-intent-option${active ? " nc-intent-option-active" : ""}`}
            >
              <input
                type="radio"
                name="source-intent"
                value={opt.id}
                checked={active}
                onChange={() => onChange(opt.id)}
                className="sr-only"
              />
              <span className="block text-sm font-medium text-foreground">{opt.label}</span>
              <span className="mt-0.5 block text-xs text-muted">{opt.description}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
