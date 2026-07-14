"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import LogoutButton from "@/components/LogoutButton";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/admin", label: "Admin Knowledge" },
  { href: "/courses", label: "Courses" },
  { href: "/ai-usage", label: "AI Usage" },
];

/**
 * Top bar (product name + nav) and main content wrapper shared by every
 * page. Replaces the inline header markup that used to live in
 * app/layout.tsx.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const hideShellChrome = pathname === "/login";

  return (
    <div className="flex min-h-full flex-col">
      {!hideShellChrome ? (
        <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-3.5 sm:flex-row sm:items-center sm:justify-between">
            <Link href="/" className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_0_3px_var(--accent-soft)]"
              />
              <span className="text-sm font-semibold tracking-tight text-foreground">
                ROKN Course Studio
              </span>
            </Link>
            <nav className="flex flex-wrap items-center gap-1 text-sm">
              {NAV_LINKS.map((link) => {
                const active =
                  link.href === "/"
                    ? pathname === "/"
                    : pathname === link.href || pathname.startsWith(`${link.href}/`);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={
                      active
                        ? "rounded-full bg-accent-soft px-3 py-1.5 font-medium text-accent"
                        : "rounded-full px-3 py-1.5 text-muted hover:bg-surface-muted hover:text-foreground"
                    }
                  >
                    {link.label}
                  </Link>
                );
              })}
              <LogoutButton />
            </nav>
          </div>
        </header>
      ) : null}
      <main className="flex-1">
        <div
          className={
            hideShellChrome
              ? "mx-auto w-full max-w-md px-6 py-16"
              : "mx-auto w-full max-w-6xl px-6 py-10"
          }
        >
          {children}
        </div>
      </main>
    </div>
  );
}
