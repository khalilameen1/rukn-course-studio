"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getToken,
  hasScope,
  SCOPE_ADMIN_KNOWLEDGE,
  SCOPE_AI_USAGE,
} from "@/lib/auth";

const PUBLIC_PATHS = new Set(["/login"]);

/**
 * Client-side gate: redirects to /login when there's no stored token.
 * Also blocks /admin and /ai-usage without the matching scope (server still enforces).
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const isPublicPath = PUBLIC_PATHS.has(pathname);
    if (!isPublicPath && !getToken()) {
      router.replace("/login");
      return;
    }
    if (
      !isPublicPath &&
      (pathname === "/admin" || pathname.startsWith("/admin/")) &&
      !hasScope(SCOPE_ADMIN_KNOWLEDGE)
    ) {
      router.replace("/courses");
      return;
    }
    if (
      !isPublicPath &&
      (pathname === "/ai-usage" || pathname.startsWith("/ai-usage/")) &&
      !hasScope(SCOPE_AI_USAGE)
    ) {
      router.replace("/courses");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReady(true);
  }, [pathname, router]);

  if (!ready) return null;
  return <>{children}</>;
}
