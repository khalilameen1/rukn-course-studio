"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { API_BASE_URL, API_BASE_URL_CONFIGURED } from "@/lib/config";
import type { BuildInfoResponse } from "@/lib/types";

/** Build-time stamp from Next (inlined at compile). Diagnostic only. */
const FRONTEND_BUILD_TIME =
  process.env.NEXT_PUBLIC_BUILD_TIME ??
  process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ??
  "unknown (set NEXT_PUBLIC_BUILD_TIME at build if needed)";

/**
 * Compact deploy visibility card for Admin Knowledge.
 * Shows which frontend/backend builds are live — no secrets.
 */
export default function DeployDiagnostics() {
  const [info, setInfo] = useState<BuildInfoResponse | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const health = await api.health();
        if (cancelled) return;
        setReachable(health.status === "ok");
        const build = await api.buildInfo();
        if (!cancelled) setInfo(build);
      } catch (err) {
        if (cancelled) return;
        setReachable(false);
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Backend unreachable",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <details className="rounded-lg border border-border bg-surface-muted p-3 text-xs text-muted">
      <summary className="cursor-pointer font-medium text-foreground">
        Deploy diagnostics (no secrets)
      </summary>
      <dl className="mt-3 grid gap-1.5 sm:grid-cols-2">
        <div>
          <dt className="inline text-foreground">Frontend build: </dt>
          <dd className="inline">{FRONTEND_BUILD_TIME}</dd>
        </div>
        <div>
          <dt className="inline text-foreground">API base (baked): </dt>
          <dd className="inline break-all">
            {API_BASE_URL_CONFIGURED ? API_BASE_URL : "(not configured — localhost fallback)"}
          </dd>
        </div>
        <div>
          <dt className="inline text-foreground">Backend reachable: </dt>
          <dd className="inline">
            {reachable == null ? "…" : reachable ? "yes" : "no"}
          </dd>
        </div>
        {info ? (
          <>
            <div>
              <dt className="inline text-foreground">Backend commit: </dt>
              <dd className="inline">{info.git_commit}</dd>
            </div>
            <div>
              <dt className="inline text-foreground">Backend build time: </dt>
              <dd className="inline">{info.build_time}</dd>
            </div>
            <div>
              <dt className="inline text-foreground">Database type: </dt>
              <dd className="inline">{info.database_type}</dd>
            </div>
            <div>
              <dt className="inline text-foreground">AI provider: </dt>
              <dd className="inline">{info.ai_provider}</dd>
            </div>
            <div>
              <dt className="inline text-foreground">Auth enabled: </dt>
              <dd className="inline">{info.auth_enabled ? "yes" : "no"}</dd>
            </div>
          </>
        ) : null}
      </dl>
      {error ? <p className="mt-2 text-red-600 dark:text-red-400">{error}</p> : null}
    </details>
  );
}
