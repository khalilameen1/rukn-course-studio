# Rukn Course Studio

Internal tool that generates full DOCX practical-skill courses for Rukn from a
course brief, admin-managed fixed rules, and optional sources / manual course
map.

**Current state (MVP):** frontend and backend run locally. A user can create a
course, upload sources, run generation, and download a final DOCX. Generation
uses **`FakeProvider` by default** (deterministic placeholder content, no API
calls). The full internal 8-stage pipeline, validators, source extraction, and
DOCX export are implemented. Real AI (`AnthropicProvider`) exists in code but
is **not wired to the API** unless you pass it explicitly in tests or future
integration work.

See `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/BUILD_PLAN.md` for the
full product spec and what remains (auth, background jobs, migrations, Phase 7
hardening).

## Repository Structure

```
rukn-course-studio/
  frontend/        Next.js (TypeScript, App Router)
  backend/         FastAPI (SQLite, SQLModel, Pydantic)
  storage/
    uploads/       Raw uploaded source files
    extracted/     Normalized/extracted text from sources
    outputs/       Generated DOCX files
    templates/     DOCX formatting templates
  docs/            PRD, architecture, and build plan docs
```

## Prerequisites

- **Node.js** 20+ and npm (frontend)
- **Python** 3.12+ (backend)

Check what you have installed:

```powershell
node --version
npm --version
python --version
```

If any are missing, install them (Windows, via winget):

```powershell
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Python.Python.3.12
```

Then close and reopen your terminal so `PATH` picks up the new installs.

## Backend Setup (FastAPI)

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.reset_local_db --seed
uvicorn app.main:app --reload --port 8000
```

macOS/Linux equivalent:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.reset_local_db --seed
uvicorn app.main:app --reload --port 8000
```

Verify it's running:

```powershell
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "environment": "development"}
```

Interactive API docs: `http://localhost:8000/docs`

On first run, the backend creates `backend/rukn_course_studio.db` and ensures
`storage/` subdirectories exist. **If you already have an older dev database**
and see errors about missing columns (e.g. after pulling schema changes), reset
it — see [Reset local database](#reset-local-database) below.

Seed admin knowledge separately (idempotent — skips keys that already exist):

```powershell
python -m app.seed_admin_knowledge
```

## Frontend Setup (Next.js)

From the repository root, in a **separate terminal** (keep the backend
running in the first one):

```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

macOS/Linux equivalent:

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`. The home page shows whether the backend is
reachable via `/health` — start the backend first if you see "unreachable".

## Running Both Together

1. Terminal 1: `cd backend && .\.venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000`
2. Terminal 2: `cd frontend && npm run dev`
3. Visit `http://localhost:3000`

## Current Pages

- `/` — Home, backend connectivity status, links to admin and courses
- `/admin` — Admin Knowledge Center (CRUD + activate fixed Rukn rules)
- `/courses` — List courses
- `/courses/new` — Create course brief
- `/courses/[id]` — Tabs: Brief, Sources, Generate, Versions, Report (Report tab
  only when `explanation_level` is `full_report`)

Generation shows **high-level progress only** (no reel-by-reel output). After a
successful run, download the latest DOCX from the Generate or Versions tab.

## Reset local database

`create_all` creates missing tables but does **not** add new columns to existing
SQLite files. If generation fails with a schema/column error on an old dev DB,
reset it (local SQLite only; refuses `ENVIRONMENT=production`):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.reset_local_db --seed
```

Without re-seeding admin knowledge:

```powershell
python -m app.reset_local_db
```

**Warning:** this deletes all local courses, sources, jobs, and versions in
that database file. Uploaded files under `storage/` are not deleted. **Stop
`uvicorn` first** if the database file is in use (Windows will block deletion
otherwise).

## Tests

From `backend/` with the venv activated:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

End-to-end fake generation scenario (no API key, no network):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scenario_meta_ads_no_sources.py -q
```

## Environment Variables

| File | Variable | Purpose |
|---|---|---|
| `backend/.env` | `DATABASE_URL` | SQLite connection string |
| `backend/.env` | `ENVIRONMENT` | `development` / `production` |
| `backend/.env` | `ANTHROPIC_API_KEY` | Optional; only for `AnthropicProvider` in tests/manual use |
| `backend/.env` | `AI_MODEL_NAME` | Model name for `AnthropicProvider` |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL` | Backend base URL (default `http://localhost:8000`) |

`.env` / `.env.local` are git-ignored; copy from `.env.example` /
`.env.local.example`.

## Troubleshooting

- **"Backend unreachable" on the home page:** confirm `uvicorn` is running on
  port 8000 and `frontend/.env.local` points at the right URL.
- **Port already in use:** stop whatever else is using port 3000/8000, or use
  `--port 8001` / `npm run dev -- -p 3001` and update `NEXT_PUBLIC_API_URL`.
- **CORS errors:** backend allows `http://localhost:3000` by default
  (`backend/app/config.py` `cors_origins`).
- **Schema / missing column errors:** run `python -m app.reset_local_db --seed`
  from `backend/` (see above).
- **Frontend stops responding after long dev sessions:** restart `npm run dev`.
