# Course Engine Rebuild — Implementation Plan

Status legend: `pending` · `in_progress` · `done` · `blocked`

---

## Phase 1 — Content contracts
**Status:** done

**Files:**
- `backend/app/models/enums.py` — `LessonDeliveryMode`, `AddressForm`, `CourseMixType`, `GenerationJobKind`
- `backend/app/schemas/generation.py` — `CourseThesis`, blueprint fields, `spoken_beats`, `ModuleProject`
- `backend/app/generation/contracts/` — thesis, lesson blueprint, spoken final master
- `backend/app/generation/duration_policy.py` — soft/hard ranges by delivery mode

**Tests:** thesis defaults/hard caps; spoken beats → plain script; metadata forbidden in export text.

---

## Phase 2 — Course Map rebuild + anti-inflation
**Status:** done

**Files:**
- `backend/app/generation/course_map_quality.py` — Premium 120-min floor removed
- `backend/app/generation/map_compression.py` — compression pass + hard max fail
- `backend/app/generation/orchestrator.py` — thesis → map → compress → fail if over hard max
- `backend/app/prompts/build_course_map.md`

**Tests:** 61 lessons fail at hard_max=60; similar lessons merge; no Premium min inflation.

---

## Phase 3 — Module projects + DOCX
**Status:** done

**Files:**
- `backend/app/schemas/generation.py` — `ModuleProject` on plan/final
- `backend/app/services/docx_export.py` — module + graduation projects (not Lesson N); legacy `bridge_project` internal-only

**Tests:** project between modules; no lesson number; bridge text does not leak.

---

## Phase 4 — Creator / Final Master / phrase ledger
**Status:** done

**Files:**
- `backend/app/prompts/write_single_reel.md`
- `backend/app/generation/phrase_ledger.py`
- `backend/app/ai/fake_provider.py` — spoken_beats + unique openers

**Tests:** ledger/diversity path covered via rebuild + FakeProvider e2e.

---

## Phase 5 — Egyptian Arabic + terminology + address form
**Status:** done

**Files:**
- `backend/app/generation/egyptian_arabic_gate.py`
- `backend/app/generation/terminology_map.py`
- Wired into integrated review + export blockers

**Tests:** golden Arabic fixtures; gender/literal/intro failures.

---

## Phase 6 — Knowledge vs spoken style calibration
**Status:** done

**Files:**
- `backend/app/generation/voice_profile.py`
- Source authority firewall preserved; voice profile compact retrieval

---

## Phase 7 — Admin Knowledge packing + research
**Status:** done

**Files:**
- `backend/app/generation/knowledge_packs.py` — token-aware priority packing; mandatory core uncut
- `backend/app/generation/web_research.py` — higher gap-based search budget (not fixed 5)

**Tests:** mandatory core intact.

---

## Phase 8 — Reviews rebuild
**Status:** done

**Files:**
- `backend/app/generation/integrated_editorial_review.py`
- `backend/app/generation/orchestrator.py` — First Draft → checks → Integrated Review → Rewrite (max 2) → Final Master
- Final deterministic checks are authoritative for pass/fail

**Tests:** forbidden-phrase rewrite; FakeProvider e2e; fatal/serious block export.

---

## Phase 9 — Hard quality gates + recovery
**Status:** done

**Files:**
- `backend/app/generation/export_blockers.py`
- `backend/app/services/finalize_saved_job.py` — always run export gates

**Tests:** needs_review blocks DOCX; recovery cannot bypass; finalize fixtures pass gates.

---

## Phase 10 — Teleprompter DOCX formatting
**Status:** done

**Files:**
- `backend/app/services/docx_export.py` — strip punctuation; beat lines; preserve pause blanks
- `backend/app/generation/contracts/spoken_final_master.py`

**Tests:** no punctuation body; no Hook/Loop/JSON/critic leak; blank pause blocks.

---

## Phase 11 — Writer test: 3 reels
**Status:** done

**Files:**
- `backend/app/generation/writer_test.py`
- Routes in `backend/app/routers/generation.py`
- `frontend/src/components/courses/WriterTestPanel.tsx` + API/types + GeneratePanel

**Tests:** exactly 3; rebuild acceptance suite.

---

## Phase 12 — Map preview + cost before full gen
**Status:** done

**Files:**
- `backend/app/generation/map_preview.py` + route
- Frontend GeneratePanel requires map preview confirm before full gen

---

## Phase 13 — Golden fixtures + full suite
**Status:** done

**Files:**
- `backend/tests/golden/arabic_quality_fixtures.py` + tests
- `backend/tests/test_course_engine_rebuild.py`
- FakeProvider tests remain structural (not production QA)

---

## Final verification (this run)

| Check | Command | Result |
|-------|---------|--------|
| Generation cluster | `pytest` orchestrator/docx/rebuild/golden/finalize… | 100 passed |
| Frontend test | `npm test` | 13 passed |
| Frontend build | `NEXT_PUBLIC_API_BASE_URL=… npm run build` | success |
| Frontend lint | `npm run lint` | 4 pre-existing errors (unrelated pages) |
| Full backend pytest | `pytest tests/ -q` | ~736 passed; remaining failures/errors are pre-existing SQLite/admin_knowledge/source suites |
