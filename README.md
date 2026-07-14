# ROKN Course Studio

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

To intentionally refresh selected system defaults (forbidden phrases, quality
rubric, high-signal doctrine, teleprompter contract) after a code upgrade —
keeps previous active content as an inactive backup version:

```powershell
python -m app.seed_admin_knowledge --refresh-defaults --confirm
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
- `/courses/[id]` — Sources + Generate + download Teleprompter DOCX

### V1 output lock (Final)

**User-facing output is only the Teleprompter DOCX** (plus progress/status,
and optional partial DOCX if a run stops early).

DOCX contains only: course title, module headings, lesson headings, spoken
transcript. Never: production notes, asset briefs, sources/citations,
reviews, scores, planning labels, Project/bridge blocks.

All map/draft/review/mentor/research/market/evergreen/originality/
recordability/promise gates stay **internal** and rewrite scripts silently.

**Cancelled for V1 (do not implement):** Production Pack, asset planning,
separate JSON user downloads, course update-impact scan product UI.

Generation shows high-level progress only. Download the Teleprompter DOCX
from the Output panel after a successful run.

## Source types

Every uploaded/pasted source has a `source_category` (`app/models/enums.py`
`SourceCategory`) that controls how the generation pipeline treats it -
see `app/generation/prompt_compiler.py` for exactly how each one is
compiled into prompt context:

| Category | Use for | How it's handled |
|---|---|---|
| `scientific_reference` | Factual/technical/educational material to extract, summarize, and rephrase into Rukn's style. | Short source -> full text; long source -> summary, or a few keyword-matched chunks when writing a specific reel. Never copied as long verbatim passages. |
| `flow_reference` | A style/speaking reference - HOW something is said (hook, pacing, transitions, escalation, ending, naturalness), not WHAT is said. | Never summarized or quoted. Instead reduced to a short **heuristic flow profile** (pacing, opening/ending pattern, transition style, escalation, naturalness) - see "Prompt compiler" below. |
| `old_course` | A previous course, to understand its structure/strengths/weaknesses. | Same extract/summarize/chunk-select handling as `scientific_reference`. Reuse what's useful, avoid the weak parts - no automatic "fusion" logic exists yet. |
| `user_notes` | Direct user instructions - highest priority (scope/audience/tone/constraints). | Always passed through in full. Never trimmed by category logic; protected as long as possible even when the overall source budget (below) has to trim something. |
| `raw_material` | Mixed/unclear material that hasn't been classified yet. | Same extract/summarize/chunk-select handling as `scientific_reference`, prefixed with a short "unclassified/mixed material - verify before treating as fact" marker. |

**Why `flow_reference` is analyzed instead of summarized:** a style
reference's *content* is irrelevant (and must never leak into a course as
if it were a fact) - what matters is its *delivery pattern*. Summarizing
it would either produce a meaningless summary or, worse, tempt the
pipeline into treating a catchphrase as real course material.
`scientific_reference` is the opposite: its content *is* the point, so it
gets extracted/summarized/chunk-selected instead of pattern-profiled.

Change a source's category after upload with
`PATCH /courses/{course_id}/sources/{source_id}` (body:
`{"source_category": "..."}`) - this re-derives that source's category-driven
"avoid points" (`app/services/source_analysis.py` `CATEGORY_AVOID_POINTS`)
without re-running extraction/chunking/summarization. Delete a source with
`DELETE /courses/{course_id}/sources/{source_id}` (204 on success, 404 if it
doesn't belong to that course) - removes the DB row, the uploaded file, the
extracted-text copy, and any analysis rows.

### Source Authority

**Sources never define Rukn's language, format, lesson/reel structure, or
style.** That authority comes only from:

- **Rukn Admin Knowledge** - specifically `rukn_writing_style`,
  `rukn_practical_course_rules`, `rukn_teleprompter_docx_contract`,
  `rukn_quality_rubric`, `rukn_high_signal_reel_doctrine`,
  `rukn_creator_critic_loop`, `rukn_student_confusion_layer`, and
  `rukn_master_mentor_engine`
  (`app/models/admin_knowledge_item.py`, loaded per stage by
  `select_rules_for_stage`) - and
- **explicit user instructions** (`user_notes` sources, always passed
  through in full).

Concretely: `scientific_reference` sources provide **knowledge only** (facts
to extract, simplify, and rephrase into Rukn's own voice - never tone,
wording, or structure to imitate). `flow_reference` sources provide **human
delivery mechanics only** (pacing, hooks, escalation, naturalness) - never a
factual source and never a format/reel template. A transcript or document
from a completely different field/domain must never become a course
template just because it was uploaded - it can only ever inform *how a human
naturally talks*, never *what Rukn's course looks like*.

**Authority priority order** (highest to lowest):

1. Explicit user instructions (`user_notes`)
2. Rukn Admin Knowledge (`rukn_writing_style`, `rukn_practical_course_rules`,
   `rukn_teleprompter_docx_contract`, `rukn_quality_rubric`,
   `rukn_high_signal_reel_doctrine`, `rukn_dynamic_teaching_curve`,
   `rukn_creator_persona_engine`)
3. The teleprompter DOCX contract specifically (`rukn_teleprompter_docx_contract`)
4. The course brief / target learner (title, audience, outcome, structure mode)
5. Scientific/factual sources (`scientific_reference`)
6. Flow/style mechanics (`flow_reference`)
7. Old course structure (`old_course`)

`compile_source_context` (`app/generation/prompt_compiler.py`) enforces this
hierarchy on every stage's compiled sources, ordering the returned excerpts
`user_notes` -> `scientific_reference` -> `flow_reference` -> `old_course` ->
`raw_material`, independent of the unrelated high/medium/low `priority`
field (which stays a secondary signal used only for budget trimming).

**Conflict-resolution rules:**

- Admin Knowledge beats source style/tone, always.
- The teleprompter contract beats a source's own formatting, always.
- An explicit user instruction beats default source-handling behavior.
- Scientific facts beat creative/stylistic wording when they conflict.
- `flow_reference` never overrides Rukn's own lesson/reel format/structure -
  it can only ever describe delivery mechanics.

Every compiled `SourceExcerpt` (`app/ai/provider.py`) also carries
`allowed_use` / `disallowed_use` / `style_contamination_warning` - a narrow,
explicit label of exactly what that source's content may and may never be
used for (e.g. `scientific_reference` allows
`extract_factual_knowledge`/`rephrase_into_rukn_style` but disallows
`imitate_source_tone`/`copy_source_structure`; `flow_reference` allows
`identify_pacing`/`identify_escalation_and_tension` but disallows
`copy_catchphrases_or_signature_lines`/`treat_as_reel_template`). See
`ALLOWED_USE_BY_CATEGORY` / `DISALLOWED_USE_BY_CATEGORY` /
`STYLE_CONTAMINATION_WARNING_BY_CATEGORY` in `app/generation/prompt_compiler.py`
for the exact per-category lists.

## High-signal reel doctrine

`rukn_high_signal_reel_doctrine` (Admin Knowledge; auto-seeded when missing)
defines Rukn's writing standard against shallow short-form habits:

- **Viral without bait** — hooks stop because of the idea, not hype
  ("biggest"/"secret no one knows"/forced heat).
- **Standalone + series** — each reel works alone on social; no disguised
  recap of the previous reel inside the app series.
- **Organic loops** — natural cut at an important point, never "in the next
  reel" announcements.
- **Variable length by idea** — short/medium/long as needed; no equal word
  counts, no padding, no cutting until shallow.
- **High-signal only** — save/share-worthy distinction, correction, local
  realistic example, or mental model.
- **Local examples** — Egyptian/Arab learner reality (shops, phones, low
  budgets); not imported luxury/default mega-company contexts.
- **Teacher dignity** — honest value ok; no desperate selling tone.
- **Domain voice** — not one robotic voice for every skill.
- **No template copying** — scientific sources = knowledge only;
  `flow_reference` = `human_flow_profile` only, never a format template.
- **Adversarial self-review** — write path must internally produce Draft A →
  Draft B → Adversarial Critic → **Master Version**; only Master becomes
  `script_text` (see `app/prompts/write_single_reel.md`). Local validators
  (`app/validators/high_signal_checker.py`,
  `app/validators/anti_template_checker.py`) catch obvious failures even
  under `FakeProvider`.

## Dynamic teaching curve

`rukn_dynamic_teaching_curve` (Admin Knowledge) plus
`app/generation/teaching_curves.py` make the course feel like a human teacher,
not a machine on one fixed line:

- **No fixed course-wide depth, voice, reel length, or energy.**
- Before each **module**, plan a compact internal `module_curve` (role, energy
  curve, depth pattern, variation goal, risk).
- Before each **lesson/reel**, plan a compact internal `lesson_curve` (natural
  length/depth, teaching energy, tension, speech density, explanation mode,
  hook strength, ending motion, compression/expansion).
- Curves are **planning decisions** passed compactly into write prompts
  (`WriteSingleReelInput.module_curve` / `lesson_curve`). The idea controls the
  curve; labels never become DOCX headings or script meta.
- Quiet lessons may stay quiet; long connected lessons may stay long; short
  complete lessons may stay short. Forced viral / sales overperformance and
  flat same-length / same-hook modules are flagged by
  `app/validators/teaching_curve_checker.py`.

## Synthetic creator persona

`rukn_creator_persona_engine` (Admin Knowledge) plus
`app/generation/creator_persona.py` give the model a stronger internal state:

- **Synthetic only** — not a real person, clone, or named-creator imitation.
- Before generation, plan a compact `course_creator_persona` (domain identity,
  audience psychology, creator instinct, never-do list, trust/seller avoidances).
- Before each module, `module_persona_adjustment` (shift, audience need, feel).
- Before each lesson, `lesson_persona_state` (real point, heat, viral_intent:
  viral_worthy / quiet_useful / corrective_strong / technical_spine, fake risks).
- Compact profiles go into map/write/review prompts; full Admin Knowledge is
  stable stage context (`prompt_compiler` v1.4). Labels never appear in DOCX.
- Local checks (`app/validators/creator_persona_checker.py`) flag imitation cues,
  fake AI-Egyptian slang, superlative spam, flow-template leaks, and viral heat
  on quiet spine lessons.

## Final generation architecture (locked)

The writing brain is **complete**. Do **not** add more persona layers.
The **Creator Agent does not self-criticize** — separate agents review.

Per lesson/reel:

1. **Creator Agent** writes the full first draft (uninterrupted)
2. **Student Agent** reviews the completed draft (broad learner confusion)
3. **Specialist Critic Agent** reviews the completed draft (accuracy, weakness,
   filler, realism, language, domain)
4. **Master Mentor Agent** reviews draft + review signals (hook, loop, pacing,
   creator instinct, subtle academic gaps)
5. **Creator Agent** writes the **Final Master Version** — absorbs valid
   feedback and rewrites naturally (never pastes review comments into script)
6. Save only Final Master as `script_text`
7. Export only Final Master to Teleprompter DOCX

Never export: first draft, student/critic/mentor reviews, internal labels,
evidence notes, sources, citations, needs_review, needs_confirmation, scores.

Agency: one draft + one review bundle + one final rewrite; up to **2** final
rebuilds only if a serious issue remains. Fatal leftovers are tracked
internally (`needs_review` on the job for admin/debug) — never printed beside
the script or in DOCX. No infinite debates / open-ended multi-agent chat.

### Persistent Source Memory (uploads)

PDFs and uploaded sources are processed **once** into persistent Source Memory
(`source_analyses.source_memory_json`: facts, examples, terminology, summary,
`source_hash`, extraction version). Generation prompts receive only relevant
memory snippets per lesson — never the full PDF/extracted text repeatedly.
If `source_hash` is unchanged: do not re-extract, do not re-read, reuse memory.

### Cost Hygiene + Trusted Knowledge Gate

Quality-first with **no waste**:
- Compact stage Admin Knowledge packs (`map_planning_rules_pack`,
  `lesson_writing_rules_pack`, `review_rules_pack`, `final_export_rules_pack`)
- Web research per **distinct information need** (Research Need → Research Memory),
  reused unless stale / low-confidence / platform-current freshness requires refresh
- Factual authority only from trusted educational/official/academic sources —
  social posts, forums, TikTok, Reddit comments are **not** factual authority
- Academic/book/course knowledge is **transformed** into Rukn spoken Egyptian
  Arabic teleprompter format (not academic prose)
- Identical retry inputs are blocked; max 2 Final Master rebuilds; Premium
  Creator → Student → Specialist → Mentor → Final rewrite stays intact
- Usage panel: total est. cost, cost/lesson, web searches, source memory reuse,
  waste warnings (never in DOCX)

### Autonomous web research (`web_research_mode`)

Default: **`autonomous_gap_fill`**. Alternative: `disabled`.

When uploads are incomplete, Rukn researches missing factual/practical gaps
from trusted web sources **without asking the user**. Results go into internal
Web Source Memory (cached on the course — same query is not re-fetched) +
Evidence Ledger. Job telemetry tracks `web_searches_count`. If a claim is not
well supported: omit or safely rewrite — never hallucinate, never show
"needs confirmation".

Sensitive domains (religious/legal/medical/financial/high-stakes science):
stricter sources, weaker claims omitted; human reviewer reads the clean final
script outside the app. Evidence/risk flags may live on the job for admin
debug only — never in DOCX or normal UI.

### Course map two-pass (before any lesson)

The course map itself uses the same creator → student → specialist → mentor →
rebuild loop. The first map draft is never accepted as final. Only the **Final
Course Map** starts lesson generation. Users are not asked to approve the map.

### Duration rules (Premium)

- Serious Premium courses normally aim for **≥ ~120 minutes** total estimated
  spoken time; if the plan is shorter and not a mini/preview, rebuild with real
  depth (bridges, examples, practical steps) — never motivational padding.
- Lessons normally **~2–5 minutes**; under ~2 minutes → merge or expand with real
  value only; over ~5 minutes allowed when a connected idea would go shallow if
  split. No fixed maximum lesson count.

### Final course quality gates (pre-export)

Before DOCX export, Rukn runs local gates (no new agents):

1. **Promise fulfillment** — does the course deliver the brief outcome?
2. **Learner level** — consistent targeting for the 80% serious learner
3. **Recordability** — spoken teleprompter rhythm; strip written tone / leaks
4. **Application** — practical courses need clear do-steps
5. **Repetition** — merge/rewrite near-duplicate hooks/lessons
6. **Course ending** — complete the journey without sales/fake motivation
7. **Egyptian market reality** — default `target_market=egypt`; local clients,
   budgets, WhatsApp/FB/IG; no US/EU-translated fluff (unless market is global/custom)
8. **Evergreen durability** — principles over exact salaries/prices/dates/UI
   button positions; demos support lessons, they are not button-click tutorials
9. **Originality + rights** — sources are knowledge only (facts/concepts), never
   writing templates; no close paraphrase, catchphrases, distinctive examples,
   or creator imitation; free/public sources still not free to copy

Gates may rewrite scripts internally. DOCX stays spoken transcript only.
After generation the UI can show: Course generated · lessons · ~duration ·
complete/partial · optional internal flag count (never critic notes).

`target_market`: `egypt` (default) | `arab_market` | `global` | `custom`.

### Preview vs Premium (`generation_quality_mode`)

| | **Premium** (default) | **Preview** |
|---|---|---|
| Use | Real course generation | Faster direction tests |
| Pipeline | Full Student + Critic + Mentor AI review bundle | Simplified local review only |
| Output | Final Master teleprompter script | Still teleprompter-ready |
| UI | Mode label only — never raw temperature or agent internals |

Internal reviews stay hidden. Users see progress/status, estimated usage, last
saved, and partial DOCX availability. On quota/rate/timeout/provider error:
completed lessons persist, clear stopped status, partial DOCX downloadable when
lessons exist; regenerate starts a new job (mid-pipeline pair-resume remains
unsupported by design).

### Locked multi-agent review loop (Admin Knowledge)

`rukn_creator_critic_loop` — the Creator **does not self-criticize**. Roles:

1. **Creator Agent** — full first draft, uninterrupted
2. **Student Agent** — broad ~80% learner confusion on the completed draft
   (`rukn_student_confusion_layer`)
3. **Specialist Critic Agent** — accuracy, weakness, filler, realism, language,
   domain problems (harsh domain instructor; not a social commenter)
4. **Master Mentor Agent** — hook, loop, pacing, creator instinct, subtle
   academic gaps (`rukn_master_mentor_engine`; synthetic, not a named clone)
5. **Creator Agent** — Final Master Version: absorb valid feedback and rewrite
   naturally (never paste review comments into the script)

Only Final Master becomes `script_text` / Teleprompter DOCX. Never export
first draft, student/critic/mentor reviews, labels, evidence, sources,
citations, needs_review, needs_confirmation, or quality scores.

User progress only: Writing first draft → Checking student clarity → Running
specialist critic → Consulting master mentor → Rewriting final master version
→ Saving lesson X/Y.

## Master Creator-Academic Mentor

Synthetic spiritual mentor of the course creator: platform instinct + academic
awareness. Does **not** write instead of the creator; does **not** imitate any
named creator. Compact `mentor_review` is internal only. Progress may show
"Consulting master mentor" without exposing mentor notes.

## Student Confusion Layer

Represents broad serious learners (not the top 5% genius, not rare edge cases).
Catches missing terms, skipped steps, unclear transitions, and practical
confusion ("يعني إيه؟" / "طب أطبق ده إزاي؟"). Follows an **80% rule**: fix
blockers for most learners; ignore rare/philosophical/textbook expansion asks.
Does **not** turn courses into beginner padding. Reviews stay internal;
progress may show "Checking student clarity" without exposing review text.

Critic/`student_review`/`mentor_review` stay compact and hidden. Users see
**progress/status only**. Prefer: one draft call + one review-bundle call +
one final-rewrite call (prompt_compiler v1.7) — not unbounded multi-agent
credit burn. Hard limit: one draft / one review bundle / one final rewrite.
On quota/rate/timeout the run stops cleanly and may offer partial DOCX.

Seed seeds doctrine, curve, persona, critic-loop, student-layer, and mentor
keys for new installs. Existing DBs get missing keys on next startup. To
intentionally replace *selected* system defaults, use:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.seed_admin_knowledge --refresh-defaults --confirm
```

