"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

const ERRORS: Record<string, string> = {
  email_unverified:
    "Your email is not verified with the provider. Verify it, then try again.",
  email_in_use: "This email is already linked to another sign-in method.",
  invalid_state: "Sign-in expired. Start again.",
  auth_failed: "Sign-in failed. Try again.",
  access_denied: "Sign-in was cancelled.",
  jwks_fetch_failed: "Could not verify sign-in with the provider. Try again.",
  invalid_id_token: "Could not verify sign-in with the provider. Try again.",
};

type Portal = "student" | "teacher";

function LoginBody() {
  const params = useSearchParams();
  const error = params.get("error");
  const message = error ? (ERRORS[error] ?? `Sign-in error: ${error}`) : null;
  const [portal, setPortal] = useState<Portal | null>(null);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium tracking-wide text-accent">Sign in</p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-ink">
        DataBuddy
      </h1>
      <p className="mt-4 text-ink/75">
        Choose how you want to enter, then sign in with your university Google
        or Microsoft account.
      </p>
      {message ? (
        <p
          className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {message}
        </p>
      ) : null}

      {portal === null ? (
        <div className="mt-10 grid gap-3">
          <button
            type="button"
            onClick={() => setPortal("student")}
            className="rounded-md bg-accent px-5 py-4 text-left transition hover:bg-accent/90"
          >
            <span className="block text-sm font-semibold text-white">
              I&apos;m a student
            </span>
            <span className="mt-1 block text-xs text-white/80">
              Upload data, chat with the analysis partner, and build a report.
            </span>
          </button>
          <button
            type="button"
            onClick={() => setPortal("teacher")}
            className="rounded-md border border-ink/15 bg-white px-5 py-4 text-left transition hover:bg-ink/5"
          >
            <span className="block text-sm font-semibold text-ink">
              I&apos;m a teacher
            </span>
            <span className="mt-1 block text-xs text-ink/60">
              Run your class — no campus approval wait. Student tools come next.
            </span>
          </button>
        </div>
      ) : (
        <div className="mt-10">
          <button
            type="button"
            onClick={() => setPortal(null)}
            className="text-sm text-ink/55 underline"
          >
            ← Back to student / teacher
          </button>
          <p className="mt-4 text-sm font-medium text-ink">
            Continuing as{" "}
            <span className="text-accent">
              {portal === "teacher" ? "teacher" : "student"}
            </span>
          </p>
          <div className="mt-4 flex flex-col gap-3">
            <a
              href={`/api/auth/google/start?portal=${portal}`}
              className="rounded-md bg-accent px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-accent/90"
            >
              Continue with Google
            </a>
            <a
              href={`/api/auth/microsoft/start?portal=${portal}`}
              className="rounded-md border border-ink/15 bg-white px-5 py-3 text-center text-sm font-semibold text-ink transition hover:bg-ink/5"
            >
              Continue with Microsoft
            </a>
          </div>
        </div>
      )}

      <p className="mt-8 text-sm text-ink/55">
        Personal Gmail or Outlook addresses cannot join a campus automatically.
        You can still sign in and request access.
      </p>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="p-8 text-ink/60">Loading…</main>}>
      <LoginBody />
    </Suspense>
  );
}
