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
| `backend/.env` | `DATABASE_URL` | Highest-priority DB connection string. Leave **unset locally** (defaults to a local SQLite file). In production, set to a Postgres URL (e.g. Render Postgres' "Internal Database URL") - see [Deploying to Render](#deploying-to-render) |
| `backend/.env` | `SQLITE_DB_PATH` | SQLite-only fallback, used only when `DATABASE_URL` is unset: absolute path to the SQLite file (e.g. Render's persistent disk). Leave unset locally |
| `backend/.env` | `ENVIRONMENT` | `development` / `production` |
| `backend/.env` | `AI_PROVIDER` | `fake` (default, no key needed) or `anthropic` |
| `backend/.env` | `ANTHROPIC_API_KEY` | Only required when `AI_PROVIDER=anthropic` |
| `backend/.env` | `AI_MODEL_NAME` | Model name for `AnthropicProvider`; only required when `AI_PROVIDER=anthropic` |
| `backend/.env` | `AUTH_ENABLED` | Defaults to `true` (see [Authentication](#authentication) below) |
| `backend/.env` | `ADMIN_USERNAME` | The one admin login username |
| `backend/.env` | `ADMIN_PASSWORD` | The one admin login password |
| `backend/.env` | `AUTH_SECRET_KEY` | Signs session tokens; any long random string |
| `backend/.env` | `STORAGE_DIR` | Base directory for uploaded/extracted/generated files. Leave unset locally (defaults to `storage/` at the repo root). In production, point at the persistent disk mount - independent of where the database lives |
| `backend/.env` | `FRONTEND_ORIGIN` | Optional: allow exactly one extra CORS origin (the deployed frontend's URL) without hand-writing a `CORS_ORIGINS` JSON array. Leave unset locally |
| `frontend/.env.local` | `NEXT_PUBLIC_API_BASE_URL` | Backend base URL, no trailing slash, e.g. `http://localhost:8000` locally or the backend's Render URL in production. Inlined at **build time** - changing it always requires a rebuild, not just a restart |

`.env` / `.env.local` are git-ignored; copy from `.env.example` /
`.env.local.example`.

## Authentication

Single-admin-user login for this internal tool - no registration, roles,
or OAuth (see `backend/app/auth/`). `AUTH_ENABLED` defaults to `true`, so
set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `AUTH_SECRET_KEY` in
`backend/.env` or every login/protected request fails with a clear
401/503 instead of silently allowing access.

- `POST /auth/login` - checks the username/password against
  `ADMIN_USERNAME`/`ADMIN_PASSWORD` and returns a signed token (valid 7
  days).
- Every other route requires `Authorization: Bearer <token>` **except**
  `GET /health`, `POST /auth/login`, and `GET /auth/diagnostics` (see
  below).
- The frontend stores the token in `localStorage`, attaches it to every
  API call, and redirects to `/login` if it's missing or the backend
  returns `401`. Log out from the top nav.
- To disable auth locally (e.g. quick API testing), set
  `AUTH_ENABLED=false` in `backend/.env`.

### Diagnosing a broken login (`GET /auth/diagnostics`)

`GET /auth/diagnostics` is a public, secret-free status endpoint (see
`backend/app/auth/diagnostics.py`) built specifically so a broken deployment
can be diagnosed without SSH/log access. It never returns
`ADMIN_PASSWORD`, `AUTH_SECRET_KEY`, `DATABASE_URL`, or any other
credential - only booleans/labels:

```json
{
  "auth_enabled": true,
  "admin_username_configured": true,
  "admin_password_configured": true,
  "auth_secret_key_configured": true,
  "frontend_origin_configured": true,
  "frontend_origin_value": "https://rukn-frontend.onrender.com",
  "cors_origins": ["http://localhost:3000", "http://127.0.0.1:3000", "https://rukn-frontend.onrender.com"],
  "database_backend": "postgres",
  "storage_dir_configured": true,
  "storage_dir_exists": true,
  "storage_dir_writable": true
}
```

The `/login` page also renders a small **diagnostics block** under the
form (temporary, safe to leave in place) showing the resolved API base URL
and the live status of `/health` and `/auth/diagnostics` - use it as the
first thing to check when login doesn't work. If `cors_origins` doesn't
include the frontend's actual URL, that's almost always the cause - see
[CORS errors](#troubleshooting) below.

## Deploying to Render

`render.yaml` at the repo root is a Render Blueprint that deploys two
services from this monorepo: `rukn-course-studio-backend` (FastAPI) and
`rukn-course-studio-frontend` (Next.js). Uploaded/extracted/generated files
under `storage/` are always kept on a persistent disk so they survive
redeploys, **regardless of which database option below you pick** - see
[Storage vs. database](#storage-vs-database) below. Requires a paid Render
plan on the backend (persistent disks aren't on the free tier).

There are two supported database options:

- **A. Recommended - Postgres + Disk.** Set `DATABASE_URL` to a dedicated
  Postgres database's connection string. Real production-grade DB, survives
  redeploys/restarts by nature (Render manages Postgres storage itself).
- **B. Temporary/legacy - SQLite + Disk.** Leave `DATABASE_URL` unset and set
  `SQLITE_DB_PATH` instead. Simpler (no separate DB resource to create), but
  a single SQLite file is not a real production database - prefer Option A
  once you have more than one thing depending on this data.

`DATABASE_URL` always takes priority over `SQLITE_DB_PATH` if both happen to
be set (see `backend/app/config.py` `_resolve_database_url`) - set exactly
one of them.

1. **If using Option A (recommended):** In the Render Dashboard, **New >
   PostgreSQL**, create a **dedicated database for this app** - do not reuse
   or share a database from another project/workspace. Once it's
   provisioned, copy its **Internal Database URL** (not the external one -
   the backend and the database run in the same Render private network).
2. In the Render Dashboard: **New > Blueprint**, point it at this repo/branch.
3. Render reads `render.yaml` and creates both services with the settings below.
4. After the first deploy, set the secret env vars in the Dashboard (never
   commit them) - see the exact lists below. For Option A, this includes
   pasting the Postgres Internal Database URL from step 1 into `DATABASE_URL`.
5. Trigger a manual redeploy on both services after setting those so they
   pick up the new values.
6. Run the admin knowledge seed once (see
   [Seed admin knowledge](#seed-admin-knowledge-production) below).
7. Run the [smoke test](#production-smoke-test) against the deployed backend
   URL to confirm login and the auth flow actually work.

### Backend service settings

| Setting | Value |
|---|---|
| Service type | Web Service |
| Runtime | Python |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Standard (persistent disks require a paid plan) |
| Health Check Path | `/health` |
| Disk | 10 GB, mounted at `/opt/render/project/src/backend/storage` - see [Storage vs. database](#storage-vs-database) |

Backend environment variables - **Option A (recommended: Postgres + Disk)**:

```
PYTHON_VERSION=3.12.8
ENVIRONMENT=production
AI_PROVIDER=fake
AUTH_ENABLED=true
ADMIN_USERNAME=<secret, set in Render Dashboard>
ADMIN_PASSWORD=<secret, set in Render Dashboard>
AUTH_SECRET_KEY=<secret, set in Render Dashboard - any long random string>
DATABASE_URL=<secret, set in Render Dashboard - the dedicated Postgres database's Internal Database URL>
STORAGE_DIR=/opt/render/project/src/backend/storage
FRONTEND_ORIGIN=<secret, set in Render Dashboard - the deployed frontend's URL, once known>
ANTHROPIC_API_KEY=            # secret - leave blank while AI_PROVIDER=fake
AI_MODEL_NAME=                # secret - leave blank while AI_PROVIDER=fake
```

Backend environment variables - **Option B (temporary/legacy: SQLite + Disk)**
- same as above, except omit `DATABASE_URL` and add instead:

```
SQLITE_DB_PATH=/opt/render/project/src/backend/storage/rukn_course_studio.db
```

`render.yaml` already sets the non-secret ones (`PYTHON_VERSION`,
`ENVIRONMENT`, `STORAGE_DIR`, `AI_PROVIDER`, `AUTH_ENABLED`); the vars marked
"secret" above (including `DATABASE_URL`) need to be set manually in the
Dashboard - never commit real credentials into `render.yaml` or `.env`
files. `CORS_ORIGINS` (a JSON array string) still works as an alternative to
`FRONTEND_ORIGIN` if more than one frontend origin is ever needed - see
`backend/app/config.py`.

### Frontend service settings

| Setting | Value |
|---|---|
| Service type | Web Service (this app runs `next build` / `next start`, not a static export, so it needs a real Node server - a Static Site would not work) |
| Runtime | Node |
| Root Directory | `frontend` |
| Build Command | `npm install && npm run build` |
| Start Command | `npm start` |

Frontend environment variables:

```
NEXT_PUBLIC_API_BASE_URL=https://<your-backend-service>.onrender.com
```

No trailing slash, and do **not** include `/health` or any path - just the
backend service's root URL. This is read at **build time** (Next.js inlines
`NEXT_PUBLIC_*` vars into the client bundle), so any change requires
**Manual Deploy > Deploy** (a rebuild), not just a restart.

### Storage vs. database

The database (Postgres or SQLite) and the `storage/` files (uploaded
sources, extracted text, generated DOCX outputs) are two independent
concerns - switching `DATABASE_URL` between Postgres and SQLite never
changes how files are stored. **The persistent disk is required either
way**: uploaded/generated files are plain files on disk, not database rows,
and this app deliberately has no cloud object storage (S3, etc. - see
`.cursor/rules/v1-architecture-constraints.mdc`), so without the disk every
file would be lost on every redeploy/restart regardless of which database
you use.

### Database tables (`create_all`, no migration tool)

Tables are created via `SQLModel.metadata.create_all(engine)` on every
backend startup (`backend/app/db.py` `init_db`, called from `main.py`'s
lifespan) - the same for SQLite and Postgres, since it's plain SQLAlchemy
DDL, not SQLite-specific. There is no separate migration tool (e.g. Alembic)
in this MVP.

- **First deploy against a brand-new database:** no manual step needed -
  `create_all` creates every table automatically the first time the backend
  starts.
- **Later, if a model gains a new column:** `create_all` only creates
  *missing tables*, it never alters existing ones (same limitation
  documented for local SQLite above). Against production Postgres, run the
  equivalent `ALTER TABLE ... ADD COLUMN ...` manually (e.g. via `psql
  "$DATABASE_URL"` from a Render Shell session, or any Postgres client)
  before/after deploying the code that expects the new column. This MVP
  intentionally does not introduce a full migration system (e.g. Alembic)
  until the schema needs changes complex enough to require one - see
  `docs/BUILD_PLAN.md`.

### Seed admin knowledge (production)

`python -m app.seed_admin_knowledge` (see [above](#backend-setup-fastapi))
is idempotent - it skips any `key` that already has a row, so it's always
safe to re-run, but it is **not** wired into the build/start command, so it
won't run automatically on deploy. Run it once after the first deploy via a
Render Shell session on the backend service:

```bash
cd backend  # if the shell doesn't already start there
python -m app.seed_admin_knowledge
```

### Production smoke test

`backend/scripts/smoke_test.py` checks `/health`, login, and a protected
route against a live deployment without creating or modifying any data:

```powershell
python backend/scripts/smoke_test.py --base-url https://<your-backend-service>.onrender.com --username admin --password '...'
```

Prefer environment variables over `--password` on a shared machine (avoids
the password landing in shell history):

```powershell
$env:SMOKE_BASE_URL = "https://<your-backend-service>.onrender.com"
$env:SMOKE_ADMIN_USERNAME = "admin"
$env:SMOKE_ADMIN_PASSWORD = "..."
python backend/scripts/smoke_test.py
```

For a full generation smoke check (fake provider, no network/API key), run
the existing end-to-end test scenario instead - see [Tests](#tests) above.

### Manual frontend auth checklist

No frontend test framework exists in this repo (no jest/vitest); check the
login flow manually after deploying:

1. Open `/login` on the deployed frontend - confirm it renders (not a blank
   page or a build error).
2. Submit the wrong password - confirm a clear "Invalid username or
   password" message appears (not a stack trace or blank screen).
3. Submit the correct credentials - confirm you're redirected to `/` and the
   page loads course data (not stuck on a spinner or redirected back to
   `/login`).
4. Open browser devtools > Network, reload, and click into any API request
   (e.g. `GET /courses`) - confirm the request goes to the backend's Render
   URL (not the frontend's own origin) and carries an `Authorization: Bearer
   ...` header.
5. Click **Logout** - confirm you're redirected to `/login` and reloading
   any protected page also redirects to `/login` (token was actually
   cleared).

## Troubleshooting

- **"Backend unreachable" on the home page:** confirm `uvicorn` is running on
  port 8000 and `frontend/.env.local` points at the right URL.
- **Port already in use:** stop whatever else is using port 3000/8000, or use
  `--port 8001` / `npm run dev -- -p 3001` and update
  `NEXT_PUBLIC_API_BASE_URL`.
- **CORS errors:** backend allows `http://localhost:3000` /
  `http://127.0.0.1:3000` by default (`backend/app/config.py`
  `cors_origins`); on Render, set `FRONTEND_ORIGIN` (or `CORS_ORIGINS` for
  more than one origin) to the deployed frontend's exact URL. Confirm via
  `GET /auth/diagnostics` (see [Diagnosing a broken
  login](#diagnosing-a-broken-login-get-authdiagnostics) above) - if the
  frontend's URL isn't in the returned `cors_origins`, that's the cause.
  The browser reports this as a generic network error (`"Network/CORS/API
  URL error"` on `/login`, or "Failed to fetch" in devtools), never a
  readable CORS message, because a CORS rejection happens in the browser
  itself, before any response reaches the page's JavaScript.
- **Schema / missing column errors:** run `python -m app.reset_local_db --seed`
  from `backend/` (see above).
- **Frontend stops responding after long dev sessions:** restart `npm run dev`.
- **Backend `/health` works but login fails:** `/health` is always public and
  doesn't touch auth at all, so it passing tells you little about auth.
  Check the backend logs for a `503` with `"ADMIN_USERNAME and ADMIN_PASSWORD
  must be set"` (config missing) vs. a `401` with `"Invalid username or
  password"` (wrong credentials) - they're deliberately different status
  codes. Confirm `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`AUTH_SECRET_KEY` are all
  set on the backend service in the Render Dashboard.
- **Frontend opens but login doesn't work at all (button does nothing /
  network error):** open devtools > Network and check what URL the login
  request actually went to. If it's the frontend's own origin instead of the
  backend's, `NEXT_PUBLIC_API_BASE_URL` was unset or wrong **at build time**
  - see the next two items.
- **Seeing `{"detail":"Not authenticated"}` specifically:** this is the
  backend's generic "no/invalid token" response. On `/auth/login` itself
  this most likely means the request path arrived malformed - historically
  caused by `NEXT_PUBLIC_API_BASE_URL` having a trailing slash, producing a
  request to `.../auth/login` with a doubled leading slash (`//auth/login`)
  that failed the public-route check before reaching the login handler. The
  backend now normalizes repeated/trailing slashes
  (`app/auth/middleware.py` `_normalize_path`) and the frontend strips
  trailing slashes from `NEXT_PUBLIC_API_BASE_URL`
  (`frontend/src/lib/config.ts`), so double-check both are actually running
  the current code (redeploy if unsure) before assuming this is still the
  cause.
- **`NEXT_PUBLIC_API_BASE_URL` missing or wrong:** the frontend build fails
  loudly in production if it's unset at all (`frontend/next.config.ts`). If
  the build succeeded but requests still go to the wrong host, the value was
  wrong at build time, not just at runtime - fix it in the Render Dashboard
  and redeploy (see next item).
- **Changed `NEXT_PUBLIC_API_BASE_URL` but nothing changed:** Next.js inlines
  `NEXT_PUBLIC_*` vars into the client bundle at **build time**. Updating the
  value in the Dashboard and restarting the service is not enough - trigger
  **Manual Deploy > Deploy** (a real rebuild) on the frontend service.
- **`AUTH_SECRET_KEY` missing:** every protected request (and login itself,
  since it signs a token on success) returns `503` with `"AUTH_SECRET_KEY is
  not configured on the server."` until it's set on the backend service in
  the Render Dashboard, followed by a redeploy/restart.
- **Uploaded/generated files lost after a deploy (any database option):**
  `STORAGE_DIR` must point under the disk's `mountPath` (see [Backend
  service settings](#backend-service-settings) and [Storage vs.
  database](#storage-vs-database) above) - if it's unset, or points
  somewhere off the disk, every deploy/restart silently starts from an
  empty `storage/` directory, independent of the database.
- **Data lost after a deploy, using Option B (SQLite):** the SQLite file
  itself must also live under the persistent disk mount path. Confirm
  `SQLITE_DB_PATH` is set to a path under the disk's `mountPath` - if it's
  unset, or points somewhere off the disk, every deploy/restart silently
  starts from an empty database. Prefer switching to Option A (Postgres)
  instead of debugging this further - see [Deploying to
  Render](#deploying-to-render).
- **`ModuleNotFoundError` / `NoSuchModuleError` mentioning `psycopg2` or
  `postgres`/`postgresql` on startup, using Option A (Postgres):** confirm
  `requirements.txt` includes `psycopg2-binary` (already the case in this
  repo) and that the build actually ran `pip install -r requirements.txt`
  after pulling this change. A `postgres://`-scheme URL (some providers'
  older convention) is normalized to `postgresql://` automatically
  (`backend/app/config.py` `normalize_database_url`), so this is not a
  cause of this specific error.
