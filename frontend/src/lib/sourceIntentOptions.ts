// User-facing “How should ROKN use this source?” options for Create Course UX.
// Maps to backend SourceCategory — keep enum values internal in API calls.

import type { SourceCategory } from "@/lib/types";

export type SourceIntentId =
  | "knowledge"
  | "colloquial"
  | "mixed_draft"
  | "user_notes"
  | "classify";

export interface SourceIntentOption {
  id: SourceIntentId;
  label: string;
  description: string;
  category: SourceCategory;
}

export const SOURCE_INTENT_OPTIONS: SourceIntentOption[] = [
  {
    id: "knowledge",
    label: "Knowledge source for this course",
    description:
      "Use useful concepts, facts, objections, and practical points after filtering.",
    category: "scientific_reference",
  },
  {
    id: "colloquial",
    label: "Natural spoken language sample only",
    description:
      "Only helps avoid stiff or translated Arabic. Not used for facts, hooks, structure, or examples.",
    category: "flow_reference",
  },
  {
    id: "mixed_draft",
    label: "Previous mixed-quality AI course draft",
    description:
      "May contain useful ideas and defects. ROKN extracts candidates and discards weak, outdated, or off-promise parts.",
    category: "mixed_quality_ai_course_draft",
  },
  {
    id: "user_notes",
    label: "User notes",
    description: "Your direct instructions for this course.",
    category: "user_notes",
  },
  {
    id: "classify",
    label: "Let ROKN classify",
    description: "Use this if you are not sure.",
    category: "raw_material",
  },
];

const INTENT_BY_CATEGORY: Record<SourceCategory, SourceIntentId> = {
  scientific_reference: "knowledge",
  transcript: "knowledge",
  flow_reference: "colloquial",
  mixed_quality_ai_course_draft: "mixed_draft",
  old_course: "mixed_draft",
  user_notes: "user_notes",
  raw_material: "classify",
};

export function intentIdForCategory(category: SourceCategory): SourceIntentId {
  return INTENT_BY_CATEGORY[category] ?? "classify";
}

export function categoryForIntent(intent: SourceIntentId): SourceCategory {
  return SOURCE_INTENT_OPTIONS.find((o) => o.id === intent)?.category ?? "raw_material";
}

export function intentLabelForCategory(category: SourceCategory): string {
  const id = intentIdForCategory(category);
  return SOURCE_INTENT_OPTIONS.find((o) => o.id === id)?.label ?? "Source";
}

export function intentDescriptionForCategory(category: SourceCategory): string {
  const id = intentIdForCategory(category);
  return SOURCE_INTENT_OPTIONS.find((o) => o.id === id)?.description ?? "";
}
