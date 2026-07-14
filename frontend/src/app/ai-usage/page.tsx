"use client";

import { useEffect, useState } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { AIUsageSummary } from "@/lib/types";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";

function money(n: number): string {
  return `$${n.toFixed(4)}`;
}

export default function AIUsagePage() {
  const [summary, setSummary] = useState<AIUsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAIUsageSummary()
      .then(setSummary)
      .catch((err) => setError(formatApiErrorForDisplay(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="AI Usage / Operations"
        description="Estimated app usage from this product — not your real Anthropic account balance."
      />

      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {loading ? <p className="text-sm text-muted">Loading...</p> : null}

      {!loading && !error && summary ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <p className="text-xs font-medium tracking-wide text-muted uppercase">Provider</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <p className="text-lg font-semibold capitalize">{summary.provider}</p>
              <StatusBadge
                label={summary.provider === "fake" ? "Safe / no spend" : "Live"}
                tone={summary.provider === "fake" ? "info" : "warning"}
              />
            </div>
            <p className="mt-3 text-sm text-muted">Model</p>
            <p className="font-mono text-sm">{summary.model}</p>
            <p className="mt-3 text-sm text-muted">Default preset</p>
            <p className="text-sm capitalize">{summary.default_preset}</p>
          </Card>

          <Card>
            <p className="text-xs font-medium tracking-wide text-muted uppercase">
              Estimated app usage
            </p>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted">Today</p>
                <p className="text-xl font-semibold">{money(summary.estimated_cost_today_usd)}</p>
              </div>
              <div>
                <p className="text-xs text-muted">This month</p>
                <p className="text-xl font-semibold">{money(summary.estimated_cost_this_month_usd)}</p>
              </div>
            </div>
            <p className="mt-4 text-xs text-muted">
              These figures are app-side estimates from token counts. They are not live credit
              remaining from Anthropic.
            </p>
          </Card>

          <Card className="sm:col-span-2">
            <p className="text-xs font-medium tracking-wide text-muted uppercase">
              Latest request
            </p>
            {summary.last_request_status ? (
              <div className="mt-3 flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge
                    label={summary.last_request_status}
                    tone={summary.last_request_status === "ok" ? "success" : "danger"}
                  />
                  {summary.last_request_at ? (
                    <span className="text-sm text-muted">
                      {new Date(summary.last_request_at).toLocaleString()}
                    </span>
                  ) : null}
                </div>
                {summary.last_error_message ? (
                  <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
                    {summary.last_error_category ? `${summary.last_error_category}: ` : ""}
                    {summary.last_error_message}
                  </p>
                ) : (
                  <p className="text-sm text-muted">No recent provider error recorded.</p>
                )}
              </div>
            ) : (
              <EmptyState
                title="No usage events yet"
                description="Run a generation (even with Fake provider) to populate estimated usage here."
              />
            )}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
