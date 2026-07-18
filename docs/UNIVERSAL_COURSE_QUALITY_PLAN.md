# Universal Course Quality Engine — Execution Plan

Status: **done** (credit-safe implementation). No real provider / web / full paid generation used.

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | CourseQualityContract + Domain Adapters + GenerationContextSnapshot | done |
| 2 | Content Atom Ledger + Coverage Matrix + compression atom safety | done |
| 3 | Terminology / Claim / Protected Spans + language QA routing | done |
| 4 | Teleprompter blocks + layout checks + DOCX verify helper | done |
| 5 | Disable no-op reviews + export blockers + mutation guard | done |
| 6 | Unify preview/snapshot + API/UI wiring + deprecate generate-map | done |
| 7 | Fixtures, capacity(90), network guard, docs | done |

## Credit safety
- `RUKN_CREDIT_SAFE_TESTS=1` forces FakeProvider and blocks network
- Tests assert zero real provider calls
