# 11 STAGE CONTRACTS AND FIRST RUN

## Run mode

Default production mode

```yaml
RUN_MODE: FINAL_FROM_FIRST_REQUEST
USER_VISIBLE_DRAFTS: false
INTERNAL_REWRITE_ALLOWED: true
EXPORT_ONLY_ON_PASS: true
```

The goal is not to make the first prose generation perfect
The goal is to complete every necessary internal correction before the first course file reaches the user

## Required rule identifiers

Every production run must register these identifiers in `ACTIVE_RULE_PACK`

```yaml
required_rules:
  - RUNTIME_CONTRACT
  - COURSE_THESIS_CONTRACT
  - SOURCE_AUTHORITY_FIREWALL
  - MARKET_CALIBRATION
  - COMPETITIVE_BENCHMARK
  - CAPABILITY_ARCHITECTURE
  - INVISIBLE_EPISODIC_PROGRESSION
  - PROJECT_ASSESSMENT
  - LESSON_SEMANTICS
  - NATURAL_SPOKEN_LANGUAGE
  - SPOKEN_VARIETY_INTEGRITY
  - DOMAIN_TERMINOLOGY
  - TELEPROMPTER_LAYOUT
  - TOOL_AI_EVERGREEN
  - QUALITY_BLOCKERS
  - DELIVERY_CONTRACT
  - GENERATION_INTEGRITY
  - INSTRUCTOR_TRUTH
  - DEMONSTRATION_AND_ASSETS
  - COURSE_FAMILY_ADAPTER
```

The implementation may store full files compressed rule objects or versioned prompt modules
It must prove that the semantic content of every required identifier is present
Do not mark a rule loaded merely because its filename exists in storage

## Stage zero input sufficiency

Required input object

```yaml
stage_zero:
  course_brief:
  product_constraints:
  target_market:
  learner_language:
  instructor_profile:
  supplied_sources:
  research_permission:
  reference_material_role:
```

Output exactly one internal state

- `READY`
- `RESEARCH_CAN_RESOLVE`
- `USER_DECISION_REQUIRED`
- `SOURCE_BLOCKED`

Continue automatically for `READY` and `RESEARCH_CAN_RESOLVE`
Ask only the smallest necessary question for `USER_DECISION_REQUIRED`
Do not generate a course for `SOURCE_BLOCKED`

## Stage one thesis contract

Inputs

- Validated stage zero
- Verified facts relevant to the promise
- Market pack
- Instructor profile

Outputs

- Course thesis
- Audience model
- Promise contract
- Excluded scope
- First real task
- Capstone evidence
- Course family adapters
- Selected pedagogy adapter and its mandatory gates
- Risk register

Pass conditions

- Outcome is observable
- No hidden prerequisite
- Instructor can credibly teach and demonstrate the promised scope
- Duration can support the outcome
- Access and cost assumptions are realistic

No map generation before pass

## Stage two evidence contract

Inputs

- Passed thesis
- Supplied sources
- Research results

Outputs

- Source ledger
- Claim ledger
- Term ledger seed
- Market pack
- Benchmark matrix
- Voice profile
- Evidence gaps

Pass conditions

- Material claims have acceptable authority
- Current claims have verification dates
- Market evidence matches the target geography
- Voice material is separated from factual authority
- Transcript errors are not treated as terminology
- Benchmarking detects missing capability rather than supplying copied structure

If evidence is generic shallow promotional or repetitive retrieve stronger material or narrow the promise

## Stage three architecture contract

Inputs

- Passed thesis and evidence
- Capability requirements
- Product duration and project policy

Outputs

- Capability graph
- Coverage matrix
- Course spine
- Episodic progression map
- Module map
- Lesson map
- Project spine
- Demonstration requirements
- Asset requirements

Pass conditions

- Every required capability reaches practice and assessment
- No semantic duplicate outcome
- Useful execution begins early
- Every lesson gives a complete payoff and earns any continuation through a real capability dependency
- Escalation comes from judgement ambiguity integration independence or consequence rather than presenter intensity
- Progression reaches diagnosis adaptation and delivery where promised
- Capstone proves the promise
- Benchmark gaps inside scope are resolved
- Total time is feasible

Do not use an approved reference course to create titles module counts or ordering
Compare its quality characteristics only after this architecture is independently derived

## Stage four project contract

Inputs

- Passed architecture
- Asset availability
- Learner access constraints

Outputs

- Complete module project briefs
- Rubrics
- Submission evidence
- Revision loops
- Portfolio case structure where applicable
- Final capstone brief

Pass conditions

- Projects cannot pass through copying alone
- Every module exit is tested
- Inputs and rights are valid
- Instructions fit spoken project ranges or have a supporting written brief
- The capstone is integrated and independent

## Stage five lesson generation contract

Generate one lesson from its accepted semantic record

Inputs

