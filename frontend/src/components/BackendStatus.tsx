"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, API_BASE_URL_CONFIGURED } from "@/lib/config";
import StatusBadge, { type StatusTone } from "@/components/ui/StatusBadge";

type Status = "checking" | "online" | "offline" | "unconfigured";

const TONE: Record<Status, StatusTone> = {
  checking: "neutral",
  online: "success",
  offline: "danger",
  unconfigured: "danger",
};

const LABEL: Record<Status, string> = {
  checking: "Checking backend...",
  online: "Backend online",
  offline: "Backend unreachable",
  unconfigured: "Backend API URL not configured",
};

export default function BackendStatus() {
  // Distinct from "offline" - this means the frontend build itself never
  // got a NEXT_PUBLIC_API_BASE_URL, so it's silently pointed at the
  // localhost fallback (see lib/config.ts) rather than a real outage.
  const [status, setStatus] = useState<Status>(
    API_BASE_URL_CONFIGURED ? "checking" : "unconfigured",
  );

  useEffect(() => {
    if (!API_BASE_URL_CONFIGURED) return;

    let cancelled = false;

    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!cancelled) setStatus(res.ok ? "online" : "offline");
      })
      .catch(() => {
        if (!cancelled) setStatus("offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm">
      <StatusBadge label={LABEL[status]} tone={TONE[status]} dot />
      {status !== "unconfigured" ? <span className="text-muted">{API_BASE_URL}</span> : null}
    </div>
  );
}
