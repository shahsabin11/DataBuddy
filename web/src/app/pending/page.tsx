"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { fetchMe, logout, submitAccessRequest, type MeResponse } from "@/lib/api";

function PendingBody() {
  const params = useSearchParams();
  const reason = params.get("reason");
  const [me, setMe] = useState<MeResponse | null>(null);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchMe().then(setMe).catch(() => setMe(null));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await submitAccessRequest(message.trim());
      setSent(true);
    } catch {
      setError("Could not save your request. Try again.");
    }
  }

  const inactive = reason === "inactive" || me?.status === "institution_inactive";

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
      <h1 className="font-display text-3xl tracking-tight text-ink">
        {inactive
          ? "Your institution is inactive"
          : "Your institution isn't on DataBuddy yet"}
      </h1>
      <p className="mt-4 text-ink/75">
        {inactive
          ? "Contact a platform admin. You are signed in, but campus access is paused."
          : "Request access and a platform admin will attach you to a campus when one is ready."}
      </p>
      {me ? (
        <p className="mt-3 text-sm text-ink/55">Signed in as {me.email}</p>
      ) : null}

      {!inactive ? (
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block text-sm text-ink/80">
            Optional note for admins
            <textarea
              className="mt-1 w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm"
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g. I'm a student at …"
            />
          </label>
          {error ? (
            <p className="text-sm text-red-700" role="alert">
              {error}
            </p>
          ) : null}
          {sent ? (
            <p className="text-sm text-accent">Request saved. We'll be in touch.</p>
          ) : (
            <button
              type="submit"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white"
            >
              Request access
            </button>
          )}
        </form>
      ) : null}

      <button
        type="button"
        className="mt-10 text-left text-sm text-ink/60 underline"
        onClick={() => void logout().then(() => (window.location.href = "/login"))}
      >
        Sign out
      </button>
    </main>
  );
}

export default function PendingPage() {
  return (
    <Suspense fallback={<main className="p-8 text-ink/60">Loading…</main>}>
      <PendingBody />
    </Suspense>
  );
}
