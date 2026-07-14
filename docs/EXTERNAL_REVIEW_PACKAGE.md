# Rukn Course Studio — External Product / UX / Code Review Package

**Purpose:** Hand this package (plus screenshots) to an external Fable-like AI/product reviewer.

**Scope of review:** The **application** (UI, UX, flows, polish, hidden bugs, production readiness) — **not** the quality of generated course scripts.

**Out of scope for the reviewer:** Do not connect Fable inside the app. Do not add a critic model. Do not change generation/course-content logic as part of this review. Design recommendations welcome; redesign implementation comes after the review.

**App under review date:** 2026-07-14 (local MVP + Render-deployable)

---

## 1. Product summary

### What it is
**Rukn Course Studio** is an internal single-user tool that turns a course brief (+ optional sources + fixed Admin Knowledge rules) into a **teleprompter-ready DOCX** — spoken lecturer script only, ready to record on camera.

### Who uses it
One internal operator (Rukn course creator). Single admin username/password from environment. No multi-user accounts, no registration, no OAuth.

### Main workflow
1. **Login**
2. **Admin Knowledge** — confirm Rukn fixed rules are seeded/active
3. **Create Course** — brief, outcome, preset, optional map
4. **Upload Sources** — typed as scientific / flow / old course / notes / raw
5. **Generate** — runs an internal multi-stage pipeline (hidden from the user)
6. **Download DOCX** — final teleprompter-ready lecturer script

### Final user-facing output
Exactly one deliverable: a **DOCX** structured as:

- Course title  
- `Module N — …`  
- `Lesson N — …`  
- Spoken script paragraphs only  
- Optional project text only if meant to be spoken/shown  

Not a book, handout, branded cover, methodology report, or internal AI notes dump.

### Product promise (must stay visible in the UI)
> Final DOCX is a teleprompter-ready lecturer script — spoken script only.

---

## 2. Current app routes / pages

| Route | Purpose |
|-------|---------|
| `/login` | Single-user login; temporary login diagnostics for misconfigured API/CORS/auth |
| `/` | Home: workflow line + two entry cards (Admin Knowledge, Courses) + backend status |
| `/admin` | Admin Knowledge Center — card grid of fixed Rukn rules (edit/view) |
| `/courses` | Courses list (empty state + New Course) |
| `/courses/new` | Guided create-course form |
| `/courses/[id]` | Course workspace — 3 zones: **Inputs / Generate / Output** + Sources / Versions / Report tabs |
| *(planned / partial)* `/ai-usage` | Backend API exists (`GET /ai-usage/summary`); **no frontend page yet** |

**API-only (not product pages):**
- `GET /health` — liveness
- `GET /auth/diagnostics` — public, secret-free config/status (provider ready flags, CORS, storage, etc.)

**Nav (AppShell):** Home · Admin Knowledge · Courses · Logout  
*(No AI Usage nav link yet.)*

---

## 3. Main user flows

### First login
1. Open frontend URL → redirect to `/login` if unauthenticated  
2. Enter admin username/password  
3. Token stored in `localStorage`; subsequent API calls send `Authorization: Bearer …`  
4. On success → Home  

**Auth notes:** HMAC-signed token; middleware protects routes except health, login, diagnostics.

### Create new course
1. Courses → New Course  
2. Fill: title, audience, outcome, structure mode, generation preset (default Balanced), explanation level (default Final only)  
3. Optional: special notes, manual course map  
4. Submit → course detail workspace  

### Upload source
1. Course workspace → Sources tab  
2. Upload file (docx/pdf/txt/md) + choose **source type** + priority  
3. Or add free-text notes source  
4. Source appears with type badge + extraction status  

**Source types:**
- `scientific_reference` — knowledge only (facts/concepts); not style authority  
- `flow_reference` — speech mechanics / flow profile only; not facts/template  
- `old_course` — prior attempt; reuse selectively  
- `user_notes` — highest priority instructions  
- `raw_material` — mixed/unclear; extract carefully  

### Change source type
In Sources table: compact “change type” select → `PATCH` category → badge updates.

### Delete mistaken source
Delete button → browser confirm → removes DB row + stored files (not the course / not DOCX versions).