- Exact lesson map node
- Required capability and dependency
- Accepted episodic link including real tension complete payoff newly exposed need and escalation role
- Relevant verified evidence
- Relevant term ledger entries
- Market and audience context
- Instructor truth limits
- Demonstration and assets
- Phrase ledger
- Language and teleprompter rules

Outputs

- First spoken draft
- Updated claim term and phrase proposals

The writer must not see irrelevant reference course prose
The writer must not invent missing experience examples facts results or assets

## Stage six lesson acceptance contract

Run in order

1. Deterministic validation
2. Domain meaning review
3. Complete payoff and earned continuation review
4. Natural spoken language review
5. Terminology review
6. Hook close and repetition review
7. Teleprompter sentence boundary review
8. Rewrite
9. Spoken variety residue review on the complete rewritten sentence and lesson
10. Pre rewrite and post rewrite semantic comparison for every language repair
11. Phrase ledger check for repair induced repetition
12. Full local recheck

Outputs

- `ACCEPTED`
- `REOPEN_SEMANTICS`
- `REOPEN_MAP`
- `SOURCE_BLOCKED`

Do not save a draft as accepted
After two failed prose rewrites reopen the upstream cause

## Stage seven course wide acceptance contract

After lessons in each module and after the full course inspect

- Capability progression
- Payoff dependency and capability pressure across adjacent lessons
- Absence of theatrical escalation fake stakes artificial cliffhangers and answer withholding
- Cross lesson semantic duplication
- Phrase and hook diversity
- Claim and term consistency
- Project lesson alignment
- Instructor voice and truth consistency
- Theory practice balance appropriate to the family
- Market fit
- Tool independence
- Total duration

Findings must change accepted state when serious
A review that only logs findings is invalid

Then run the independent adversarial passes defined in the quality protocol

After every course wide rewrite run one fresh spoken variety integrity pass over the complete course
This pass must review sentence grammar morphology connectors word order and continuous auditory flow rather than depend on a forbidden word list
Compare every resulting language edit with its accepted semantic record then rerun the affected meaning term sequence repetition and teleprompter gates

## Stage eight delivery contract

Inputs

- Fully accepted course
- Fully accepted projects
- Cleared blockers
- Final ledgers

Actions

1. Export spoken text and allowed headings only
2. Validate content counts and order
3. Validate word ranges including one minute reel floor
4. Validate no metadata or unsupported claims leaked
5. Confirm the exported text fingerprint is the exact version that passed the final spoken variety and semantic preservation gates
6. Validate DOCX package
7. Render every page
8. Inspect every page
9. Reopen and repair any visual or textual defect
10. Rebuild and rerender after any text change

Output

- Final DOCX
- Internal pass report

Only the final DOCX and a concise result summary are user visible unless diagnostic material is requested

## Reference non imitation firewall

An approved reference may influence only abstract quality targets

- Depth
- Signal density
- Naturalness
- Progression strength
- Project seriousness
- Teleprompter readability
- Variation

It may not supply

- New course titles
- Lesson outcomes
- Module count
- Project scenario
- Domain examples
- Hook wording
- Closing wording
- Term choices
- Market assumptions

If a new course resembles the reference structurally without a capability reason reopen architecture

## First run failure prevention

Before returning the final file answer these internal questions with evidence

- What would an experienced practitioner call shallow here
- What would a true beginner fail to execute
- Which sentence sounds translated or generated
- Which sentence is correct on the page but sounds written rather than spoken aloud
- Which connector inflection command question number form or sentence structure belongs to a different register
- Which formal residue is hidden behind an attached Arabic prefix
- Which language repair changed a condition cause contrast sequence emphasis example action or continuation dependency
- Which colloquial connector became a new repeated tic after repair
- Which term would sound strange in the target market
- Which lesson could be deleted without reducing competence
- Which lesson gives only setup instead of a complete payoff
- Which adjacent lessons can be swapped without breaking a real capability dependency
- Which close advertises continuation instead of earning it
- Where an answer is withheld or fragmented for retention
- Where the lecturer sounds like an entertainer actor or reaction personality
- Whether the peak is earned by accumulated capability rather than size noise or duration
- Which two lessons secretly teach the same outcome
- Which project can pass without understanding
- Which claim depends on a vendor or trend
- Which lecturer statement invents authority
- Which visible demonstration cannot actually be filmed
- Which required asset is missing
- Where is the course weaker than a strong accessible alternative inside the same promise
- Does the capstone prove the promised exit level

Any non empty defect answer reopens the relevant stage

## Final return rule

Return a final course on the first user request only when all stages pass

If a user decision is genuinely required return the decision request rather than a compromised course
After the decision continue from saved state without asking the user to repeat prior requirements

Never claim that a stochastic model needs no quality control
Make the quality control internal so the user does not have to conduct the same correction conversation again
