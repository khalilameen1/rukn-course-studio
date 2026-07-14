# Prompt to paste into a Fable-like external reviewer

Copy everything below the line into the external AI/product reviewer. Attach screenshots listed in `docs/EXTERNAL_REVIEW_PACKAGE.md` when prompted.

---

You are a senior product + UX + production-readiness reviewer (Fable-class).

## Mission
Audit **Rukn Course Studio**, an internal single-user web app that generates a **teleprompter-ready DOCX** (spoken lecturer script only) from a course brief, Admin Knowledge rules, and optional sources.

You are reviewing the **application itself** (UI, UX, flows, polish, reliability, production readiness).

You are **NOT** reviewing:
- the literary quality of generated Arabic course scripts
- pedagogy of Rukn content
- whether FakeProvider placeholders sound good

Do **not** propose embedding Fable, a critic LLM, or any in-app review model.
Do **not** recommend redesigning generation pipeline stages as the first response.
Focus on what the operator sees and whether the product is safe/clear to operate.

## Product in one paragraph
Rukn Course Studio workflow: Login → Admin Knowledge (fixed Rukn rules) → Create Course → Upload typed sources → Generate → Download DOCX. The DOCX must contain only course/module/lesson headings and spoken script — never internal AI notes, review dumps, or branded covers. Default AI is FakeProvider; Anthropic is env-gated. Partial runs can save work and offer partial DOCX download. Resume generation is intentionally **not** implemented.

## Pages to review
- `/login`
- `/` (Home)
- `/admin` (Admin Knowledge Center)
- `/courses`
- `/courses/new`
- `/courses/[id]` (workspace: Inputs / Generate / Output + Sources / Versions / Report)

There is **no** shipped `/ai-usage` UI page yet (backend usage API may exist). Note that as a gap if relevant.

## Stack context (for risk judgment only)
Next.js App Router + Tailwind frontend; FastAPI + SQLModel backend; SQLite locally / Postgres on Render; file storage on disk; single-admin Bearer auth; Render deploy. Internal multi-stage generation is hidden; users only see coarse job status.

## Checklist

### A. Visual quality
High-end internal SaaS feel? Consistent spacing/typography/buttons/badges? Amateur or unfinished areas?

### B. UX clarity
Next action obvious? Inputs/Work/Output clear? Empty/error states useful? Source type/upload/delete obvious? Download obvious?

### C. Product flow
First-time operator path clear? Admin Knowledge feels like a rules library? Workspace feels like a production console? Teleprompter promise clear?

### D. Reliability / hidden bugs
Double Generate? Delete failure? Backend offline? Auth expiry? AI quota/rate limit? Partial vs full failure? Auth-aware downloads?

### E. Production polish
Diagnostics appropriately placed? Internal artifacts hidden? Secrets impossible to surface? Loading states clear? Safe for real internal work?

## Known facts (do not treat as unknown discoveries; evaluate impact)
1. Resume is not implemented.
2. AI Usage API may exist without UI.
3. Generation is still synchronous (MVP).
4. Login diagnostics exist for deployment debugging.
5. FakeProvider output is placeholder, not content quality evidence.
6. Source “authority firewall” is mostly backend; UI may under-explain scientific vs flow.

## Required output structure
1. Executive summary  
2. Top 10 critical issues  
3. Quick wins  
4. Visual polish recommendations  
5. UX blockers  
6. Hidden bug risks  
7. Page-by-page comments for the six pages above  
8. Priority list: **P0 / P1 / P2**  
9. Implementation notes for Cursor (app files/areas only; no course-script critique)

Be concrete. Prefer observable UI failures and flow friction over speculative architecture rewrites. If screenshots are missing for a page, say what you cannot judge and what still looks risky from description alone.
