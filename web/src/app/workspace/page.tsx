import { AuthGate } from "@/components/AuthGate";
import { DatasetUpload } from "@/components/DatasetUpload";

export default function WorkspacePage() {
  return (
    <AuthGate>
      <main className="mx-auto grid min-h-screen max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-6">
          <DatasetUpload />
          <section className="rounded-lg border border-ink/10 bg-white/70 p-5 shadow-sm backdrop-blur">
            <h1 className="font-display text-2xl text-ink">Chat</h1>
            <p className="mt-2 text-sm text-ink/70">
              Conversation with the analysis agent will stream here (SSE from
              FastAPI).
            </p>
            <div className="mt-6 rounded-md bg-paper px-3 py-8 text-center text-sm text-ink/50">
              Agent panel placeholder
            </div>
          </section>
        </div>
        <section className="rounded-lg border border-ink/10 bg-white/70 p-5 shadow-sm backdrop-blur">
          <h2 className="font-display text-2xl text-ink">Charts & results</h2>
          <p className="mt-2 text-sm text-ink/70">
            Figures from <code>render_chart</code> and test tables will appear
            here. A chart can be a complete run — no model required.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <div className="rounded-md bg-paper px-3 py-10 text-center text-sm text-ink/50">
              Chart panel
            </div>
            <div className="rounded-md bg-paper px-3 py-10 text-center text-sm text-ink/50">
              Results panel
            </div>
          </div>
        </section>
      </main>
    </AuthGate>
  );
}
