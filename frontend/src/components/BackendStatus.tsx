"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";

type Status = "checking" | "online" | "offline";

export default function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
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

  const dotColor =
    status === "online"
      ? "bg-green-500"
      : status === "offline"
        ? "bg-red-500"
        : "bg-yellow-500";

  const label =
    status === "online"
      ? "Backend online"
      : status === "offline"
        ? "Backend unreachable"
        : "Checking backend...";

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      <span>{label}</span>
      <span className="text-zinc-400">({API_BASE_URL})</span>
    </div>
  );
}