This deactivates the previous active version (kept as an inactive backup row
with a timestamped title) and creates a new active version from code
defaults. It never runs on startup and does not touch custom keys or
`rukn_core_rules` / `rukn_writing_style` / presets. Omitting `--confirm`
prints the warning and exits without changing anything.

Golden doctrine checks (no live AI):

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/golden -q
```

## Generation presets

`Course.generation_preset` (`app/models/enums.py` `GenerationPreset`,
default **Balanced**) is a named intent for how generation should approach
a course. See `app/generation/presets.py`:

| Preset | Intended use | Temperature |
|---|---|---|
| `conservative` | Review/correction passes - accuracy over variety. | 0.2 |
| `balanced` (default) | Everyday reel/module writing. | 0.45 |
| `creative` | Generating multiple candidate openings/examples/angles. | 0.75 |
| `fusion` | Merging a Conservative attempt and a Creative attempt into one (not implemented). | 0.35 |
| `strict_teleprompter` | Final export/cleanup pass enforcing the teleprompter DOCX contract strictly. | 0.25 |

`PRESET_TEMPERATURES` in the same module maps each preset to the
temperature values above. Every generation run logs which preset was used
(`{"step": "load_brief", "preset": "..."}` in the job's internal
`log_json`).

- **`FakeProvider`** (default) ignores the preset entirely - its output
  never changes per preset.
- **`AnthropicProvider`** actually uses it: `app/generation/orchestrator.py`
  calls `provider.configure_for_run(brief.generation_preset)` once, right
  after the course brief loads and before the first AI call, which
  re-resolves and applies that preset's temperature (see
  `AnthropicProvider.configure_for_run` in
  `app/ai/anthropic_provider.py`) for every stage's `messages.create` call
  for the rest of that run. This hook is deliberately `hasattr`-guarded at
  the call site (not a method on the `AIProvider` ABC) so `FakeProvider`
  needs zero changes.

## Connecting a real Anthropic provider

`AI_PROVIDER=fake` (the default) needs no key and produces deterministic
placeholder content - safe for all local dev and the whole automated test
suite. Switching to `AI_PROVIDER=anthropic` calls the real Claude API via
`app/ai/anthropic_provider.py` and costs real API credits. Two things to
know before flipping the switch:

- **Request timeout.** `ANTHROPIC_REQUEST_TIMEOUT_SECONDS` (default `120`,
  optional) bounds how long a single Anthropic call can hang before
  failing with a clean, classifiable `timeout` error (see "Generation
  resilience" below) instead of hanging the whole request indefinitely.
- **Switching back to `fake` at any time needs zero code changes** - just
  set `AI_PROVIDER=fake` (and redeploy/restart if in production). Nothing
  else needs to change.

### First real test mode (do this once, with a real key, before trusting it for anything bigger)

The cheapest, most predictable way to confirm the real provider actually
works end to end: create a tiny course with a **manual course map**. This
still makes one `build_course_map` call, but
`backend/app/prompts/build_course_map.md` instructs the model to convert
`manual_map_text` "as-is" rather than design its own structure - so a
short, explicit map keeps the whole run down to exactly one module and two
lessons (one `build_course_map` call, two `write_single_reel`/review
cycles, one `final_review`) instead of however large a from-scratch map
might turn out.

1. Set in `backend/.env` (or the equivalent Render env vars - see
   "Deploying to Render" below):

   ```
   AI_PROVIDER=anthropic
   ANTHROPIC_API_KEY=<your real key>
   AI_MODEL_NAME=<check Anthropic's current model list for the exact slug, e.g. something like "claude-sonnet-4-5-..." - do not copy that string verbatim, it is a placeholder, not a verified-current model name>
   ```

   Restart the backend (`uvicorn`) after changing `.env` so it picks up
   the new values.

2. Create a course with `generation_preset=balanced`, no source uploads,
   and a short, explicit `manual_map_text` that requests exactly one
   module with two lessons - either via the UI (Course form's "Manual
   course map" field) or directly via curl:

   ```powershell
   curl -X POST http://localhost:8000/courses `
     -H "Authorization: Bearer <your login token>" `
     -H "Content-Type: application/json" `
     -d '{
       "title": "Real Provider Smoke Test",
       "audience": "internal test",
       "outcome": "confirm the real Anthropic provider works end to end",
       "structure_mode": "connected_no_modules",
       "generation_preset": "balanced",
       "manual_map_text": "Exactly one module titled '\''Module 1'\'' with exactly two short lessons: Lesson 1 (a 30-second intro) and Lesson 2 (a 30-second wrap-up). Do not add any other modules or lessons."
     }'
   ```

   (Get `<your login token>` from `POST /auth/login` with your
   `ADMIN_USERNAME`/`ADMIN_PASSWORD` first.)

3. Trigger generation for that course - UI's "Generate" button, or:

   ```powershell
   curl -X POST http://localhost:8000/courses/<course_id>/generate `
     -H "Authorization: Bearer <your login token>"
   ```

4. Confirm the job ends `"status": "completed"` (`GET
   /jobs/{job_id}`) and download the DOCX (`GET
   /courses/{course_id}/download/latest`) to confirm it reads like a real,
   teleprompter-ready script for one module/two lessons - not placeholder
   text.

5. Set `AI_PROVIDER=fake` again afterward if you don't want further runs
   to spend real credits.

`backend/scripts/smoke_test.py` (see "Production smoke test" below) is a
**login/auth-only** smoke check - it deliberately never touches
generation, so it is not a substitute for the steps above and needs no
changes to support this. There is no automated test that calls the real
Anthropic API (and there should never be one - see the top of
`backend/tests/test_anthropic_provider.py`); the steps above are the only
supported way to validate a real key/model before relying on it.

## Generation resilience

The synchronous request-response model (`POST /courses/{course_id}/generate`
waits for the whole pipeline, see "Repository Structure" above) stays as-is
for this MVP - no Celery/Redis/task queue. What changed is that a mid-run
failure no longer loses already-completed work:

- **Incremental persistence.** `app/generation/orchestrator.py` flushes the
  course map (`GenerationJob.course_map_json`) to the DB as soon as it's
  built, and appends each completed reel to `GenerationJob.completed_reels_json`
  right after it's generated - not batched at the end. `last_completed_step`,
  `completed_modules_count`, and `completed_reels_count` track progress the
  same way. All four are internal-only (same exclusion principle as
  `log_json` - see `app/schemas/generation_job.py`); the API only ever
  returns the small, user-safe summary fields.
- **If credits/API calls fail mid-generation:** the pipeline classifies the
  error (`app/generation/errors.py` `classify_provider_error` - one of
  `rate_limit`, `insufficient_quota`, `timeout`, `provider_unavailable`,
  `malformed_response`, `context_too_long`, `unknown`) and checks what's
  already saved. If a course map and/or at least one completed reel exists,
  the job ends `JobStatus.PARTIAL` (not `FAILED`) with a clean,
  category-specific `error_message` (never the raw exception text) and a
  downloadable partial DOCX. If nothing usable was saved yet (e.g. failure
  before the course map even finished), the job ends `JobStatus.FAILED`.
- **Partial DOCX** (`app/services/docx_export.py`
  `export_partial_course_to_docx`) follows the exact same module/lesson
  heading structure and Arabic-friendly formatting as a real export, but
  only for modules that actually have at least one completed reel (a module
  with zero completed reels is skipped, not padded/invented), with exactly
  one extra paragraph before the course title: "Partial draft — generation
  stopped before completion." Nothing else extra - no logs, no review
  notes, no error text. Saved to
  `storage/outputs/{course_id}/partial_job_{job_id}.docx` - a naming
  pattern distinct from a real `course_v{n}.docx` version so it's never
  confused with, or picked up as, a completed version. Download via
  `GET /jobs/{job_id}/download-partial`.
- **Resume is not implemented.** A `partial` job's per-module review
  bookkeeping (specifically, whether the two-module repetition review for
  the current pair of modules already ran) can't be safely reconstructed
  from `completed_reels_json` alone - a crash between a module's own review
  and its pairing review would look identical, on resume, to one where the
  pairing already happened, silently skipping a required check. Rather than
  ship that, there's no `resume_generation` function and no `/resume`
  route. **Downloading the partial DOCX is the supported recovery path
  today.**
- **Regenerate from scratch is unaffected.** `POST /courses/{course_id}/generate`
  always starts a brand-new `GenerationJob` row, independent of any
  existing partial/failed job for the same course - it never blocks on, or
  mutates, that job's saved state. The frontend labels this "Regenerate
  from Scratch" once a partial/failed job already exists, to make clear
  it's a fresh restart, not a continuation.
- This persistence work (the incremental flushes, the clean error
  categories, the partial export) is exactly what a future background-job
  upgrade (Celery/RQ/a task queue) would build on - the synchronous
  request-response route is an acceptable MVP trade-off precisely because
  the state it produces along the way is already loss-safe.

## Prompt compiler

`app/generation/prompt_compiler.py` keeps every AI-provider prompt lean
instead of dumping everything into every call:

- **Rules per stage** (`select_rules_for_stage`) - each of the 8 pipeline
  stages (`app/prompts/prompt_registry.py` `PipelineStage`) only receives
  the admin-knowledge keys actually relevant to it (e.g. a review stage
  gets the quality rubric and forbidden phrases, not the course-structure
  rules a map-building stage needs). `rukn_generation_presets` is never
  sent to any stage - it's for admin visibility only.
- **Source budget trimming** (`compile_source_context`) - every stage's
  source excerpts are capped at a total character budget (default 6000).
  If sources would exceed it, the lowest-priority excerpts are trimmed
  first; `user_notes` sources are protected from trimming for as long as
  possible. This never fails/raises - it degrades gracefully by cutting
  text, not by dropping sources or erroring out.
- **Source Authority Firewall** - the same function also labels every
  excerpt with `allowed_use`/`disallowed_use`/`style_contamination_warning`
  and orders the result by a fixed authority hierarchy, never by the
  `priority` field. See [Source Authority](#source-authority) above.

`flow_reference` sources are reduced to a 12-field heuristic **flow
profile** (`build_flow_profile`) instead of a summary or quote: `opening_energy`,
`hook_mechanism`, `pacing`, `transition_style`, `idea_progression`,
`escalation_pattern`, `tension_curve`, `climax_or_turning_point`,
`example_integration`, `ending_motion`, `natural_speech_notes`, and
`things_not_to_copy`. Every field is a qualitative description derived
purely from sentence-length stats and regex-detected connector/instruction/
question markers (stdlib only, no ML/NLP) - never a literal phrase lifted
from the source - so the profile stays small and bounded no matter how long
or heavily-structured the source is, and can never itself leak a
catchphrase, signature line, or section order back out.

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

**Source category rename note:** `SourceCategory` values were renamed/expanded
(`main_content`/`supporting` -> `scientific_reference`, `spoken_style` ->
`flow_reference`, `notes` -> `user_notes`, plus new `raw_material`; see
"Source types" above). Any existing local `course_sources` rows still holding
an old category string will fail to validate on read - expected for this
pre-launch internal tool, not a bug. Fix with `python -m app.reset_local_db
--seed` (stop `uvicorn` first).

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
| `backend/.env` | `AI_MODEL_NAME` | Model name for `AnthropicProvider`; only required when `AI_PROVIDER=anthropic` - check Anthropic's current model list for the exact slug |
| `backend/.env` | `ANTHROPIC_REQUEST_TIMEOUT_SECONDS` | Optional, only relevant when `AI_PROVIDER=anthropic`. How long a single Anthropic API call can run before failing with a clean `timeout` error. Default `120` |
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
  "storage_dir_writable": true,
  "ai_provider": "fake",
  "ai_provider_ready": true
}
```

