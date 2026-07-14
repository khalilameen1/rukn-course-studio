// Human-friendly labels + one-line helper text for SourceCategory.
// Mirrors backend/app/models/enums.py SourceCategory - keep in sync manually.

import type { SourceCategory } from "@/lib/types";

export interface SourceCategoryOption {
  value: SourceCategory;
  label: string;
  helper: string;
}

export const SOURCE_CATEGORY_OPTIONS: SourceCategoryOption[] = [
  {
    value: "scientific_reference",
    label: "Scientific / factual reference",
    helper:
      "Factual or educational material — will be summarized and rephrased into the course, not copied.",
  },
  {
    value: "flow_reference",
    label: "Flow / style reference",
    helper: "A speaking/flow example — used for pacing and tone only, never treated as facts.",
  },
  {
    value: "old_course",
    label: "Previous course/attempt",
    helper: "An earlier version of this course — reused selectively, not blindly repeated.",
  },
  {
    value: "user_notes",
    label: "My notes / instructions",
    helper: "Your direct instructions — highest priority, always respected.",
  },
  {
    value: "raw_material",
    label: "Raw / mixed material",
    helper: "Unsorted material — the system will pick out only what's useful.",
  },
  {
    value: "transcript",
    label: "Transcript",
    helper: "Spoken lesson/transcript for this course — knowledge only, never Admin Knowledge.",
  },
];

function toLookup(options: SourceCategoryOption[], key: "label" | "helper") {
  return options.reduce(
    (acc, opt) => {
      acc[opt.value] = opt[key];
      return acc;
    },
    {} as Record<SourceCategory, string>,
  );
}

export const SOURCE_CATEGORY_LABELS: Record<SourceCategory, string> = toLookup(
  SOURCE_CATEGORY_OPTIONS,
  "label",
);

export const SOURCE_CATEGORY_HELPERS: Record<SourceCategory, string> = toLookup(
  SOURCE_CATEGORY_OPTIONS,
  "helper",
);
