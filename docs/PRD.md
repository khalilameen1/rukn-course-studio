# Product Requirements Document (PRD)

## Product: Rukn Course Studio

**Status:** Draft v1.0 — Documentation & Architecture Phase
**Owner:** Rukn (Internal Tool)
**Last Updated:** 2026-07-13

---

## 1. Summary

Rukn Course Studio is an **internal application** used by Rukn staff to produce complete, ready-to-deliver **DOCX course documents**. It is not a chatbot, not a conversational assistant, and not a general-purpose content generator. It is a **structured production system**: given a set of fixed organizational rules, a course brief, and optional source material, it deterministically produces one artifact — a finished course DOCX file.

The end user (an internal course creator/reviewer) interacts with three simple surfaces — an admin rules page, a course creation page, and a source upload page — and receives exactly one output: **the final DOCX**. All intermediate generation activity (reel-by-reel drafting, silent reviews, rebuilds) is an internal implementation detail and must never be surfaced as the primary deliverable, though it must be logged for debugging/audit purposes.

---

## 2. Problem Statement

Rukn produces structured practical-skill courses composed of modules and "reels" (short, focused instructional units). Producing these manually is slow and inconsistent. Naively generating an entire course in one LLM pass causes three recurring failure modes:

1. **Laziness** — later modules/reels are thinner, vaguer, or skipped in detail as context grows.
2. **Repetition** — the same explanations, examples, or phrasing recur across reels/modules because there's no memory of what was already said.
3. **Hallucination** — invented facts, invented steps, or invented terminology not grounded in Rukn's rules or the provided course brief/sources.

The system solves these by generating **incrementally** (reel by reel), applying an independent bounded review/rewrite to every lesson, then enforcing deterministic checks at lesson, module, adjacent-module, and whole-course scope before export.

---

## 3. Goals

- Produce a complete, well-structured DOCX course from minimal user input (a course brief).
- Guarantee consistency with Rukn's fixed rules (tone, structure, pedagogy, formatting, compliance constraints) on every course, every time.
- Allow optional grounding in user-supplied source material (DOCX/PDF/TXT/MD/transcript) to reduce hallucination and increase specificity.
- Allow an optional manual course map so power users can dictate structure directly instead of relying on auto-generated structure.
- Internally catch and correct laziness/repetition/hallucination via layered review before the user ever sees output.
- Keep the user-facing product surface minimal: Admin Rules, Create Course, Upload Sources, Generate → Download DOCX.

## 4. Non-Goals (MVP)

- Not a chatbot / conversational interface. No turn-by-turn back-and-forth authoring.
- Not a generic content generator for arbitrary content types (blog posts, marketing copy, etc.).
- Not supporting course types beyond **practical skill courses** in MVP (e.g. no academic/theory-heavy course templates yet).
- Not exposing reel-by-reel intermediate drafts to the end user as a deliverable (internal logs/debug views for admins/devs are fine, but not part of the core UX).
- No multi-user real-time collaboration.
- No in-app DOCX editing after generation (regeneration, not editing, is the correction mechanism in MVP).
- No support for video/audio source ingestion beyond a plain transcript text file.
- No public/external-facing access — internal tool only.

---

## 5. Users & Roles

| Role | Description | Capabilities |
|---|---|---|
| **Admin** | Maintains Rukn's fixed institutional knowledge/rules | CRUD on Rukn Rules (tone, structure templates, pedagogy standards, compliance/brand constraints, glossary, reel/module conventions) |
| **Course Creator** | Internal staff producing a course | Creates course briefs, uploads optional sources, optionally supplies a manual course map, triggers generation, downloads final DOCX |
| **(Implicit) System/Pipeline** | Not a human role | Executes the internal generation pipeline; not directly operated by a user beyond triggering "Generate" |

There is no end-learner-facing role in this product — the DOCX itself is later distributed to learners outside this system.

---

## 6. Core Concepts & Data Model (Conceptual)

- **Rukn Rules (Admin-managed, fixed per generation run):** The non-negotiable institutional knowledge that governs every course — house style, tone of voice, required course/module/reel structure, pedagogical patterns for "practical skill" courses, formatting/branding rules, prohibited content, glossary/terminology standards. Versioned; a course generation run pins to one rule version.
- **Course Brief:** User-entered input describing the course to be created — title, target audience, skill outcome(s), constraints, desired length/scope, any special instructions. This is the primary creative input.
- **Source(s) (optional):** Reference material uploaded by the user to ground generation — DOCX, PDF, TXT, MD, or transcript text. Used for factual grounding, not verbatim copying.
- **Course Map (optional, manual or generated):** The structural skeleton of the course: modules → reels, each reel with a working title/objective. If the user supplies one, the system uses it as-is (subject to Rukn structural rules validation). If not, the system generates one from the brief + sources + rules.
- **Reel:** The atomic content unit — a short, focused instructional segment within a module. The generation pipeline's unit of work.
- **Module:** An ordered group of reels covering a cohesive sub-skill or topic.
- **Course:** An ordered group of modules, with front matter (title, intro, objectives) and back matter (summary, next steps) per Rukn conventions.
- **Generation Run:** One execution of the pipeline for a given course, brief, sources, map, and rule version — produces one final DOCX (plus internal logs).

---

## 7. Functional Requirements

### 7.1 Admin Page (Fixed Rukn Rules)

