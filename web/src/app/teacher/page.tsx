"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { AuthGate } from "@/components/AuthGate";
import {
  createTeacherProject,
  fetchMe,
  fetchTeacherProject,
  fetchTeacherProjects,
  inviteStudentsToProject,
  logout,
  type InviteResult,
  type MeResponse,
  type TeacherProject,
  type TeacherProjectDetail,
} from "@/lib/api";

function TeacherDashboard() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [projects, setProjects] = useState<TeacherProject[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TeacherProjectDetail | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [emails, setEmails] = useState("");
  const [inviteResults, setInviteResults] = useState<InviteResult[] | null>(
    null,
  );
  const [smtpConfigured, setSmtpConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reloadProjects = useCallback(async () => {
    setProjects(await fetchTeacherProjects());
  }, []);

  const reloadDetail = useCallback(async (id: string) => {
    setDetail(await fetchTeacherProject(id));
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        setMe(await fetchMe());
        await reloadProjects();
      } catch {
        setError("Could not load teacher dashboard.");
      }
    })();
  }, [reloadProjects]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    void reloadDetail(selectedId).catch(() =>
      setError("Could not load project."),
    );
  }, [selectedId, reloadDetail]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createTeacherProject({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      setTitle("");
      setDescription("");
      await reloadProjects();
      setSelectedId(created.id);
    } catch {
      setError("Could not create project.");
    } finally {
      setBusy(false);
    }
  }

  async function onInvite(e: FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setInviteResults(null);
    try {
      const result = await inviteStudentsToProject(
        selectedId,
        emails
          .split(/[\s,;]+/)
          .map((s) => s.trim())
          .filter(Boolean),
      );
      setSmtpConfigured(result.smtp_configured);
      setInviteResults(result.invites);
      setEmails("");
      await reloadDetail(selectedId);
      await reloadProjects();
    } catch {
      setError("Could not send invites.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-12">
      <p className="text-sm font-medium tracking-wide text-accent">
        Teacher portal
      </p>
      <h1 className="mt-2 font-display text-4xl tracking-tight text-ink">
        Dashboard
      </h1>
      <p className="mt-4 max-w-xl text-ink/75">
        Create a project, invite students by email. They get a link to sign in
        or create an account and join that project.
      </p>
      {me ? (
        <p className="mt-3 text-sm text-ink/55">Signed in as {me.email}</p>
      ) : null}

      {error ? (
        <p
          className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <section className="mt-10">
        <h2 className="font-display text-2xl text-ink">Create a project</h2>
        <form onSubmit={onCreate} className="mt-4 grid gap-3">
          <label className="text-sm text-ink/80">
            Title
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="e.g. PSY 210 Capstone"
            />
          </label>
          <label className="text-sm text-ink/80">
            Description (optional)
            <textarea
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-fit rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Create project
          </button>
        </form>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl text-ink">Your projects</h2>
        {projects.length === 0 ? (
          <p className="mt-3 text-sm text-ink/55">No projects yet.</p>
        ) : (
          <ul className="mt-4 divide-y divide-ink/10 border border-ink/10">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(p.id)}
                  className={`w-full px-4 py-3 text-left text-sm transition hover:bg-ink/5 ${
                    selectedId === p.id ? "bg-accent/5" : ""
                  }`}
                >
                  <div className="font-semibold text-ink">{p.title}</div>
                  <div className="text-ink/55">
                    {p.member_count} members · {p.pending_invites} pending
                    invites
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {detail ? (
        <section className="mt-12 space-y-8">
          <div>
            <h2 className="font-display text-2xl text-ink">{detail.title}</h2>
            {detail.description ? (
              <p className="mt-2 text-sm text-ink/70">{detail.description}</p>
            ) : null}
          </div>

          <form onSubmit={onInvite} className="space-y-3">
            <h3 className="text-sm font-semibold text-ink">
              Invite students to this project
            </h3>
            <label className="block text-sm text-ink/80">
              Email addresses (comma or line separated)
              <textarea
                className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2 font-mono text-sm"
                rows={4}
                value={emails}
                onChange={(e) => setEmails(e.target.value)}
                required
                placeholder={"student1@school.edu\nstudent2@gmail.com"}
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Send invites
            </button>
            <p className="text-xs text-ink/50">
              {smtpConfigured
                ? "Invites are emailed via SMTP."
                : "SMTP is not configured — invites are saved locally and you can copy the link below. Set SMTP_* in .env to send real email."}
            </p>
          </form>

          {inviteResults ? (
            <div className="rounded-md border border-ink/10 bg-white/70 px-4 py-3 text-sm">
              <p className="font-medium text-ink">Invite results</p>
              <ul className="mt-2 space-y-2">
                {inviteResults.map((r) => (
                  <li key={r.email} className="text-ink/75">
                    <span className="font-medium">{r.email}</span> — {r.status}
                    {r.email_delivery ? ` · email ${r.email_delivery}` : ""}
                    {r.invite_url ? (
                      <div className="mt-1 break-all font-mono text-xs text-accent">
                        {r.invite_url}
                      </div>
                    ) : null}
                    {r.error ? (
                      <div className="text-red-700">{r.error}</div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="text-sm font-semibold text-ink">Members</h3>
            <ul className="mt-2 space-y-1 text-sm text-ink/70">
              {detail.members.map((m) => (
                <li key={m.user_id}>
                  {m.email}
                  {m.source === "owner" ? " (you)" : ""}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-ink">Invites</h3>
            {detail.invites.length === 0 ? (
              <p className="mt-2 text-sm text-ink/55">None yet.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-sm">
                {detail.invites.map((i) => (
                  <li key={i.id} className="text-ink/70">
                    {i.email} · {i.status}
                    {i.status === "pending" ? (
                      <div className="break-all font-mono text-xs text-accent">
                        {i.invite_url}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      <div className="mt-12 flex flex-wrap gap-4 text-sm">
        <button
          type="button"
          className="text-ink/55 underline"
          onClick={() =>
            void logout().then(() => {
              window.location.href = "/login";
            })
          }
        >
          Sign out
        </button>
      </div>
    </main>
  );
}

export default function TeacherPage() {
  return (
    <AuthGate>
      <TeacherDashboard />
    </AuthGate>
  );
}