### Generate (fake / later Anthropic)
1. Center **Generate** panel → **Generate Final DOCX**  
2. Coarse status + progress steps + % (no reel-by-reel internal feed)  
3. Poll job until `completed` / `failed` / `partial`  
4. On completed → versions refresh; Output shows download  

`AI_PROVIDER=fake` (default) or `anthropic` via env. Fake must remain selectable.

### Download final DOCX
Output panel → Download DOCX (auth-aware fetch, not bare `<a>`).

### Partial generation / download
If run stops mid-way with saved work → status `partial` (or failed with nothing usable).  
Output may show **Partial draft available** + Download Partial DOCX.  
Partial DOCX adds a top note; **final DOCX never includes that note**.

### Resume generation
**Not implemented** (intentionally). Recovery path today = partial download + **Regenerate from Scratch** (new job). Do not review “resume” as if it works.

### Admin Knowledge edit / seed
- Auto-seeded on backend startup (idempotent; does not overwrite user edits)  
- Manual: `python -m app.seed_admin_knowledge`  
- UI: card grid for known keys; edit form for content  
Keys: core rules, practical rules, writing style, forbidden phrases, quality rubric, teleprompter contract, generation presets  

### Provider / usage monitoring
- Course Output panel: live provider label (Fake / Anthropic / Anthropic needs config) via diagnostics  
- Home: BackendStatus (API URL / online / offline)  
- Backend: `/ai-usage/summary`, usage events, budget guard env vars  
- **Gap:** no dedicated in-app AI Usage page yet (API ahead of UI)

---

## 4. Screenshots needed for review

Automated screenshots were not produced for this package. Capture these manually (desktop width ~1280–1440px preferred; also one mobile frame of workspace if possible):

1. `/login` — empty form  
2. `/login` — after failed login (error message) *optional*  
3. `/` Home — backend online  
4. `/admin` — seeded knowledge cards  
5. `/courses` — empty state  
6. `/courses` — with at least one course  
7. `/courses/new` — form (preset + helper text visible)  
8. `/courses/[id]` — workspace empty/minimal sources  
9. `/courses/[id]` — Sources tab with badges + change-type + delete  
10. `/courses/[id]` — Generate panel mid-run or just completed  
11. `/courses/[id]` — Output with DOCX ready + download  
12. `/courses/[id]` — Partial state if you can simulate (stop after failure inject / quota)  
13. Error: Home with backend offline (stop API)  
14. Diagnostics block on login (if `NEXT_PUBLIC_API_BASE_URL` wrong or CORS broken) *optional*  

**Skip if not present:** AI Usage / Operations page (not shipped in UI yet).

---

## 5. Known technical context

| Area | Current stack / behavior |
|------|--------------------------|
| Frontend | Next.js (App Router), TypeScript, React 19, Tailwind CSS v4 |
| Backend | FastAPI, SQLModel/Pydantic, sync generation route (MVP) |
| Database | Local SQLite by default; production `DATABASE_URL` Postgres supported |
| Storage | `STORAGE_DIR` — uploads / extracted / outputs / templates |
| Auth | Single admin env vars; Bearer token in localStorage |
| AI | `AIProvider` abstraction; default `FakeProvider`; `AnthropicProvider` behind `AI_PROVIDER=anthropic` |
| Prompting | Stage prompts + prompt compiler (rules/source selection, authority firewall) |
| Presets | conservative / balanced / creative / fusion / strict_teleprompter → temperature on Anthropic |
| Sources | 5 types; authority hierarchy; flow ≠ scientific |
| Resilience | Incremental job persistence; `partial` status; partial DOCX; 409 if generate while running |
| Resume | **Not** shipped |
| DOCX | Teleprompter contract; RTL/Arabic-friendly formatting helpers |
| Quality (backend) | Output scoring JSON on jobs; forbidden/internal-note checks (observational) |
| Ops (backend) | Run snapshots (hashes), AI usage events, budget warn-only env, diagnostics extensions |
| Deploy | Render Blueprint (`render.yaml`); frontend `NEXT_PUBLIC_API_BASE_URL`; backend auth + AI secrets |
| Constraints (V1) | No LangChain / vector DB / RAG framework / Redis / Docker required for core |

---

## 6. Review checklist (for Fable-like reviewer)

