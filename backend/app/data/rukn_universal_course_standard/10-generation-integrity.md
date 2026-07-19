# 10 GENERATION INTEGRITY

## Purpose

Protect the quality standard from being weakened by different generation paths context loss silent cleanup or reviews that do not affect the accepted text

This file governs implementation behaviour rather than course content

## One canonical configuration

Create `CONFIG_FINGERPRINT` from every setting that can change the result

```yaml
config_fingerprint:
  standard_version:
  course_brief_version:
  thesis_version:
  selected_sources:
  research_snapshot:
  market_pack_version:
  benchmark_matrix_version:
  episodic_progression_map_version:
  instructor_profile_version:
  voice_profile_version:
  language_profile:
  spoken_residue_policy_version:
  address_form:
  quality_mode:
  writer_prompt_version:
  reviewer_prompt_version:
  model_and_provider:
  generation_parameters:
  export_contract_version:
```

Attach the fingerprint to map previews writer probes lessons saved drafts final reviews and exports
Warn when artefacts from different fingerprints are compared or combined

## Preview parity

A course map preview must use the same

- Course brief
- Selected sources
- Research policy
- Market pack
- Thesis rules
- Capability requirements
- Project policy
- Hard limits

as full generation

If cost prevents parity label the preview as an estimate and list the omitted influences
Do not present a source free map as the approved map for a source grounded run

## Writer probe parity

The three reel probe must use the same active writer and local review stack as full generation
It must receive the selected source excerpts claim ledger terminology market language profile and phrase rules needed by the chosen lessons

Differences allowed for cost

- No full course map generation when three supplied lesson intents are being tested
- No full course project review
- No whole course semantic duplication scan

Differences must be visible in the fingerprint
Do not treat probe success as full course certification

## Mandatory context pack

Build `ACTIVE_RULE_PACK` for every writer and reviewer call

It must always contain the active minimum needed from

- Runtime contract
- Course thesis
- Audience model
- Capability and lesson semantic contract
- Invisible episodic progression map and the exact adjacent dependency
- Market pack
- Instructor truth profile
- Source authority rules
- Language profile
- Spoken residue policy and protected verbatim register boundaries
- Term ledger entries relevant to the lesson
- Teleprompter contract
- Quality blockers
- Prior accepted lesson dependencies
- Phrase ledger patterns to avoid
- Demonstration and asset requirements relevant to the lesson

Never truncate a mandatory rule midway
When context is tight reduce in this order

1. Repetitive low authority sources
2. Irrelevant source sections
3. Distant accepted lesson prose replaced by summaries
4. Optional examples

Do not remove the thesis language profile term rules or blockers to make space for more source text

Validate `ACTIVE_RULE_PACK` against the required rule identifiers in `11-stage-contracts-and-first-run.md` before every paid writer or reviewer call
If a required identifier is missing stop the call rather than relying on model memory

## Source packing

Retrieve source material by the exact capability and claim needs of the lesson
Do not send the entire source library to every lesson
Do not allow retrieval popularity to replace authority ranking

Pack separately

- Verified facts
- Current values
- Practitioner tradeoffs
- Market evidence
- Voice calibration summary

Keep source labels internal and strip them from the spoken output

## Canonical lesson lifecycle

Use one accepted lifecycle across full generation probe and recovery

1. Build lesson semantics from the approved map
2. Retrieve relevant evidence and terms
3. Write first draft
4. Run deterministic checks
5. Run integrated editorial review
6. Rewrite the identified cause
7. Freeze and compare accepted semantics for every language repair
8. Run spoken variety residue and repair induced repetition checks
9. Rerun checks and review
10. Accept or mark blocked
11. Update ledgers
12. Save the accepted version and its fingerprint

Do not save an unreviewed cleanup as accepted
Do not let a post review heuristic change meaning without rerunning relevant gates

`FINAL_TEXT_ACCEPTED` requires one identical text fingerprint to have passed meaning terminology spoken variety repair induced repetition and teleprompter gates
Any content language or sentence boundary mutation invalidates that state
Rerun the affected gates and continue until the unchanged fingerprint passes all of them together

## Run to completion behaviour

When `RUN_MODE` is `FINAL_FROM_FIRST_REQUEST`

