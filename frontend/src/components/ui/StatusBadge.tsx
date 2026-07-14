export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-border bg-surface-muted text-muted",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
  info: "border-teal-200 bg-accent-soft text-accent",
};

export default function StatusBadge({
  label,
  tone = "neutral",
  dot = false,
}: {
  label: string;
  tone?: StatusTone;
  /** Small leading dot, useful for live/connectivity states. */
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${TONE_CLASSES[tone]}`}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {label}
    </span>
  );
}
