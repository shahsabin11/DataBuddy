import { ApiHealthBadge } from "@/components/ApiHealthBadge";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium tracking-wide text-accent">
        Multi-university research workspace
      </p>
      <h1 className="mt-3 font-display text-5xl leading-tight tracking-tight text-ink md:text-6xl">
        DataBuddy
      </h1>
      <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink/80">
        Upload a spreadsheet, explore it with charts, then run one comparison or
        regression. The agent recommends. You decide.
      </p>
      <div className="mt-10 flex flex-wrap items-center gap-4">
        <a
          href="/login"
          className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90"
        >
          Sign in
        </a>
        <ApiHealthBadge />
      </div>
      <p className="mt-16 text-sm text-ink/55">
        Google / Microsoft sign-in maps your verified email domain to a campus.
        See <code className="rounded bg-ink/5 px-1.5 py-0.5">docs/tenancy.md</code>.
      </p>
    </main>
  );
}
