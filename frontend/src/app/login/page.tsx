"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, formatApiErrorForDisplay } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { API_BASE_URL, API_BASE_URL_CONFIGURED } from "@/lib/config";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";

type CheckStatus =
  | { state: "loading" }
  | { state: "ok"; detail: string }
  | { state: "error"; detail: string };

type PublicDiagnostics = {
  ok: boolean;
  auth_enabled: boolean;
  auth_secret_key_configured: boolean;
  database_backend: string;
  ai_provider_ready: boolean;
};

/**
 * Public probe only — full CORS/model/error detail requires an authenticated
 * call to /auth/diagnostics/full after login.
 */
function useDiagnosticsChecks() {
  const [health, setHealth] = useState<CheckStatus>({ state: "loading" });
  const [diagnostics, setDiagnostics] = useState<CheckStatus>({ state: "loading" });
  const [diagnosticsData, setDiagnosticsData] = useState<PublicDiagnostics | null>(null);

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
      const res = await api.login(username, password);
      setToken(res.access_token, res.scopes);
      router.replace("/");
    } catch (err) {
      setError(formatApiErrorForDisplay(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Sign in"
        description="Internal workspace — use your studio credentials."
      />

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="rounded-md border border-border bg-transparent px-3 py-2 outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="rounded-md border border-border bg-transparent px-3 py-2 outline-none"
            />
          </label>
          {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
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
              auth_enabled: {String(diagnosticsData.auth_enabled)} · database:{" "}
              {diagnosticsData.database_backend}
            </p>
            <p>
              auth_secret_key_configured:{" "}
              {String(diagnosticsData.auth_secret_key_configured)} · ai_provider_ready:{" "}
              {String(diagnosticsData.ai_provider_ready)}
            </p>
            <p className="text-muted">
              Full CORS/storage/AI detail is available after sign-in via authenticated diagnostics.
            </p>
          </>
        ) : null}
      </Card>
    </div>
  );
}
