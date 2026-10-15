"use client";

import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "@/lib/api";

export function ApiHealthBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "API unreachable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <span className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs text-red-700">
        API offline
      </span>
    );
  }

  if (!health) {
    return (
      <span className="rounded-full border border-ink/10 bg-white/80 px-3 py-1 text-xs text-ink/50">
        Checking API…
      </span>
    );
  }

  return (
    <span className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
      API {health.status} · v{health.version}
    </span>
  );
}
