"use client";

import { useEffect, useState } from "react";

import {
  fetchInstitutionUsage,
  fetchMe,
  type InstitutionUsage,
  type MeResponse,
} from "@/lib/api";

export default function InstitutionAdminPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [usage, setUsage] = useState<InstitutionUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const session = await fetchMe();
        setMe(session);
        if (
          !session ||
          (session.role !== "institution_admin" &&
            session.role !== "platform_admin")
        ) {
          setError("Institution admin session required.");
          return;
        }
        setUsage(await fetchInstitutionUsage());
      } catch {
        setError("Could not load institution usage.");
      }
    })();
  }, []);

  if (error && !usage) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-red-700">{error}</p>
        <a href="/login" className="mt-4 inline-block text-accent underline">
          Sign in
        </a>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <p className="text-sm font-medium text-accent">Institution admin</p>
      <h1 className="mt-2 font-display text-3xl text-ink">Usage</h1>
      <p className="mt-2 text-sm text-ink/65">
        Totals for your campus only. Institution comes from the signed session,
        never from the client.
      </p>
      {me ? (
        <p className="mt-2 text-xs text-ink/45">{me.email}</p>
      ) : null}

      {usage ? (
        <div className="mt-10 space-y-8">
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-ink/55">Active members</dt>
              <dd className="mt-1 text-2xl font-semibold">{usage.active_members}</dd>
            </div>
            <div>
              <dt className="text-ink/55">Est. cost (USD)</dt>
              <dd className="mt-1 text-2xl font-semibold">
                {usage.totals.estimated_cost_usd}
              </dd>
            </div>
            <div>
              <dt className="text-ink/55">Input tokens</dt>
              <dd className="mt-1 text-2xl font-semibold">
                {usage.totals.input_tokens.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-ink/55">Output tokens</dt>
              <dd className="mt-1 text-2xl font-semibold">
                {usage.totals.output_tokens.toLocaleString()}
              </dd>
            </div>
          </dl>

          <section>
            <h2 className="font-display text-xl text-ink">By user</h2>
            {usage.by_user.length === 0 ? (
              <p className="mt-3 text-sm text-ink/55">No usage yet.</p>
            ) : (
              <table className="mt-4 w-full text-left text-sm">
                <thead className="border-b border-ink/15 text-ink/55">
                  <tr>
                    <th className="py-2 font-medium">User</th>
                    <th className="py-2 font-medium">Cost</th>
                    <th className="py-2 font-medium">In</th>
                    <th className="py-2 font-medium">Out</th>
                    <th className="py-2 font-medium">Events</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.by_user.map((row) => (
                    <tr key={row.user_id} className="border-b border-ink/5">
                      <td className="py-2 font-mono text-xs">
                        {row.user_id.slice(0, 8)}…
                      </td>
                      <td className="py-2">${row.estimated_cost_usd}</td>
                      <td className="py-2">{row.input_tokens}</td>
                      <td className="py-2">{row.output_tokens}</td>
                      <td className="py-2">{row.events}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      ) : (
        <p className="mt-8 text-sm text-ink/55">Loading…</p>
      )}
    </main>
  );
}