- FR-1: Admin can view, create, edit, and version the fixed rule set (structure templates, tone/style guide, pedagogy rules for practical-skill courses, formatting/branding rules, prohibited content list, glossary).
- FR-2: Rule changes do not retroactively alter already-generated courses; only new generation runs pick up the latest active rule version.
- FR-3: Rules must be structured (not just free text) enough that the generation pipeline can programmatically reference specific rule sections (e.g., "reel length," "reel structure," "module intro pattern") — see ARCHITECTURE.md for schema approach.

### 7.2 Course Creation Page

- FR-4: User can create a new course by entering a course brief (title, audience, skill outcomes, scope/length guidance, special instructions).
- FR-5: User can optionally attach a manual course map (structured input: modules → reels with titles/objectives) instead of relying on auto-generated structure.
- FR-6: User can optionally link previously uploaded sources to the course.
- FR-7: User can trigger generation once brief (and optionally map/sources) are ready.
- FR-8: User can view generation status (queued / building map / generating / reviewing / exporting / done / failed) without seeing raw reel content.
- FR-9: On completion, user can download the final DOCX.
- FR-10: On failure, user sees a clear, actionable error state (not a raw stack trace) and can retry.

### 7.3 Source Upload Page

- FR-11: User can upload one or more source files per course: DOCX, PDF, TXT, MD, or transcript text.
- FR-12: System extracts and stores normalized text content per source for downstream use (see ARCHITECTURE.md ingestion pipeline).
- FR-13: User can remove/replace sources before generation is triggered; sources are locked once a generation run starts.
- FR-14: Unsupported file types or unreadable/corrupt files are rejected with a clear error at upload time, not at generation time.

### 7.4 Generation & Export

- FR-15: The system builds or validates a course map before content generation begins (see pipeline stage 1).
- FR-16: The system generates content reel by reel internally (pipeline stage 2), never generating the whole course in a single pass.
- FR-17: The system performs an effectful independent review/rewrite after each reel and deterministic blocking review at module, adjacent-module, and whole-course scope. A final review action must change its target or block export. None of these intermediate states are delivered as product output.
- FR-18: Only after the final review/rebuild pass does the system assemble and export the final DOCX.
- FR-19: The user-visible output of a successful generation run is exactly one DOCX file, matching Rukn's formatting/branding rules.
- FR-20: Internal generation logs (per-reel review notes, revision counts, flags raised) are retained for admin/debug purposes but are not part of the user-facing deliverable.

---

## 8. Key Non-Functional Requirements

- **NFR-1 Consistency:** Every generated course must comply with the currently active Rukn rule set (structure, tone, formatting) without manual correction in the common case.
- **NFR-2 Anti-hallucination:** Generated content must not introduce facts/claims contradicting supplied sources, and should avoid fabricating specifics when no source supports them (prefer general/practical guidance framed appropriately over invented specifics).
- **NFR-3 Anti-repetition:** No near-duplicate explanations, examples, or phrasing patterns across reels/modules within one course.
- **NFR-4 Anti-laziness/degradation:** Later modules must not be systematically shorter, vaguer, or less detailed than earlier ones purely due to context growth; review stages must actively check for this.
- **NFR-5 Opacity of process:** The user-facing UI must never require the user to read, approve, or wade through reel-by-reel drafts to get their course. Status must be expressed at a coarse, human-friendly grain.
- **NFR-6 Determinism/Traceability:** Every generation run must be reproducible/traceable — which rule version, brief, sources, and map produced which output — for debugging and internal QA.
- **NFR-7 Reasonable latency:** Because generation is incremental with multiple review passes, the system must communicate progress (status, not content) so the tool doesn't feel broken during longer generation runs.
- **NFR-8 Internal-only access:** No externally exposed endpoints beyond what's needed for Rukn staff; this is an internal tool, not a public product.

---

## 9. MVP Scope (Explicit)

**In scope:**
- Practical skill courses only (one course "type"/template family).
- Optional sources: DOCX, PDF, TXT, MD, transcript text.
- Optional manual course map.
- Admin page for fixed Rukn rules.
- Course creation page.
- Source upload page.
- Final DOCX generation/export.
- The internal effectful generation pipeline described in ARCHITECTURE.md.

**Explicitly out of scope for MVP** (see Non-Goals): other course types, chat-style interaction, reel-level user editing, multi-format export (PPT, HTML, etc.), collaboration features, video/audio ingestion, in-place DOCX editing.

---

## 10. Success Criteria

- A course creator can go from "course brief only" to "final DOCX" without ever needing to read or approve intermediate content.
- Spot-checking generated courses shows no reel that is a near-duplicate of another reel in the same course.
- Spot-checking shows no fabricated specifics that contradict or invent beyond supplied sources.
- Module 8 of a 10-module course is not measurably thinner/lower-effort than Module 1, per review-stage sampling.
- Every generated DOCX conforms to Rukn's current structural/formatting rules without manual fixups in the majority of runs.
- Admins can change fixed rules without needing a code deployment.

---

## 11. Open Questions (to resolve before/while building)

- What is the canonical schema for "Rukn Rules" (see ARCHITECTURE.md proposal) — how granular do structure rules need to be for programmatic enforcement?
- What is the maximum practical course size (modules × reels) the pipeline needs to support in MVP, for cost/latency planning?
- What defines a "practical skill course" template precisely (module/reel patterns, required sections like "practice exercise," "recap," etc.)?
- What is the retry/failure policy when a review stage repeatedly rejects a reel/module (max retries before flagging for human intervention)?
- Who can view internal generation logs — admins only, or also the course creator?
