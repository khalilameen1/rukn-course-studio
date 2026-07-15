"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, formatApiErrorForDisplay } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { API_BASE_URL, API_BASE_URL_CONFIGURED } from "@/lib/config";
import type { DiagnosticsResponse } from "@/lib/types";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";

type CheckStatus =
  | { state: "loading" }
  | { state: "ok"; detail: string }
  | { state: "error"; detail: string };

/**
 * Temporary diagnostics block - see the "Login problem self-diagnosing"
 * task. Safe to keep around: /health and /auth/diagnostics are both
 * public and never return secrets (see backend/app/auth/diagnostics.py).
 * Remove once Render deployments have been stable for a while.
 */
function useDiagnosticsChecks() {
  const [health, setHealth] = useState<CheckStatus>({ state: "loading" });
  const [diagnostics, setDiagnostics] = useState<CheckStatus>({ state: "loading" });
  const [diagnosticsData, setDiagnosticsData] = useState<DiagnosticsResponse | null>(null);

  useEffect(() => {
    if (!API_BASE_URL_CONFIGURED) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setHealth({ state: "error", detail: "Backend API URL is not configured" });
      setDiagnostics({ state: "error", detail: "Backend API URL is not configured" });
      return;
    }

    api
      .health()
      .then((res) => setHealth({ state: "ok", detail: `${res.status} (${res.environment})` }))
      .catch((err) => setHealth({ state: "error", detail: describeError(err) }));

    api
      .diagnostics()
      .then((res) => {
        setDiagnosticsData(res);
        setDiagnostics({ state: "ok", detail: "reachable" });
      })
      .catch((err) => setDiagnostics({ state: "error", detail: describeError(err) }));
  }, []);

  return { health, diagnostics, diagnosticsData };
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.isNetworkError) return err.message;
    return err.status ? `HTTP ${err.status}: ${err.message}` : err.message;
  }
  return err instanceof Error ? err.message : "Unknown error";
}

function CheckLine({ label, check }: { label: string; check: CheckStatus }) {
  const detail = check.state === "loading" ? "checking..." : check.detail;
  const color =
    check.state === "loading"
      ? "text-muted"
      : check.state === "ok"
        ? "text-green-600 dark:text-green-500"
        : "text-red-600 dark:text-red-400";

  return (
    <p>
      {label}: <span className={color}>{detail}</span>
    </p>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { health, diagnostics, diagnosticsData } = useDiagnosticsChecks();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!API_BASE_URL_CONFIGURED) {
      setError("Backend API URL is not configured");
      return;
    }

    setSubmitting(true);
    try {
      const { access_token } = await api.login(username, password);
      setToken(access_token);
      router.replace("/");
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6">
      <PageHeader title="Sign in" description="ROKN Course Studio - internal access only." />

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Username
            <input
              required
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="field-input"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Password
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field-input"
            />
          </label>

          {error ? <p className="text-sm text-red-700">{error}</p> : null}

          <button
            type="submit"
            disabled={submitting}
            className="btn-primary w-fit"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </Card>

      <Card padding="sm" className="flex flex-col gap-1 text-xs text-muted">
        <p className="font-medium text-foreground">Deployment diagnostics</p>
        <p>
          API base URL:{" "}
          <span className={API_BASE_URL_CONFIGURED ? "" : "text-red-600 dark:text-red-400"}>
            {API_BASE_URL_CONFIGURED ? API_BASE_URL : "not configured"}
          </span>
        </p>
        <CheckLine label="Backend /health" check={health} />
        <CheckLine label="Backend /auth/diagnostics" check={diagnostics} />
        {diagnosticsData ? (
          <>
            <p>
              ai_provider: {diagnosticsData.ai_provider} · ready=
              {String(diagnosticsData.ai_provider_ready)}
              {diagnosticsData.ai_model_name ? ` · model=${diagnosticsData.ai_model_name}` : ""}
            </p>
            {diagnosticsData.provider_reachable ? (
              <p>
                provider_reachable: {diagnosticsData.provider_reachable}
                {diagnosticsData.last_successful_request_at
                  ? ` · last ok ${new Date(diagnosticsData.last_successful_request_at).toLocaleString()}`
                  : ""}
              </p>
            ) : null}
            {diagnosticsData.last_error_message ? (
              <p>
                last_error: {diagnosticsData.last_error_category ?? "unknown"} —{" "}
                {diagnosticsData.last_error_message}
              </p>
            ) : null}
            <p>
              auth_enabled: {String(diagnosticsData.auth_enabled)} · database:{" "}
              {diagnosticsData.database_backend}
            </p>
            <p>
              frontend_origin_configured: {String(diagnosticsData.frontend_origin_configured)}
              {diagnosticsData.frontend_origin_value ? ` (${diagnosticsData.frontend_origin_value})` : ""}
            </p>
            <p>cors_origins: {diagnosticsData.cors_origins.join(", ") || "(none)"}</p>
            <p>
              storage_dir: configured={String(diagnosticsData.storage_dir_configured)}, exists=
              {String(diagnosticsData.storage_dir_exists)}, writable=
              {String(diagnosticsData.storage_dir_writable)}
            </p>
          </>
        ) : null}
      </Card>
    </div>
  );
}
