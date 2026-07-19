# 09 DELIVERY CONTRACT AND TRANSFER

## Final learner facing deliverable

Unless the product brief says otherwise export one DOCX containing

- Course title
- Optional short course subtitle
- Module headings
- Reel headings
- Lecturer spoken text
- Module project headings and spoken project instructions between modules
- Capstone heading and spoken instructions at the end

Do not export internal planning review or research material into this document

## Spoken continuity

Within each module the lecturer text flows lesson by lesson without production commentary
Formal project boundaries separate modules

Do not insert

- Learning objectives as administrative bullets
- Lesson summaries that the lecturer will not say
- Recap pages
- Source pages
- Visual plans
- Reviewer reports
- Estimated timing
- Hook or loop labels
- Tension payoff escalation or episodic progression labels
- Camera notes
- Screen notes
- Alternative takes

If the lecturer must say an instruction write it as natural speech
If production needs an instruction keep it internal

## DOCX formatting contract

Use a simple stable hierarchy

- Right to left document direction for Arabic body
- One consistent readable Arabic font
- Course title clearly distinct
- Module headings clearly distinct
- Reel headings visible but not oversized
- Project headings visually distinct from lessons
- Spoken paragraphs visually separated without excessive blank space
- No automatic numbering in spoken body
- No decorative punctuation
- No headers footers watermarks or tables unless explicitly requested

The document is a teleprompter source not a designed workbook

## Final document verification

Perform all checks

1. Validate the DOCX archive and XML parts
2. Extract the visible text and compare against accepted lesson content
3. Verify module reel and project counts against the approved map
4. Verify no lesson or project is missing truncated or duplicated
5. Render every page
6. Inspect every rendered page visually
7. Rerun text gates after any formatting edit
8. Confirm the rendered text is the exact version that passed the final spoken variety and semantic preservation gates

Do not deliver a DOCX that has not been rendered
Any language or text edit invalidates the prior render and requires extraction comparison rendering and visual inspection again

## Internal companion artefacts

Preserve outside the learner DOCX

- Course thesis
- Market pack
- Capability graph
- Coverage matrix
- Episodic progression map
- Benchmark matrix
- Source and claim ledgers
- Term ledger
- Lesson and phrase ledgers
- Language rewrite records and final spoken variety findings
- Project rubrics
- Demonstration ledger
- Asset ledger and supporting project briefs
- Quality findings and resolutions
- Current value update triggers

These artefacts allow a later model run to revise the course without rediscovering the reasoning

## Generation handoff package

A reusable course generation package contains

```yaml
handoff:
  standard_version:
  course_brief:
  course_thesis:
  language_profile:
  market_pack:
  capability_graph:
  coverage_matrix:
  episodic_progression_map:
  benchmark_matrix:
  source_ledger:
  term_ledger:
  instructor_profile:
  project_spine:
  course_map:
  demonstration_ledger:
  asset_ledger:
  phrase_ledger:
  language_rewrite_record:
  spoken_variety_gate_text_fingerprint:
  rendered_text_fingerprint:
  unresolved_findings: []
```

Never hand off only the prose when later revisions may change the map
Never hand off a style sample without its authority limits

## Reference course use

When an approved course is supplied as a reference

Use it to calibrate

- Signal density
- Depth per lesson
- Natural lecturer stance
- Visual sentence organisation
- Project seriousness
- Progression from foundation to professional delivery
- Variety of openings closes and teaching forms

Do not infer universal defaults for

- Lesson count
- Module count
- Project length
- Tool mix
- Topic order
- Domain terminology
- Market examples
- Theory practice ratio
- Exact reel duration

The new course must still pass its own thesis capability market source and project gates

## Domain transfer protocol

For every new course

1. Reset domain facts terminology examples market assumptions and tool choices
2. Retain this standard and its quality gates
3. Build a new thesis and capability graph
4. Research the new domain using the source firewall
5. Select the correct course family adapters
6. Design a new project spine
7. Validate three representative lessons if the writer configuration is unproven
8. Generate and review the full course

Do not preserve content from the previous domain in hidden context
Do not use design and marketing examples in a programming language or religious course merely because they existed in the reference

## Version and provenance

Record

- Standard version
- Course version
- Generation date
- Market verification date
- Source versions when relevant
- Tool or platform versions for unstable demonstrations
- Human overrides
- Quality gate results

Do not expose this metadata in the teleprompter unless requested

## Final machine acceptance checklist

Return `PASS` only when every statement is true

```yaml
acceptance:
  promise_is_observable: true
  audience_has_no_hidden_prerequisites: true
  market_pack_is_sufficient: true
  competitive_benchmark_is_complete: true
  facts_are_authoritative_and_current: true
  capability_graph_is_covered: true
  course_has_real_progression: true
  lessons_are_high_signal: true
  terminology_is_domain_native: true
  speech_is_natural_in_target_variety: true
  spoken_variety_residue_gate_passed: true
  language_rewrites_preserved_semantics: true
  auditory_transition_repetition_passed: true
  openings_and_closes_are_not_formulaic: true
  semantic_duplicates_are_zero: true
  project_gates_prove_module_outcomes: true
  capstone_proves_the_course_promise: true
  tool_teaching_is_transferable: true
  learner_cost_assumptions_are_realistic: true
  instructor_claims_are_verified: true
  demonstrations_are_executable: true
  required_assets_are_ready: true
  no_material_claim_is_unsupported: true
  spoken_body_contains_no_internal_metadata: true
  teleprompter_sentences_are_visually_complete: true
  docx_is_valid: true
  render_matches_final_text_version: true
  every_page_was_rendered_and_inspected: true
  fatal_findings_are_zero: true
  serious_findings_are_zero: true
  first_user_visible_output_is_post_review: true
```

If a statement is false return `BLOCKED` with the exact finding and repair layer
Do not downgrade a blocker to deliver on time

## Non guarantee

This standard can enforce a strong evidence based production process
It cannot guarantee virality senior mastery employment revenue or performance without learner practice instructor delivery feedback market conditions and real execution

Never replace an honest course promise with an unprovable marketing guarantee
