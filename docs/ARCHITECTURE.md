# Architecture Document

## Product: Rukn Course Studio

**Status:** Draft v1.0 — Documentation & Architecture Phase
**Companion docs:** `docs/PRD.md`, `docs/BUILD_PLAN.md`
**Last Updated:** 2026-07-13

---

## 1. Architectural Principles

1. **The user sees exactly one artifact: the final DOCX.** Every internal stage (map building, reel drafting, multi-level review, rebuild) is a backend process, not a UI experience.
2. **Generation is incremental by construction.** The system is architecturally incapable of generating an entire course in a single model call — the pipeline forces reel-by-reel generation with mandatory checkpoints. This is the primary defense against laziness/repetition/hallucination, not a prompting trick.
3. **Rules are data, not prompt text scattered in code.** Fixed Rukn knowledge lives in a structured, versioned store the pipeline reads from — admins edit data, not code.
4. **Every generation run is traceable.** Given a final DOCX, it must be possible to reconstruct exactly which rule version, brief, sources, map, and review outcomes produced it.
5. **Review is layered by scope, not just repeated at one grain.** Local checks (per reel) catch local problems (drift within one reel); wider checks (every 5 reels, per module, per 2 modules, full course) catch problems only visible at larger scope (repetition across reels, degradation across modules, global inconsistency). Each layer has a distinct job — they are not redundant copies of each other.
6. **Regeneration over live editing (MVP).** Correction happens by re-running (parts of) the pipeline, not by a human hand-editing generated text in-app.

---

## 2. High-Level System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (UI)                           │
│                                                                        │
│   Admin Rules Page   |   Course Creation Page   |   Source Upload    │
│                                                                        │
│   Status view (coarse) --------------------------> Download DOCX     │
└───────────────────────────────┬────────────────────────────────────--┘
                                 │  REST/RPC API