`ai_provider` is the raw `AI_PROVIDER` value (`"fake"` or `"anthropic"` -
not a secret). `ai_provider_ready` is `true` for `fake` always, or for
`anthropic` only once both `ANTHROPIC_API_KEY` and `AI_MODEL_NAME` are
set - the frontend's course page uses this to show "Anthropic (not fully
configured)" with a warning badge instead of silently claiming a working
real provider that isn't actually configured yet.

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

Backend environment variables - **Option A (recommended: Postgres + Disk), fake AI provider (default)**:

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

To use the real Anthropic provider instead, change exactly three values
(everything else above stays the same) - see "Connecting a real Anthropic
provider" above for what these mean and the First Real Test Mode procedure
to validate them once set:

```
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=<secret, set in Render Dashboard - your real Anthropic API key>
AI_MODEL_NAME=<secret, set in Render Dashboard - check Anthropic's current model list for the exact slug>
# Optional - defaults to 120 if unset:
# ANTHROPIC_REQUEST_TIMEOUT_SECONDS=120
```

Switching back to the fake provider at any time is just `AI_PROVIDER=fake`
again (redeploy to pick it up) - no code change either way.

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
lifespan). There is no Alembic migration tool in this MVP.

On startup, `init_db()` also runs SQLite/Postgres-safe `ALTER TABLE ... ADD
COLUMN` helpers for newly introduced columns (`_ensure_course_columns`,
`_ensure_course_source_columns`, `_ensure_source_analysis_columns`,
`_ensure_generation_job_columns`). **Restart the backend after deploy** so
ALTERs apply. Existing courses and Admin Knowledge rows are preserved.

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
  `docs/BUILD_PLAN.md`. Example: `courses` gained a `generation_preset`
  column (see "Generation presets" above) - existing local/production
  databases need this column added the same way before that code deploys.
  Same for `courses.target_market` (default `'egypt'`) — added via
  `_ensure_course_columns` on SQLite startup; Postgres needs the matching
  `ALTER TABLE courses ADD COLUMN target_market TEXT DEFAULT 'egypt'` if
  the table already exists.
  Same situation for `generation_jobs`' new resilience columns
  (`last_completed_step`, `completed_modules_count`, `completed_reels_count`,
  `error_category`, `partial_docx_path`, `course_map_json`,
  `completed_reels_json` - see "Generation resilience" above): a local dev
  DB with existing job rows needs the equivalent manual `ALTER TABLE ...
  ADD COLUMN ...` (or just `python -m app.reset_local_db --seed`, if losing
  local data is fine) before/after deploying this code.

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
