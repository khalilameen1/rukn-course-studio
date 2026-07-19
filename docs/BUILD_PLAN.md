# Build Plan

## Product: Rukn Course Studio

**Status:** Draft v1.0 — Documentation & Architecture Phase
**Companion docs:** `docs/PRD.md`, `docs/ARCHITECTURE.md`
**Last Updated:** 2026-07-13

---

## 0. Guiding Principle

**Do not build everything at once.** Each phase below produces a working, reviewable slice before moving to the next. No phase should start until the previous phase's exit criteria are met. Phase 0 (this documentation) is complete once `PRD.md`, `ARCHITECTURE.md`, and `BUILD_PLAN.md` are reviewed and approved — no application code is written until that approval happens.

---

## Phase 0 — Documentation & Architecture (current phase)

**Goal:** Shared understanding of what's being built and how, before any code exists.

- [x] `docs/PRD.md` — scope, users, functional/non-functional requirements, MVP boundaries.
- [x] `docs/ARCHITECTURE.md` — system components, immutable context/map, effectful review pipeline, and anti-laziness/repetition/hallucination mechanisms.
- [x] `docs/BUILD_PLAN.md` — this document.

**Exit criteria:** Stakeholder review/sign-off on all three docs. Open Questions in `PRD.md` §11 are answered or explicitly deferred with an owner.

**Explicitly not done in this phase:** No repo scaffolding, no framework selection commitment, no code, no schema migrations, no prompts.

---

## Phase 1 — Foundations & Rules Management

**Goal:** Stand up the project skeleton and the one piece with zero dependencies on generation: the Admin Rules system. Nothing here touches LLM generation yet.