┌───────────────────────────────▼──────────────────────────────────────┐
│                          APPLICATION LAYER                           │
│  - Rules Service (CRUD + versioning)                                 │
│  - Course Service (brief, map, sources linkage, run lifecycle)       │
│  - Source Ingestion Service (upload, parse, normalize, store text)   │
│  - Generation Orchestrator (owns the pipeline state machine)         │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │
┌───────────────────────────────▼──────────────────────────────────────┐
│                     GENERATION PIPELINE (internal)                   │
│  1. Course Map (build/validate)                                      │
│  2. Reel-by-reel generation                                          │
│  3. Per-reel silent review                                           │
│  4. Every-5-reels review                                             │
│  5. Per-module review                                                │
│  6. Every-2-modules review                                           │
│  7. Full-course review/rebuild                                       │
│  8. DOCX export                                                      │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │
┌───────────────────────────────▼──────────────────────────────────────┐
│                              DATA LAYER                               │
│  Rules store | Courses/Briefs | Sources (raw+parsed) | Course Maps   │
│  Reels (draft+final+revision history) | Review Logs | Generated DOCX │
└────────────────────────────────────────────────────────────────────--┘
```

---

## 3. Component Breakdown

### 3.1 Frontend

Three functional surfaces, deliberately minimal:

- **Admin Rules Page** — structured forms/editors over the Rukn Rules schema (§4.1). Not a raw text blob editor; fields map to the schema so the pipeline can address rule sections programmatically. Includes versioning UI (view history, activate a version).
- **Course Creation Page** — form for the course brief (§4.2), optional manual course map entry (structured builder: add module → add reels with title/objective, or import/paste a structure), optional linking of previously uploaded sources, a "Generate" action, and a coarse status indicator (`queued → mapping → generating → reviewing → exporting → done/failed`).
- **Source Upload Page** — file upload (DOCX/PDF/TXT/MD/transcript), list of uploaded sources with parse status (`parsed` / `failed: reason`), delete/replace before a run starts.

The frontend never renders reel-level draft content as a primary feature. (An optional, clearly-separated "internal debug log" view gated to admins/devs may exist for troubleshooting — see PRD FR-20 — but it is not part of the main course-creator flow.)

### 3.2 Application Layer Services

- **Rules Service** — CRUD + versioning over Rukn Rules. Exposes a "get active rules for new runs" read path used only by the orchestrator.
- **Course Service** — owns Course, Course Brief, and Course Map entities; manages linking Sources to a Course; exposes "start generation run" which snapshots brief + map + source refs + active rule version into an immutable **Generation Run** record.
- **Source Ingestion Service** — handles upload, file-type validation, text extraction/normalization per format (§5), and persistence of parsed text + metadata (page/section boundaries where available, for later citation/grounding).
- **Generation Orchestrator** — the state machine that executes the 8-stage pipeline (§6) for a Generation Run, persists intermediate artifacts (map, reel drafts, review verdicts) for traceability, exposes coarse status to the frontend, and on success hands the final assembled content to the DOCX Exporter.
- **DOCX Exporter** — deterministic renderer that takes the final, reviewed course content tree (modules → reels, front/back matter) plus formatting rules from Rukn Rules and produces the `.docx` binary.

### 3.3 Why an Orchestrator/State Machine (not a single long LLM chain)

The pipeline has 8 distinct stages with different scopes (reel / 5-reels / module / 2-modules / course) and different failure-handling needs (a failed per-reel review triggers a reel rewrite; a failed full-course review can trigger a targeted rebuild of specific modules, not necessarily everything). This requires explicit state, not an implicit chain-of-thought inside one model call. The orchestrator:

- Tracks pipeline position (which stage, which reel/module index).
- Persists each stage's output and verdict, enabling resumability after failure/crash.
- Applies bounded retry policy per stage (see §6.9) instead of infinite regeneration loops.
- Is the single place that decides "is this run done, does it need another pass, or has it failed."

---

## 4. Core Data Model

### 4.1 Rukn Rules (Admin-managed, versioned)

Structured, not free text, so the pipeline can pull specific sections deterministically. Proposed top-level sections:

- `structure_rules` — required course/module/reel shape for "practical skill" courses: min/max reels per module, required reel components (e.g., objective, explanation, practical example, common mistake, recap/check), required module components (intro, recap), required course front/back matter.
- `style_rules` — tone of voice, person/voice (e.g., second person, direct/practical), sentence/paragraph length guidance, terminology to prefer/avoid.
- `pedagogy_rules` — instructional patterns mandated for practical-skill content (e.g., "every reel must end with an actionable step," "avoid pure theory without an application").
- `formatting_rules` — DOCX-level formatting/branding: heading styles, fonts, numbering scheme, required cover/section pages — consumed directly by the DOCX Exporter.
- `prohibited_content` — disallowed claims, topics, phrasing.
- `glossary` — canonical terms/definitions to enforce consistent terminology across reels (also used by review stages to catch terminology drift).
- `version` metadata — id, created_at, created_by, active flag, changelog note.

A Generation Run pins to exactly one Rules version at creation time (PRD FR-2).

### 4.2 Course Brief

`title`, `audience`, `skill_outcomes[]`, `scope_guidance` (e.g. target module/reel counts or "let system decide"), `special_instructions` (free text), `course_type` (fixed to `practical_skill` in MVP).

### 4.3 Course Map

Ordered list of Modules, each with: `title`, `objective`, ordered list of Reels, each with `title`, `objective`, optional `notes`. Two provenance types: `manual` (user-supplied, validated against `structure_rules` bounds but not restructured) or `generated` (produced by pipeline stage 1 from brief + sources + rules). A course map is immutable once a generation run starts.

### 4.4 Sources

`file_type` (`docx|pdf|txt|md|transcript`), raw file reference, `parsed_text`, `parse_status`, optional structural metadata (headings/pages/timestamps if derivable), linkage to Course.

### 4.5 Generation Run

Immutable snapshot at start: `rules_version_id`, `course_brief` (copy), `course_map` (copy, post stage-1), `source_ids[]`. Mutable during execution: `status`, `current_stage`, `reel_drafts[]` (with revision history), `review_logs[]`, `final_docx_ref` on success, `error` on failure.

### 4.6 Reel (generation unit)

`module_index`, `reel_index`, `title`, `objective`, `content` (current draft), `revision_history[]` (previous drafts + why replaced), `review_flags[]` (from any review stage that touched it), `status` (`draft|reviewed|approved|rebuilt`).

### 4.7 Review Log Entry

`stage` (one of the 8 pipeline stages), `scope` (e.g. `reel:3`, `reels:1-5`, `module:2`, `modules:3-4`, `course`), `verdict` (`pass|revise|fail`), `findings[]` (structured: type = `repetition|hallucination|laziness|style_violation|structure_violation|other`, description, affected reel/module refs), `action_taken` (`none|reel_rewrite|module_rebuild|course_rebuild`), `timestamp`.

---

## 5. Source Ingestion Pipeline

1. **Upload & type validation** — reject unsupported types immediately (PRD FR-14).
2. **Extraction** — format-specific text extraction:
   - DOCX → paragraph/heading-aware text extraction.
   - PDF → text extraction with page boundaries retained (fallback: flag low-confidence extraction, e.g. scanned PDFs without OCR in MVP — reject or warn rather than silently degrade).
   - TXT/MD → direct read; MD headings retained as structural hints.
   - Transcript text → treated as plain text but tagged `transcript` so downstream generation knows it's spoken-style source material, not a style model to imitate verbatim.
3. **Normalization** — whitespace/encoding cleanup, chunking into addressable segments (for later grounding references in review, e.g. "reel 4 claim not supported by any source segment").
4. **Storage** — persisted parsed text + metadata, linked to Course, available to pipeline stage 1 (map building) and stage 2 (reel generation) as grounding context.

Sources are optional; when absent, generation relies on the Course Brief + Rukn Rules only, and pedagogy rules should favor general practical guidance over invented specifics (PRD NFR-2).

---

## 6. The Internal Generation Pipeline (8 Stages)

This is the core of the system and the direct mechanism for preventing laziness, repetition, and hallucination. **None of these stages are user-visible as content** — only as a coarse status.

### Stage 1 — Build or Use Course Map

- If a manual course map was supplied: validate it against `structure_rules` bounds (reel/module counts, required components present at the planning level). Do not silently rewrite user structure; surface validation errors instead.
- If not supplied: generate one from Course Brief + Sources + Rukn Rules. Output: ordered modules → reels with titles/objectives — no reel body content yet.
- This map becomes the fixed skeleton for all subsequent stages; it is not revisited reel-by-reel (structural changes only happen in stage 7's full-course rebuild, if ever).

### Stage 2 — Generate Reel by Reel

- For each reel in map order: generate content using (a) that reel's title/objective, (b) the active Rukn Rules (structure/style/pedagogy/glossary), (c) relevant Source segments, and (d) a **compact "prior context" summary** (not full prior reel text) consisting of: prior reel titles/objectives in the same module, key terms/examples already used so far (to actively avoid repetition), and the module's position in the overall arc (to actively counter degradation toward later modules).
- Explicitly bounded context strategy: full verbatim history of all prior reels is not passed back in — it's summarized/indexed — otherwise cost/latency grows unboundedly and repetition-avoidance becomes the model's implicit job instead of the system's explicit job (see §7 Anti-repetition mechanism).
- Output: one reel draft, persisted immediately (crash-safe, resumable).

### Stage 3 — Silent Per-Reel Review

- Runs immediately after each reel is drafted, before moving to the next reel.
- Checks: structure_rules compliance (required components present), style_rules compliance, pedagogy_rules compliance, prohibited_content, and factual grounding against linked Source segments (flag unsupported specific claims).
- Verdict `pass` → move to next reel. Verdict `revise` → bounded retry: regenerate this reel with review findings injected as explicit correction instructions. Verdict `fail` after max retries → mark reel `flagged`, continue (do not block whole run on one reel; surfaced in stage 7/final QA).

### Stage 4 — Every-5-Reels Review

- Triggered after every 5th reel is drafted+passed stage 3 (window may cross module boundaries).
- Checks scoped to this 5-reel window: cross-reel repetition (duplicate examples/explanations/phrasing patterns), local terminology consistency (glossary), local pacing/difficulty consistency.
- Verdict `revise` → targeted rewrite of specific offending reel(s) within the window (not the whole window by default).

### Stage 5 — Per-Module Review

- Triggered when all reels in a module have passed stages 2–4.
- Checks: does the module fulfill its stated objective as a whole; internal ordering/flow between reels; module-level intro/recap components present and accurate to actual reel content; repetition within the module not caught by the 5-reel window (e.g. module has 7 reels).
- Verdict `revise` → targeted reel rewrite(s) or module intro/recap rewrite.

### Stage 6 — Every-2-Modules Review

- Triggered after every 2nd module completes stage 5 (or at course end if odd count).
- Checks scoped across the module pair: cross-module repetition, consistency of depth/effort (the primary **anti-laziness check** — comparing detail/length/quality signals between the earlier and later module in the pair), terminology consistency.
- Verdict `revise` → targeted module or reel rewrites within the pair.

### Stage 7 — Final Full-Course Review / Rebuild

- Triggered once all modules pass stage 6.
- Checks at whole-course scope: global repetition across all modules, global depth/effort consistency across the entire module sequence (not just adjacent pairs — catches slow drift stage 6 could miss), global terminology/glossary consistency, front/back matter accuracy against final module list, overall compliance with `structure_rules`/`pedagogy_rules` as a complete artifact.
- This stage has authority to trigger a **rebuild**: targeted regeneration of specific reels/modules identified as outliers, followed by a re-check (bounded retries), rather than assuming stages 3–6 already guarantee perfection. This is the safety net.
- Only on `pass` here does the run proceed to export.

### Stage 8 — Export DOCX

- Assemble final approved content tree (front matter, modules, reels, back matter) and render via the DOCX Exporter using `formatting_rules` from the active Rukn Rules.
- Persist the resulting file, mark Generation Run `done`, expose download to the user.
- This is the **only stage whose output the user ever sees.**

### 6.9 Retry & Failure Policy (cross-cutting)

- Each review stage has a configurable max-retry count for its corrective action (reel rewrite / module rebuild / course rebuild).
- Exceeding max retries at any stage does not silently continue with bad content — it marks the affected unit `flagged` and escalates: stage 7 always re-evaluates flagged units; if still failing after stage 7, the run ends in a `needs_review` state (distinct from `done`/`failed`) with a clear reason, rather than exporting a known-bad DOCX. Exact thresholds are a tuning parameter, not fixed in this document — see BUILD_PLAN.md and Open Questions in PRD.md.

---

## 7. Anti-Laziness / Anti-Repetition / Anti-Hallucination — Mechanism Summary

| Failure mode | Primary defense | Secondary defense |
|---|---|---|
| **Laziness** (later content thinner) | Stage 6 (every-2-modules) explicitly compares depth/effort signals across the pair | Stage 7 full-course pass re-checks global consistency; reel-level structure_rules (Stage 3) enforce minimum required components on every reel regardless of position |
| **Repetition** | Stage 4 (every-5-reels) checks cross-reel duplication in a bounded window | Stage 5 (module) and Stage 7 (course) catch repetition at larger grains the 5-reel window misses |
| **Hallucination** | Stage 3 per-reel grounding check against linked Source segments | Stage 7 full-course pass re-validates claims; `prohibited_content` and pedagogy rules bias generation toward general practical guidance over invented specifics when ungrounded |
| **Context-growth degradation** | Stage 2's bounded "prior context summary" (not full history) keeps generation cost/quality stable regardless of course length | Orchestrator persists compact per-module summaries, not raw growing transcripts, as it moves forward |

This table is the architectural justification for the 8-stage design — each stage exists to catch a specific failure mode at the smallest scope where it's economically detectable, with wider stages as a safety net for what smaller scopes miss.

---

## 8. Traceability & Observability

- Every Generation Run stores: rules version, brief snapshot, map (with provenance), source refs, and a full Review Log (§4.7) across all 8 stages.
- Given a final DOCX, an admin/dev can reconstruct exactly which reels were rewritten, why, and how many times, without that history ever having been exposed to the course creator.
- This is required for MVP (PRD NFR-6) primarily for internal QA and pipeline tuning, not as an end-user feature.

---

## 9. Technology Considerations (Proposed, non-binding)

This document intentionally avoids locking in application code, but for BUILD_PLAN.md sequencing purposes, the following directions are reasonable and should be confirmed before implementation begins:

- **Backend:** A typed backend service (e.g. Node/TypeScript or Python) capable of running a durable state machine for the Generation Orchestrator (stage persistence, resumability) — a lightweight job/queue mechanism is preferable to a purely synchronous request/response model given multi-stage, potentially long-running generation.
- **Storage:** A relational or document database for Rules, Courses, Briefs, Maps, Sources, Runs, Reels, Review Logs; blob storage for raw uploaded files and generated DOCX files.
- **DOCX generation:** A dedicated DOCX-building library driven by structured formatting rules, rather than string/template concatenation, to keep formatting consistent and testable.
- **LLM access:** Abstracted behind a single generation-provider interface used by stages 1–2 (drafting) and 3–7 (review/critique), so model/provider choice is swappable without pipeline redesign.
- These choices are deferred to BUILD_PLAN.md / implementation kickoff and are not decided by this architecture document.

---

## 10. Explicit Boundaries (What This Architecture Does Not Cover)

- UI visual design / component library choice.
- Exact LLM prompts per stage (belongs in an implementation-time "pipeline prompts" spec, not architecture).
- Authentication/authorization mechanism specifics (assumed internal/trusted-network tool; must still be decided before build).
- Multi-tenancy (single internal org — Rukn — only).
