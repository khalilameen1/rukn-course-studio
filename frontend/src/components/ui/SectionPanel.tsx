import type { ReactNode } from "react";

/**
 * A labeled zone/section: small uppercase label + content. Used to build
 * the 3-zone course workspace (Inputs / Work / Output) and to group
 * related fields inside forms (e.g. "Course basics", "Target learner").
 */
export default function SectionPanel({
  label,
  description,
  children,
  framed = false,
}: {
  label: string;
  description?: string;
  children: ReactNode;
  /** When true, wraps the zone in the soft workspace-zone frame. */
  framed?: boolean;
}) {
  const body = (
    <>
      <div>
        <h2 className="text-[11px] font-semibold tracking-[0.08em] text-accent uppercase">
          {label}
        </h2>
        {description ? <p className="mt-0.5 text-sm text-muted">{description}</p> : null}
      </div>
      {children}
    </>
  );

  if (framed) {
    return <section className="workspace-zone flex flex-col gap-3">{body}</section>;
  }

  return <section className="flex flex-col gap-3">{body}</section>;
}
