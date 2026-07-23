// Human-friendly labels + one-line helper text for GenerationPreset.
// Mirrors backend/app/models/enums.py GenerationPreset - keep in sync manually.
// Intentionally the ONLY control surfaced for this - no raw temperature
// input anywhere in the UI.

import type { GenerationPreset } from "@/lib/types";

export interface GenerationPresetOption {
  value: GenerationPreset;
  label: string;
  helper: string;
}

/** Presets offered in create/edit forms. Fusion kept for legacy course rows. */
export const GENERATION_PRESET_OPTIONS: GenerationPresetOption[] = [
  {
    value: "conservative",
    label: "Conservative",
    helper: "Cautious, low-variation — best for review/correction passes.",
  },
  {
    value: "balanced",
    label: "Balanced (recommended)",
    helper: "The default — normal lesson/script generation.",
  },
  {
    value: "creative",
    label: "Creative",
    helper: "More variety — best for exploring different openings/examples.",
  },
  {
    value: "fusion",
    label: "Fusion (uses Balanced)",
    helper: "Legacy option — currently identical to Balanced.",
  },
  {
    value: "strict_teleprompter",
    label: "Strict Teleprompter",
    helper: "Strictest enforcement of the spoken-script-only export contract.",
  },
];

function toLookup(options: GenerationPresetOption[], key: "label" | "helper") {
  return options.reduce(
    (acc, opt) => {
      acc[opt.value] = opt[key];
      return acc;
    },
    {} as Record<GenerationPreset, string>,
  );
}

export const GENERATION_PRESET_LABELS: Record<GenerationPreset, string> = toLookup(
  GENERATION_PRESET_OPTIONS,
  "label",
);

export const GENERATION_PRESET_HELPERS: Record<GenerationPreset, string> = toLookup(
  GENERATION_PRESET_OPTIONS,
  "helper",
);

export const DEFAULT_GENERATION_PRESET: GenerationPreset = "balanced";
