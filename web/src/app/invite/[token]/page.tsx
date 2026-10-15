"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchPublicInvite, type PublicInvite } from "@/lib/api";

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    void fetchPublicInvite(token)
      .then(setInvite)
      .catch(() => setError("This invite link is invalid or has expired."));
  }, [token]);

  if (error) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
        <h1 className="font-display text-3xl text-ink">Invite not found</h1>
        <p className="mt-4 text-ink/70">{error}</p>
        <a href="/login" className="mt-8 text-accent underline">
          Go to sign in
        </a>
      </main>
    );
  }

  if (!invite) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-ink/55">
        Loading invite…
      </main>
    );
  }

  const already = invite.status === "accepted";

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium tracking-wide text-accent">
        Project invite
      </p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-ink">
        {invite.project_title}
      </h1>
      <p className="mt-4 text-ink/75">
        {invite.teacher_name} invited <strong>{invite.email}</strong> to join
        this project on DataBuddy.
      </p>
      {already ? (
        <p className="mt-6 text-sm text-accent">
          This invite was already accepted. Sign in as a student to open your
          workspace.
        </p>
      ) : (
        <p className="mt-6 text-sm text-ink/60">
          Use the same email address ({invite.email}) when you sign in.
        </p>
      )}
      <div className="mt-10 flex flex-col gap-3">
        <a
          href={`/api/auth/google/start?portal=student&invite=${encodeURIComponent(token)}`}
          className="rounded-md bg-accent px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-accent/90"
        >
          Continue with Google
        </a>
        <a
          href={`/api/auth/microsoft/start?portal=student&invite=${encodeURIComponent(token)}`}
          className="rounded-md border border-ink/15 bg-white px-5 py-3 text-center text-sm font-semibold text-ink transition hover:bg-ink/5"
        >
          Continue with Microsoft
        </a>
      </div>
    </main>
  );
}
