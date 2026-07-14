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
    label: "Natural spoken language sample",
    helper:
      "Use this when the transcript may be unrelated to the course. It only helps the script sound naturally spoken, not translated or robotic. It will not be used for facts, hooks, course structure, or examples.",
  },
  {
    value: "mixed_quality_ai_course_draft",
    label: "Previous mixed-quality AI course draft",
    helper:
      "Use this for previous AI-generated course drafts that may contain useful ideas but also defects. The system will extract useful candidates, detect defects, verify claims elsewhere, and rebuild the course in ROKN quality. (مسودة كورس سابقة مختلطة الجودة)",
  },
  {
    value: "old_course",
    label: "Previous course/attempt (legacy)",
    helper:
      "Same mixed-quality draft handling as “Previous mixed-quality AI course draft” — useful candidates + defects; not a quality reference. Prefer the dedicated mixed-quality type for new uploads.",
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
