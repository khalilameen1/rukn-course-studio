# Universal Course Quality Engine

Credit-safe documentation for the domain-aware quality stack.

## CourseQualityContract

Four parts stored on map-preview snapshot and used by gates:

1. **CourseLanguageProfile** — presenter/subject/learner languages, dialect, address form, punctuation policy, which spoken QA to apply (Egyptian vs English).
2. **DomainPedagogyProfile** — domain adapter id, practice/assessment/project types, validators, theory/practice targets (only when the domain needs them).
3. **EvidenceAndRiskProfile** — risk level, freshness, expert review requirements, protected content types.
4. **DeliveryContract** — spoken-only teleprompter targets, hard max lessons/minutes (micro-reel pattern may allow 90+ lessons), block/line targets.

Built by `app/generation/domain_adapters/`.

## Domain Adapters

`language_learning`, `software_and_tools`, `professional_or_income_skill`, `religious_studies`, `academic_or_general_knowledge`, `hands_on_practical_skill`, `high_stakes_health_legal_financial`, `generic`.

Adapters **add** rules; they do not replace global spoken/export rules. Domain literal fixtures (e.g. «عميل بارد») stay in test fixtures / domain ledgers — not injected into every prompt.

## GenerationContextSnapshot

`app/generation/quality/context_snapshot.py`

One v2 contract is shared by map preview, full generation, Writer Test, resume,
finalize, and export. Preview stores its candidate on
`Course.generation_context_snapshot_json`; a real run freezes the same contract
once on `GenerationJob.run_snapshot_json`, after thesis/map approval and before
the first lesson write. Later stages never rewrite it.

`CONFIG_FINGERPRINT` is a full SHA-256 over the canonical standard package,
brief, thesis, selected source hashes, research result hash, market, course type,
language/address profile, quality mode, provider/model, generation settings, and
approved map. Resume and every DOCX export fail closed when the embedded inputs
have been altered or the current output-affecting configuration differs.

The snapshot contains the complete state-key contract (`COURSE_THESIS`, audience
and instructor profiles, capability/coverage/benchmark matrices, all ledgers,
quality findings, active rule pack, stage state, pedagogy adapter, episodic map,
and language rewrite record). Raw standard Markdown, source text, secrets, and
mutable writer results are never copied into it.

## Content Atom Ledger

`app/generation/quality/content_atoms.py`

Core teaching atoms tracked across map compression. Merges must preserve must_cover union; losing a core atom fails compression.

## Coverage Matrix

`app/generation/quality/coverage_matrix.py`

Blocks map approval when promises/skills/checkpoints/theory-ratio/early-practice rules fail for the active contract.

## Terminology / Claims / Protected Spans

- `quality/ledgers.py` — terminology + claim ledgers
- `quality/protected_spans.py` — literal spans survive punctuation policy `protected_examples`

## Teleprompter + Read-aloud

`quality/teleprompter_blocks.py` — meaning-based blocks/lines; layout checks; no Pause labels in DOCX.

## Reviews

- Every-5 and two-module AI reviews: **disabled** (were log-only).
- Module review: **structural** (`quality/module_review.py`) — failing lessons + missing checkpoints → `needs_map_revision`.
- Integrated editorial + local validators remain the per-lesson effect path.

## Export blockers

`export_blockers.py` honors contract delivery hard max, language QA routing, checkpoint policy, and statuses:

`needs_review` | `needs_sources` | `needs_map_revision` | `needs_expert_review`

Human override may raise size caps only — never quality/source failures.

## Credit-safe tests

Set `RUKN_CREDIT_SAFE_TESTS=1`.

- Network sockets blocked (`quality/network_guard.py`)
- Non-fake providers raise `RealProviderBlockedError`
- Capacity test builds 90 synthetic lesson records with FakeProvider disabled for content generation

```bash
cd backend && RUKN_CREDIT_SAFE_TESTS=1 python -m pytest tests/test_universal_quality_engine.py -q
```

## DOCX verify

`quality/docx_verify.py` — reopen exported DOCX, compare against approved text, check metadata leaks and protected spans.

## Canonical map approval

`POST /courses/{id}/map-preview` is the only course-map generation route.
It freezes the selected brief, sources, Source/Web Memory, market, Thesis,
quality settings, compressed map, projects, and Coverage Matrix under one
configuration fingerprint. Full generation requires explicit confirmation of
that fingerprint, consumes the frozen map without rebuilding it, and rejects
any changed input before the worker starts.
