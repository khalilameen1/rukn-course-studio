import type { ReactNode } from "react";

const PADDING_CLASSES = {
  none: "",
  sm: "p-3",
  md: "p-4 sm:p-5",
  lg: "p-5 sm:p-6",
} as const;

/**
 * Bordered surface panel used everywhere instead of ad-hoc
 * `rounded-lg border ...` class strings repeated across components.
 */
export default function Card({
  children,
  className = "",
  padding = "md",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  padding?: keyof typeof PADDING_CLASSES;
  /** Soft hover elevation for clickable cards (Home links, etc.). */
  interactive?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-border bg-surface shadow-[var(--shadow-sm)] ${
        interactive
          ? "transition-[box-shadow,transform,border-color] hover:-translate-y-0.5 hover:border-[rgba(15,118,110,0.25)] hover:shadow-[var(--shadow-md)]"
          : ""
      } ${PADDING_CLASSES[padding]} ${className}`}
    >
      {children}
    </div>
  );
}
