"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  approveAccessRequest,
  createInstitution,
  fetchAccessRequests,
  fetchInstitutions,
  fetchMe,
  rejectAccessRequest,
  type AccessRequestRow,
  type InstitutionRow,
  type MeResponse,
} from "@/lib/api";

export default function PlatformAdminPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [institutions, setInstitutions] = useState<InstitutionRow[]>([]);
  const [requests, setRequests] = useState<AccessRequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [domains, setDomains] = useState("");
  const [userBudget, setUserBudget] = useState("50");
  const [instBudget, setInstBudget] = useState("250");

  const reload = useCallback(async () => {
    const [inst, req] = await Promise.all([
      fetchInstitutions(),
      fetchAccessRequests("pending"),
    ]);
    setInstitutions(inst);
    setRequests(req);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const session = await fetchMe();
        setMe(session);
        if (!session || session.role !== "platform_admin") {
          setError("Platform admin session required.");
          return;
        }
        await reload();
      } catch {
        setError("Could not load platform admin data.");
      }
    })();
  }, [reload]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createInstitution({
        name: name.trim(),
        slug: slug.trim().toLowerCase(),
        domains: domains
          .split(/[\s,]+/)
          .map((d) => d.trim().toLowerCase())
          .filter(Boolean),
        user_token_budget_usd: userBudget,
        institution_token_budget_usd: instBudget,
        enforce_institution_budget: false,
        allowed_entra_tenant_ids: [],
      });
      setName("");
      setSlug("");
      setDomains("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  if (error && !me) {
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
    <main className="mx-auto max-w-4xl space-y-12 px-6 py-12">
      <header>
        <p className="text-sm font-medium text-accent">Platform admin</p>
        <h1 className="mt-2 font-display text-3xl text-ink">Institutions</h1>
        <p className="mt-2 text-sm text-ink/65">
          Create campuses, add domains, set per-user token quotas, approve
          pending requests. Institution quota enforcement is optional for later.
        </p>
        {me ? (
          <p className="mt-2 text-xs text-ink/45">{me.email}</p>
        ) : null}
      </header>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      <section>
        <h2 className="font-display text-xl text-ink">Create institution</h2>
        <form onSubmit={onCreate} className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            Name
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>
          <label className="text-sm">
            Slug
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              required
              pattern="[a-z0-9][a-z0-9-]{1,78}[a-z0-9]"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            Domains (comma-separated; exact match, e.g. uni.edu, students.uni.edu)
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={domains}
              onChange={(e) => setDomains(e.target.value)}
              required
            />
          </label>
          <label className="text-sm">
            Per-user token budget (USD)
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={userBudget}
              onChange={(e) => setUserBudget(e.target.value)}
            />
          </label>
          <label className="text-sm">
            Institution budget (USD, optional later)
            <input
              className="mt-1 w-full rounded-md border border-ink/15 px-3 py-2"
              value={instBudget}
              onChange={(e) => setInstBudget(e.target.value)}
            />
          </label>
          <button
            type="submit"
            className="sm:col-span-2 mt-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white"
          >
            Create
          </button>
        </form>
      </section>

      <section>
        <h2 className="font-display text-xl text-ink">Campuses</h2>
        <ul className="mt-4 divide-y divide-ink/10 border border-ink/10">
          {institutions.map((inst) => (
            <li key={inst.id} className="px-4 py-3 text-sm">
              <div className="font-semibold text-ink">
                {inst.name}{" "}
                <span className="font-normal text-ink/50">({inst.slug})</span>
              </div>
              <div className="mt-1 text-ink/65">
                Domains: {inst.domains.join(", ") || "—"}
              </div>
              <div className="text-ink/55">
                User quota ${inst.user_token_budget_usd ?? "—"} · Institution $
                {inst.institution_token_budget_usd ?? "—"}
                {inst.enforce_institution_budget ? " (enforced)" : " (not enforced)"}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="font-display text-xl text-ink">Pending access requests</h2>
        {requests.length === 0 ? (
          <p className="mt-3 text-sm text-ink/55">No pending requests.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {requests.map((req) => (
              <li
                key={req.id}
                className="rounded-md border border-ink/10 bg-white/70 px-4 py-3 text-sm"
              >
                <div className="font-medium">{req.email}</div>
                <div className="text-ink/55">domain: {req.email_domain}</div>
                {req.message ? (
                  <p className="mt-1 text-ink/70">{req.message}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <select
                    id={`inst-${req.id}`}
                    className="rounded-md border border-ink/15 px-2 py-1"
                    defaultValue={institutions[0]?.id ?? ""}
                  >
                    {institutions.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="rounded-md bg-accent px-3 py-1.5 text-white"
                    onClick={() => {
                      const select = document.getElementById(
                        `inst-${req.id}`,
                      ) as HTMLSelectElement | null;
                      if (!select?.value) return;
                      void approveAccessRequest(req.id, select.value)
                        .then(reload)
                        .catch(() => setError("Approve failed"));
                    }}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-ink/20 px-3 py-1.5"
                    onClick={() =>
                      void rejectAccessRequest(req.id)
                        .then(reload)
                        .catch(() => setError("Reject failed"))
                    }
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