### A. Visual quality
- Does it look like a high-end **internal** SaaS (NotebookLM / Linear / Vercel-dashboard class), not Bootstrap admin or marketing landing?
- Spacing, typography, cards, primary vs secondary buttons, status badges consistent?
- Anything amateur, unfinished, or visually noisy (gradients, clutter, weak brand signal on Home)?

### B. UX clarity
- Is the **next action** obvious on every page?
- Are **Inputs / Work / Output** clear on the course workspace?
- Empty states: useful + one clear CTA?
- Errors: short, actionable, no stack traces?
- Source upload / type / delete obvious?
- Download final DOCX obvious and discoverable?

### C. Product flow
- Can a first-time user understand Login → Knowledge → Course → Sources → Generate → DOCX?
- Does Admin Knowledge feel like a **rules library**, not raw DB rows?
- Does Course Workspace feel like a **production console**?
- Is the teleprompter-ready promise clear and consistent?

### D. Reliability & hidden bugs
- Double-click Generate? (backend 409; does UI handle it well?)
- Source delete failure messaging?
- Backend offline?
- Auth expired / 401 → login?
- AI quota / rate limit / timeout → partial save + clean message?
- Partial generation UX clear vs “failed with nothing”?
- Download with auth / missing file?

### E. Production polish
- Diagnostics: helpful on login, not cluttering the workspace?
- Internal reels/reviews/logs never exposed as product output?
- Secrets impossible to expose (UI, diagnostics, usage APIs)?
- Loading / running indicators clear?
- Safe enough for real internal work with `AI_PROVIDER=fake` today / Anthropic when configured?

---

## 7. Required output format from the reviewer

Use this structure exactly:

1. **Executive summary** (5–10 sentences)  
2. **Top 10 critical issues**  
3. **Quick wins** (≤1 day each)  
4. **Visual polish recommendations**  
5. **UX blockers**  
6. **Hidden bug risks**  
7. **Page-by-page comments** (`/login`, `/`, `/admin`, `/courses`, `/courses/new`, `/courses/[id]`)  
8. **Priority list**  
   - **P0** must fix before real Anthropic / real operator use  
   - **P1** should fix soon  
   - **P2** nice to have  
9. **Implementation notes for Cursor** — concrete file/area suggestions, still app-audit only (no course-content critique)

---

## 8. Known weak spots (pre-flagged for honesty)

Document these so the reviewer doesn’t treat them as discoveries-only:

1. **Resume generation is not implemented** — only partial DOCX + regenerate-from-scratch.  
2. **AI Usage Center API exists without a frontend page/nav** — ops visibility incomplete in-product.  
3. **Frontend `GenerationJob` types may lag backend** extras (`run_snapshot_json`, `output_score_json`, budget warnings) — quality/snapshot UI not fully surfaced.  
4. **Synchronous generation** — long real-Anthropic runs may time out at the edge (proxy/request); persistence prepares for background jobs later.  
5. **README** has historically lagged feature shipping; trust runtime behavior + this package over older top-of-README claims.  
6. **Login page still carries diagnostic tooling** — useful for deployment debugging; may feel unpolished for a “done” product feel.  
7. **FakeProvider scripts** are placeholders — fine for pipeline/UX review; not for judging spoken Arabic quality.  
8. **Source authority / prompt compiler** are backend-heavy; UI only labels types — reviewer should still check whether the UI *explains* the scientific vs flow distinction well enough.  
9. **Authenticated download** was recently fixed (Bearer blob download) — verify that path in review.  
10. **No automated visual regression / Playwright suite** in frontend — review is largely human/AI visual + code reading.

---

## Manual routes to open (smoke path for screenshots)

With frontend + backend running and `AI_PROVIDER=fake`:

1. `/login` → sign in  
2. `/` → confirm Backend online  
3. `/admin` → 7 cards present  
4. `/courses` → list/empty  
5. `/courses/new` → create a tiny course  
6. `/courses/[id]` → upload one source, change type, delete, re-upload  
7. Generate Final DOCX → wait → Download from Output  
8. (Optional) Stop backend → refresh Home / try Generate for offline messaging  
9. (Optional) Wrong `NEXT_PUBLIC_API_BASE_URL` rebuild to see login diagnostics  

---

*End of review package body. See companion prompt in the same folder: `EXTERNAL_REVIEWER_PROMPT.md`.*
