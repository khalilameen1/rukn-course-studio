"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
  const [status, setStatus] = useState<Status>(
    API_BASE_URL_CONFIGURED ? "checking" : "unconfigured",
  );

  useEffect(() => {
    if (!API_BASE_URL_CONFIGURED) return;

    let cancelled = false;

    api
      .health()
      .then(() => {
        if (!cancelled) setStatus("online");
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