- Project scaffolding (backend + frontend + shared types), per the technology direction confirmed after Phase 0 sign-off.
- Data layer setup for: Rukn Rules (with versioning), basic auth/access boundary (internal-only).
- Rukn Rules schema implementation per `ARCHITECTURE.md` §4.1 (`structure_rules`, `style_rules`, `pedagogy_rules`, `formatting_rules`, `prohibited_content`, `glossary`).
- Admin Rules Page: CRUD UI + versioning UI (create version, view history, activate a version).
- Seed one real, complete Rukn rule set for "practical skill" courses (this is required content input for every later phase's testing — do not use placeholder rules).

**Exit criteria:** An admin can create/edit a full rule set through the UI and it persists correctly with version history; no course/generation functionality exists yet.

---

## Phase 2 — Course, Brief & Source Intake (no generation yet)

**Goal:** Capture all inputs to the pipeline and get them stored/validated correctly, with zero LLM calls.

- Course Service: create course, store Course Brief.
- Course Creation Page: brief form; manual Course Map builder (structured, per `ARCHITECTURE.md` §4.3); linking of sources to a course.
- Source Ingestion Service: upload handling + format-specific extraction for DOCX, PDF, TXT, MD, transcript text (per `ARCHITECTURE.md` §5); parse-status surfaced in UI.
- Source Upload Page: upload, list, delete/replace before a run starts.
- Manual course map validation against `structure_rules` bounds (reject/flag, do not silently rewrite).

**Exit criteria:** A user can create a course, write a brief, optionally build a manual course map, optionally upload and link sources of all 5 supported types, and see them correctly parsed/stored — with no "Generate" action wired to real generation yet (can be stubbed/disabled).

---

## Phase 3 — Pipeline Skeleton: Map Building + Orchestrator Shell (Stage 1 only)

**Goal:** Build the Generation Orchestrator's state machine and wire up only Stage 1 (course map build/validate) end-to-end, so the hardest infrastructure problem (durable, resumable multi-stage execution) is solved before layering on 7 more stages.

- Generation Run entity + immutable snapshot creation (rules version + brief + sources + map) per `ARCHITECTURE.md` §4.5.
- Orchestrator scaffold: stage tracking, persistence of intermediate artifacts, coarse status exposed to frontend (`queued → mapping → ...`), resumability after crash/restart.
- Stage 1 implementation: generate a course map from brief + sources + rules when no manual map is supplied; validate manual maps otherwise.
- Course Creation Page: wire "Generate" to actually run Stage 1 and stop (temporary MVP-of-MVP checkpoint) — output visible only as an internal/debug view at this phase, not yet a DOCX.

**Exit criteria:** Triggering generation reliably produces a valid, rules-compliant course map (manual or generated) and the run stops cleanly in a `map_ready` state. Orchestrator survives a restart mid-run without corrupting state.

---

## Phase 4 — Reel-by-Reel Generation + Per-Reel Review (Stages 2–3)

**Goal:** Add real content generation, but only the smallest-scope loop: draft a reel, review it, retry if needed. This is the first phase that produces actual instructional content.

- LLM generation-provider abstraction (per `ARCHITECTURE.md` §9) — implemented for stage 2 (drafting) and stage 3 (review) usage.
- Stage 2: reel-by-reel generation using reel objective + Rukn Rules + relevant Source segments + bounded "prior context" summary (not full history) per `ARCHITECTURE.md` §6 Stage 2.
- Stage 3: per-reel silent review (structure/style/pedagogy/prohibited-content/grounding checks) + bounded retry-and-rewrite loop.
- Persist reel drafts, revision history, and review log entries per `ARCHITECTURE.md` §4.6–4.7.
- Internal-only debug view to inspect reel drafts + review verdicts (for pipeline tuning, not the end-user product surface).

**Exit criteria:** For a real course map, the system can generate every reel in a course, each individually passing (or being flagged after bounded retries by) per-reel review, with full traceability in the review log. No wider review yet — repetition/laziness across reels/modules is not yet checked.

---

## Phase 5 — Effectful Wider Review Layers

**Goal:** Add the review layers that catch what Stage 3 structurally cannot see: repetition and degradation across reels and modules.

- Delete log-only five-reel, AI module, and two-module calls and their provider/prompt/routing surface.
- Apply independent review findings through bounded Creator rewrite and deterministic re-check.
- Enforce lesson, module, adjacent-module, and whole-course checks as export blockers when unresolved.
- Verify final rebuild actions changed their requested targets; otherwise fail closed.

**Exit criteria:** Unit/integration fixtures prove no serious/fatal finding can be logged and ignored, without generating a complete course or calling a paid provider.

---

## Phase 6 — Full-Course Review/Rebuild + DOCX Export (Stages 7–8)

**Goal:** Close the loop: the final safety-net review and the one artifact the user actually receives.

- Stage 7: full-course review with authority to trigger targeted reel/module rebuilds; re-check loop with bounded retries; `needs_review` terminal state for runs that can't converge.
- DOCX Exporter: render final approved content tree using `formatting_rules`, producing a real, correctly formatted `.docx`.
- Wire end-to-end: Course Creation Page "Generate" → effectful pipeline → coarse status → download link on success, clear actionable error/needs-review state on failure.
- Remove/disable any temporary debug-output-as-primary-flow scaffolding from Phases 3–5 so the shipped UX matches `PRD.md` NFR-5 (opacity of process).

**Exit criteria:** A user can go from brief-only (or brief+map+sources) to a downloaded, correctly formatted final DOCX with no visibility into intermediate reels, matching all functional requirements in `PRD.md` §7. This is the first phase that delivers the complete MVP end-to-end.

---

## Phase 7 — Hardening, Observability & Internal QA

**Goal:** Make the MVP reliable and tunable, not just functional.

- Full traceability review: confirm any final DOCX can be traced back to its exact rules version/brief/map/sources/review history (`ARCHITECTURE.md` §8).
- Tune retry/escalation thresholds per stage using real generation runs (finalize the Open Question in `PRD.md` §11).
- Cost/latency measurement across realistic course sizes; confirm status UX (NFR-7) communicates progress adequately for real run durations.
- Edge cases: unreadable/scanned PDFs, empty briefs, manual maps that violate structure_rules, very short/very long courses, source content that contradicts the brief.
- Internal QA pass against every success criterion in `PRD.md` §10 using real Rukn course briefs (not synthetic test data only).

**Exit criteria:** MVP is stable enough for real internal usage by Rukn course creators; known limitations are documented, not silently broken.

---

## Explicit Sequencing Rules

1. Do not start Phase 2 until Phase 1's Rukn Rules system is real (not placeholder) — every later phase depends on real rules, not stubs, to validate against.
2. Do not attempt Stages 4–7 (Phase 5–6) until Stage 2–3 (Phase 4) reliably produces individually-good reels — wider review layers are meaningless if the base unit is broken.
3. DOCX export (Phase 6) is deliberately last among generation phases — it is the easiest part technically and the least valuable to build early, since there's nothing correct to export until Phase 5 is solid.
4. No phase introduces a second course type or non-MVP feature (see `PRD.md` §4/§9) — all 7 build phases stay within "practical skill courses" MVP scope.

## Explicit Non-Sequencing (anti-patterns to avoid)

- Do not build the DOCX exporter early "to see output" using fake/unreviewed content — it creates a false sense of completion and tests the wrong thing.
- Do not implement all 8 pipeline stages in one phase — each stage should be independently testable against real generated content before the next is layered on, per the anti-laziness/repetition/hallucination goals in `ARCHITECTURE.md` §7.
- Do not add a chat-style or reel-editing UI at any point in MVP phases — this contradicts `PRD.md` Non-Goals and NFR-5.
