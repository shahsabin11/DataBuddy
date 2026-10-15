"use client";

import { useEffect, useState, type ReactNode } from "react";

import { fetchMe, type MeResponse } from "@/lib/api";

export function AuthGate({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null | undefined>(undefined);

  useEffect(() => {
    void fetchMe()
      .then((session) => {
        if (!session) {
          window.location.href = "/login";
          return;
        }
        if (
          session.role === "pending" ||
          session.status === "pending" ||
          session.status === "institution_inactive"
        ) {
          const q =
            session.status === "institution_inactive" ? "?reason=inactive" : "";
          window.location.href = `/pending${q}`;
          return;
        }
        setMe(session);
      })
      .catch(() => {
        window.location.href = "/login";
      });
  }, []);

  if (me === undefined) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-ink/55">
        Checking session…
      </main>
    );
  }

  return <>{children}</>;
}
