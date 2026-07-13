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
| `backend/.env` | `DATABASE_URL` | SQLite connection string (local dev default) |
| `backend/.env` | `SQLITE_DB_PATH` | Production-only override: absolute path to the SQLite file (e.g. Render's persistent disk). If set, this takes priority over `DATABASE_URL`. Leave unset locally |
| `backend/.env` | `ENVIRONMENT` | `development` / `production` |
| `backend/.env` | `AI_PROVIDER` | `fake` (default, no key needed) or `anthropic` |
| `backend/.env` | `ANTHROPIC_API_KEY` | Only required when `AI_PROVIDER=anthropic` |
| `backend/.env` | `AI_MODEL_NAME` | Model name for `AnthropicProvider`; only required when `AI_PROVIDER=anthropic` |
| `backend/.env` | `AUTH_ENABLED` | Defaults to `true` (see [Authentication](#authentication) below) |
| `backend/.env` | `ADMIN_USERNAME` | The one admin login username |
| `backend/.env` | `ADMIN_PASSWORD` | The one admin login password |
| `backend/.env` | `AUTH_SECRET_KEY` | Signs session tokens; any long random string |
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
  `GET /health` and `POST /auth/login`.
- The frontend stores the token in `localStorage`, attaches it to every
  API call, and redirects to `/login` if it's missing or the backend
  returns `401`. Log out from the top nav.
- To disable auth locally (e.g. quick API testing), set
  `AUTH_ENABLED=false` in `backend/.env`.

## Deploying to Render

`render.yaml` at the repo root is a Render Blueprint that deploys two
services from this monorepo: `rukn-course-studio-backend` (FastAPI) and
`rukn-course-studio-frontend` (Next.js). The backend's SQLite database and
`storage/` files are kept on a persistent disk so they survive redeploys.
Requires a paid Render plan (persistent disks aren't on the free tier).

1. In the Render Dashboard: **New > Blueprint**, point it at this repo/branch.
2. Render reads `render.yaml` and creates both services with the settings below.
3. After the first deploy, set the secret env vars in the Dashboard (never
   commit them) - see the exact lists below.
4. Trigger a manual redeploy on both services after setting those so they
   pick up the new values.
5. Run the admin knowledge seed once (see
   [Seed admin knowledge](#seed-admin-knowledge-production) below).
6. Run the [smoke test](#production-smoke-test) against the deployed backend
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
| Disk | 10 GB, mounted at `/opt/render/project/src/backend/storage` |

Backend environment variables:

```
PYTHON_VERSION=3.12.8
ENVIRONMENT=production
SQLITE_DB_PATH=/opt/render/project/src/backend/storage/rukn_course_studio.db
STORAGE_UPLOADS_DIR=/opt/render/project/src/backend/storage/uploads
STORAGE_EXTRACTED_DIR=/opt/render/project/src/backend/storage/extracted
STORAGE_OUTPUTS_DIR=/opt/render/project/src/backend/storage/outputs
STORAGE_TEMPLATES_DIR=/opt/render/project/src/backend/storage/templates
AI_PROVIDER=fake
ANTHROPIC_API_KEY=            # secret - leave blank while AI_PROVIDER=fake
AI_MODEL_NAME=                # secret - leave blank while AI_PROVIDER=fake
CORS_ORIGINS=["https://<your-frontend-service>.onrender.com"]   # secret - set after frontend URL is known
AUTH_ENABLED=true
ADMIN_USERNAME=<secret, set in Render Dashboard>
ADMIN_PASSWORD=<secret, set in Render Dashboard>
AUTH_SECRET_KEY=<secret, set in Render Dashboard - any long random string>
```

`SQLITE_DB_PATH`, and the four `STORAGE_*_DIR` vars, all point under the one
mounted disk (`/opt/render/project/src/backend/storage`) so the database and
all uploaded/generated files survive redeploys and restarts - everything
else in the service's filesystem is ephemeral. `render.yaml` already sets
the non-secret ones (`PYTHON_VERSION`, `ENVIRONMENT`, `SQLITE_DB_PATH`, the
`STORAGE_*` vars, `AI_PROVIDER`, `AUTH_ENABLED`); only the ones marked
"secret" above need to be set manually in the Dashboard.

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
- **CORS errors:** backend allows `http://localhost:3000` by default
  (`backend/app/config.py` `cors_origins`); on Render, set `CORS_ORIGINS`.
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
- **SQLite data lost after a deploy:** the database file must live under the
  persistent disk mount path, not the ephemeral service filesystem. Confirm
  `SQLITE_DB_PATH` is set to a path under the disk's `mountPath` (see
  [Backend service settings](#backend-service-settings) above) - if it's
  unset, or points somewhere off the disk, every deploy/restart silently
  starts from an empty database.