- Keep drafts findings rewrites and reviewer discussions internal
- Continue through course wide adversarial review and rendering
- Return only the accepted deliverable and a concise validation summary
- Surface a blocker only when it requires a user product decision authority or missing external material

Do not interpret this mode as permission to skip reviews
It requires more internal completion before the first visible output

## Review actionability

Every paid or model based review must have one of three explicit outcomes

- `PASS` and preserve the accepted content
- `REWRITE` with findings applied and rechecked
- `STRUCTURAL_CHANGE` with affected map or project nodes reopened

Do not pay for a review whose result is only logged and ignored
Remove a non actionable review call or make its findings part of the canonical lifecycle

## Window reviews

Course level reviews after a group of lessons modules or the full course must inspect relationships local lesson review cannot see

- Semantic duplication
- Progression gaps
- Repeated phrases examples and teaching forms
- Contradictory terms or claims
- Missing dependency
- Broken payoff newly exposed need or capability escalation
- Artificial suspense theatricality or answer withholding introduced across lessons
- Project lesson mismatch
- Tone and address drift
- Course promise drift

When a window review finds a defect it must reopen the smallest affected accepted units apply changes and rerun their local gates plus the window gate

## Silent transformations

Mechanical cleanup may safely

- Remove internal labels
- Normalise whitespace
- Apply approved punctuation policy
- Apply known formatting styles

Mechanical cleanup may not silently

- Change a term
- Replace a market example
- Shorten a causal explanation
- Add a claim
- Merge sentences
- Alter the learner action
- Rewrite a hook or close

Any semantic transformation returns to review

## Persistence and recovery

Save after every accepted lesson
Persist ledgers and the configuration fingerprint with the lesson
Persist `LANGUAGE_REWRITE_RECORD` and the text fingerprint that passed the spoken variety gate

Recovery from saved work must

- Verify fingerprint compatibility
- Reload the canonical thesis map and ledgers
- Resume from the first incomplete or reopened unit
- Rerun whole course gates before export
- Respect all current export blockers

Recovery must not bypass a `BLOCKED` or `needs_review` state
Do not export a mixture of drafts accepted lessons and cleaned variants

## Hard limits

Hard limits must be enforced at the stage where they matter and again at export

- Map size and total duration before lesson generation
- Lesson spoken range by delivery mode after accepted rewrite
- Project presence and placement after map and at export
- Semantic duplication after window reviews and at export
- Teleprompter formatting after rendering

If a human override exists record the exact limit reason and scope in the fingerprint
An override does not disable unrelated quality gates

## Quality mode

Quality modes may change provider cost number of reviewers or research breadth
They may not change the definition of truth natural language term correctness teleprompter validity or export safety

A lower cost preview must be clearly identified and must not overwrite an accepted premium artefact with the same fingerprint

## Output scoring

Numeric scoring is diagnostic
It may help compare attempts and locate weakness
It must not override fatal or serious blockers
Do not optimise prose to a proxy metric at the expense of meaning

## Test strategy

Use deterministic fixtures for

- API and state transitions
- Map schemas
- Saving and recovery
- DOCX structure
- Export blockers
- Duplicate detection
- Context packing rules
- Profile specific spoken residue detection including attached prefix fixtures
- Pre rewrite and post rewrite semantic comparison records
- Invalidation of spoken variety and render passes after any text mutation

Use the smallest paid representative probe for model writing behaviour
Do not generate a complete course to test infrastructure

Before production release run one controlled end to end generation only when all structural tests and representative probes pass

## Runtime acceptance

Block the run when

- Preview and full generation use materially different hidden inputs
- The writer call lacks a mandatory rule pack component
- A lesson call lacks its accepted episodic progression record or receives an incompatible adjacent dependency
- A review finding cannot alter accepted state
- A silent transformation changes meaning
- The final spoken variety gate predates the last accepted text mutation
- A language rewrite lacks its semantic comparison record
- The rendered text fingerprint differs from the text that passed the final spoken variety gate
- Saved lessons lack their fingerprint or ledgers
- Recovery would bypass current blockers
- A lower quality artefact can overwrite a higher quality accepted artefact invisibly
- The exporter enforces weaker limits than the writer contract
- The run returns a first draft before the final stage contract passes
