# DataBuddy

Multi-university web app with an AI analysis partner for research students.
Upload a CSV/XLSX, explore with charts, then run one group comparison or regression
and produce a report. The agent recommends; the student decides.

Design notes live in [`docs/`](docs/). Start with [`docs/decisions.md`](docs/decisions.md).

## Stack

| Layer | Choice |
| --- | --- |
| Web | Next.js (App Router) + TypeScript + Tailwind |
| API | FastAPI (Python 3.11) + SQLAlchemy + Alembic |
| Agent | LangGraph + Claude API (`api/agent`) |
| Sandbox | E2B (`sandbox/`) |
| Data | Postgres + MinIO locally (R2/S3 in production) |
| Deploy | Docker Compose on a small VM |

## Run locally in 5 commands

Prerequisites: Docker Desktop (or Docker Engine + Compose), and a copy of this repo.

```bash
cp .env.example .env
docker compose up --build
# open http://localhost:3000  (web)
# open http://localhost:8000/api/health  (api)
# open http://localhost:9001  (MinIO console; minioadmin / minioadmin)
docker compose down
```

That is the full loop. Fill OAuth, `ANTHROPIC_API_KEY`, and `E2B_API_KEY` in `.env`
when you start auth and agent work. Local health checks and the scaffold UI do not
need those keys.

## Repository layout

```text
web/       Next.js chat workspace
api/       FastAPI app, Alembic, LangGraph agent
sandbox/   E2B template + helper library preloaded into the image
docs/      Product and security decisions
```

## Develop without Docker (optional)

**API**

```bash
cd api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
# start Postgres + MinIO via: docker compose up postgres minio minio-init -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Web**

```bash
cd web
npm ci
npm run dev
```

## Database (tenancy schema)

```bash
# once: create local roles + database (Homebrew Postgres)
psql -h 127.0.0.1 -d postgres -f api/scripts/bootstrap_local_db.sql

cd api
source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://databuddy:databuddy@127.0.0.1:5432/databuddy
export DATABASE_APP_URL=postgresql+psycopg://databuddy_app:databuddy_app@127.0.0.1:5432/databuddy
export DATABASE_ADMIN_URL=postgresql+psycopg://databuddy_admin:databuddy_admin@127.0.0.1:5432/databuddy
alembic upgrade head
python -m scripts.seed   # Northfield + Cedar, 3 users each
```

RLS policy cheat sheet: [`docs/rls-policies.md`](docs/rls-policies.md).

## Tests and lint

```bash
# API (includes multi-tenancy invariant suite)
cd api && ruff check app tests scripts && pytest -q

# Web
cd web && npm run lint && npm run typecheck && npm test
```

CI runs the same checks on every push with a Postgres service (see `.github/workflows/ci.yml`).

## E2B sandbox template

See [`sandbox/README.md`](sandbox/README.md). After you build the template once,
set `E2B_TEMPLATE_ID` in `.env`.

## Docs

| File | What it decides |
| --- | --- |
| `docs/decisions.md` | Plain-language product summary |
| `docs/architecture.md` | Stack, request flow, budget |
| `docs/analytics-spec.md` | Methods, charts, cleaning, out of scope |
| `docs/collaboration-model.md` | Who decides what, and when the student must approve |
| `docs/threat-model.md` | Sandbox autonomy and isolation |
| `docs/tenancy.md` | Multi-university model and invariants |
