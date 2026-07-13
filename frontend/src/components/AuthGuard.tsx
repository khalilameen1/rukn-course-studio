"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/auth";

const PUBLIC_PATHS = new Set(["/login"]);

/**
 * Client-side gate: redirects to /login when there's no stored token.
 * Doesn't validate the token against the backend - an expired/invalid
 * token is instead caught on the first API call (see lib/api.ts), which
 * clears it and redirects the same way.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Runs on mount and on every route change to decide whether this route
    // needs a redirect to /login; not derivable from render since it reads
    // localStorage (a browser-only external system).
    const isPublicPath = PUBLIC_PATHS.has(pathname);
    if (!isPublicPath && !getToken()) {
      router.replace("/login");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReady(true);
  }, [pathname, router]);

  if (!ready) return null;
  return <>{children}</>;
}
