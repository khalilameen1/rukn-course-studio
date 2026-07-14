"use client";

import type { AdminKnowledgeItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";

// Human-friendly title/description for the fixed Rukn keys seeded by
// backend/app/seed_admin_knowledge.py - any other key falls back to its
// raw title/key below instead of being hidden or mislabeled.
const KNOWN_KEY_INFO: Record<string, { title: string; description: string }> = {
  rukn_core_rules: {
    title: "Core Voice & Delivery Rules",
    description: "Non-negotiable tone and delivery rules for every generated script.",
  },
  rukn_practical_course_rules: {
    title: "Practical Course Structure Rules",
    description: "Connected modules, bridge projects, and real-world examples.",
  },
  rukn_writing_style: {
    title: "Writing Style Rules",
    description: "Short, natural sentences - no filler, no clichés.",
  },
  rukn_forbidden_phrases: {
    title: "Forbidden Phrases",
    description: "Phrases that must never appear in a generated script.",
  },
  rukn_quality_rubric: {
    title: "Quality Rubric",
    description: "Checks applied when reviewing a course during generation.",
  },
  rukn_teleprompter_docx_contract: {
    title: "Teleprompter DOCX Contract",
    description: "Defines what the final DOCX is - and isn't.",
  },
  rukn_high_signal_reel_doctrine: {
    title: "High-Signal Reel Doctrine",
    description:
      "Hooks, organic loops, variable length, adversarial Draft A/B/Critic/Master - viral without bait.",
  },
  rukn_generation_presets: {
    title: "Generation Presets",
    description: "Named presets for AI-provider use.",
  },
};

const ITEM_TYPE_LABELS: Record<string, string> = {
  markdown: "Markdown",
  json: "JSON",
  docx_template: "DOCX template",
};

export default function KnowledgeItemGrid({
  items,
  onEdit,
  onDelete,
  onActivate,
}: {
  items: AdminKnowledgeItem[];
  onEdit: (item: AdminKnowledgeItem) => void;
  onDelete: (item: AdminKnowledgeItem) => void;
  onActivate: (item: AdminKnowledgeItem) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const known = KNOWN_KEY_INFO[item.key];
        return (
          <Card key={item.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium">{known?.title ?? item.title}</p>
                <p className="mt-0.5 font-mono text-xs text-muted">{item.key}</p>
              </div>
              <StatusBadge
                label={item.is_active ? "active" : "inactive"}
                tone={item.is_active ? "success" : "neutral"}
              />
            </div>

            <p className="text-sm text-muted">{known?.description ?? item.title}</p>

            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="rounded-full border border-border px-2 py-0.5">
                {ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}
              </span>
              <span>v{item.version}</span>
            </div>

            <div className="mt-1 flex gap-3 text-sm">
              <button onClick={() => onEdit(item)} className="hover:underline">
                Edit
              </button>
              {!item.is_active ? (
                <button onClick={() => onActivate(item)} className="hover:underline">
                  Activate
                </button>
              ) : null}
              <button
                onClick={() => onDelete(item)}
                className="text-red-600 hover:underline dark:text-red-400"
              >
                Delete
              </button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
