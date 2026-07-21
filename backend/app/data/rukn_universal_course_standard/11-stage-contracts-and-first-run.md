# 11 STAGE CONTRACTS AND FIRST RUN

## Run mode

Default production mode

```yaml
RUN_MODE: FINAL_FROM_FIRST_REQUEST
USER_VISIBLE_DRAFTS: false
INTERNAL_REWRITE_ALLOWED: true
EXPORT_ONLY_ON_PASS: true
USER_VISIBLE_OUTPUT: ONE_CAMERA_READY_DOCX
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
  - PRACTITIONER_REALITY_RESEARCH
  - SOURCE_SUFFICIENCY
  - MARKET_CALIBRATION
  - COMPETITIVE_BENCHMARK
  - REAL_WORKFLOW_COVERAGE
  - PERFORMANCE_EPISODE_MAP
  - UNIVERSAL_CAPABILITY_COMPOSITION
  - CAPABILITY_ADAPTER_MAP
  - CAPABILITY_MODE_MATRIX
  - CUSTOM_ADAPTER_REGISTRY
  - CAPABILITY_ARCHITECTURE
  - COURSE_DURATION_SUFFICIENCY
  - INVISIBLE_EPISODIC_PROGRESSION
  - INTER_MODULE_PROJECT_SCRIPT
  - PROJECT_UPLOAD_RESULT_CLARITY
  - ATTACHMENT_SELF_EVIDENCE
  - FINAL_BOUNDARY_INTEGRATED_READINESS
  - FINAL_MODULE_RESOLUTION
  - PROJECTS_ONLY_BETWEEN_MODULES
  - UNLABELLED_MODULE_CLOSURE
  - LESSON_SEMANTICS
  - NATURAL_SPOKEN_LANGUAGE
  - SPOKEN_VARIETY_INTEGRITY
  - DOMAIN_TERMINOLOGY
  - TELEPROMPTER_LAYOUT
  - TOOL_AI_EVERGREEN
  - EVERGREEN_SPOKEN_CONTENT
  - STRICT_EVERGREEN_VISIBLE_TEXT
  - STRICT_SPOKEN_OUTPUT_FILTER
  - QUALITY_BLOCKERS
  - SOLE_LECTURER_DOCX_DELIVERY
  - GENERATION_INTEGRITY
  - INSTRUCTOR_TRUTH
  - DEMONSTRATION_AND_ASSETS
  - UNIVERSAL_CAPABILITY_ADAPTER_LIBRARY
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
  community_source_access_policy:
  platform_supported_submission_categories:
    - IMAGE
    - SCREENSHOT
    - FILE
  inter_module_project_policy:
    default_active_minutes_min: 10
    default_active_minutes_max: 25
    redesign_review_above_minutes: 30
    upload_count_min: 1
    upload_count_max: 3
    project_after_final_module: false
    final_boundary_project_role: COMPACT_INTEGRATED_READINESS
    final_module_new_promise_critical_capability: false
    attachment_self_evidence_required: true
    generate_evaluator_or_post_upload_logic: false
  final_output_contract: SINGLE_LECTURER_DOCX
  evergreen_spoken_content_required: true
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
- First authentic performance episode
- Provisional performance episode map
- Real performance or workflow start and end boundary
- Provisional course performance composition
- Provisional capability adapter map with primary secondary and overlay assignments
- Custom adapter research requirements
- Inter module project strategy
- Final boundary integrated readiness strategy
- Attachment self evidence strategy
- Final module resolution strategy
- Module bridge strategy
- Evergreen spoken content strategy
- Duration and reel boundary policy
- Final integrated performance strategy
- Compatibility pedagogy adapter view and mandatory gates
- Risk register

Pass conditions

- Outcome is observable
- No hidden prerequisite
- Instructor can credibly teach and demonstrate the promised scope
- Duration can support the outcome without superficial compression or padding
- The platform supports image screenshot and file submissions suitable for the planned projects
- Every planned project can be self contained in the teleprompter DOCX
- Every planned attachment has a viable directly inspectable self evidence form without evaluator design
- The final boundary can compactly represent the promise critical capability set and the final module can resolve without adding a new standalone proof requirement
- Access and cost assumptions are realistic
- The course promise can be taught without rapidly expiring spoken prices fees plan details rankings interface coordinates or temporary limits
- Every promised real situation can be decomposed into observable performance stages and capability units
- No course title or broad family label is being used as a substitute for capability level composition
- Every capability has a provisional primary adapter and any required custom adapter has a viable evidence research path

No map generation before pass

## Stage two evidence contract

Inputs

- Passed thesis
- Supplied sources
- Research results

Outputs

- Source ledger
- Claim ledger
- Practitioner reality pack
- Source sufficiency matrix
- Term ledger seed
- Market pack
- Benchmark matrix
- Voice profile
- Accepted or revised capability adapter map
- Capability adapter evidence status
- Accepted custom adapter registry or explicit absence of custom adapters
- Evidence gaps
- Spoken expiry decisions for unstable claims

Pass conditions

- Material claims have acceptable authority
- Market evidence matches the target geography
- Every core applied capability has sufficient practitioner performance input variation failure correction transfer completion and handoff evidence
- Every primary and material secondary adapter is supported in the target domain rather than inferred from the course title
- Every custom adapter is accepted from evidence or rejected and replaced before architecture
- Official authority and practitioner reality remain separate complementary roles
- The source sufficiency matrix has no material unresolved gap
- Practical saturation is reached by capability adapter and real performance stage rather than source count
- Voice material is separated from factual authority
- Transcript errors are not treated as terminology
- Benchmarking detects missing capability rather than supplying copied structure
- Every volatile current fact is marked for durable reframing or exclusion from the spoken course

A current source may inform the internal decision model
It does not earn the right to place its current price number plan name ranking interface path or temporary limit in the lecturer script

If evidence is generic shallow promotional repetitive or too volatile to support an evergreen course retrieve stronger material reframe the capability or narrow the promise

## Stage three architecture contract

Inputs

- Passed thesis and evidence
- Capability requirements
- Product duration and project policy

Outputs

- Course performance composition
- Performance episode map
- Real performance or workflow trace
- Capability adapter map
- Capability mode matrix
- Custom adapter registry
- Workflow coverage matrix
- Capability graph
- Coverage matrix
- Duration budget
- Course spine
- Episodic progression map
- Module bridge map
- Module map
- Lesson map
- Project spine
- Final boundary readiness record
- Final module resolution contract
- Attachment self evidence plan for every project
- Demonstration requirements
- Asset requirements

Pass conditions

- Every required capability reaches its adapter native modelling perception or retrieval practice correction variation and project proof where needed
- Every required context overlay changes source boundaries teaching practice or evidence where material
- Every custom adapter is accepted and represented in the capability mode matrix
- Every required real performance or workflow action perception phrase response decision check correction completion or handoff is taught supported practised or proved before first use
- The cold start walkthrough contains no missing middle
- No semantic duplicate outcome
- Useful execution begins early
- Every lesson gives a complete payoff and earns any continuation through a real capability dependency
- Every non final module has a natural bridge based on a newly visible real work limit consequence or integration need
- No module bridge says in the next module or uses an equivalent continuation advertisement
- Escalation comes from judgement ambiguity integration independence or consequence rather than presenter intensity
- Progression reaches diagnosis adaptation and delivery where promised
- The last project before the final module compactly proves the integrated promise critical capability set
- The final module introduces no new promise critical standalone capability uses the accepted integrated work adds completion value and resolves without a project after it
- Every project has a viable attachment self evidence form that is directly inspectable without hidden context or evaluator assumptions
- Benchmark gaps inside scope are resolved
- Total time is sufficient for the promise and feasible for production
- Every teaching reel is planned between one and five spoken minutes
- Reel count follows capability need with no arbitrary default ceiling
- No lesson outcome depends on a rapidly expiring spoken fact

Do not use an approved reference course to create titles module counts ordering project scenarios or module closing wording
Compare its quality characteristics only after this architecture is independently derived

## Stage four project contract

Inputs

- Passed architecture
- Learner access constraints
- Platform supported attachment types
- Course supplied inputs already available in the script or approved assets

Outputs

- Complete compact module project design records
- Self contained learner facing spoken project scripts
- Exact attachment type and maximum count for every project
- Required visible result for every attachment
- Attachment self evidence record for every project
- Project progression and prior work reuse decisions
- One compact integrated readiness project at the last boundary before the final module
- One unlabelled module bridge close after every non final project

Do not generate

- Any specification for what happens after the learner uploads the attachment
- Rubrics evaluator prompts scores pass fail thresholds feedback routing retry logic or platform safety operations
- Separate project briefs checklists workbooks or other companion learner material

Pass conditions

- Projects cannot be completed through copying alone
- Every standard module project targets one dominant exit capability or the smallest inseparable cluster
- The final boundary project targets one connected integrated performance episode covering the accepted promise critical capability set
- Every standard project uses attachment evidence native to its dominant adapter and includes only inseparable secondary proof
- The final boundary project uses the smallest attachment set native to its connected promise critical adapter combination
- Expected active effort is ten to twenty five minutes by default and any project above thirty minutes has passed redesign review
- No project depends on a real client external account paid spend public response external approval lucky input or multi day result
- Every project names one to three supported attachment types and the exact visible audible structural or runtime content required
- Every attachment passes the internal self evidence check and can be understood without an external link private dashboard hidden context unseen process or long explanation
- The self evidence check remains an authoring inspectability record and contains no evaluator grading feedback or post upload logic
- The spoken instructions are complete inside the teleprompter DOCX
- The project script contains only learner facing situation task constraint upload and visible result language
- The last project before the final module is the compact integrated readiness proof and its promise critical capability omission list is empty
- The final module uses already practised integrated work and introduces no new promise critical standalone capability
- Every non final project is followed by one to three natural bridge sentences that expose a real later dependency without naming the next module
- The final module has no project after it and no open bridge

## Stage five lesson generation contract

Generate one lesson from its accepted semantic record

Inputs

- Exact lesson map node
- Required capability dependency primary adapter secondary adapters context overlays and learning cycle role
- Accepted custom adapter contract when active
- Accepted episodic link including real tension complete payoff newly exposed need and escalation role
- Relevant verified evidence
- Relevant durable reframes for any unstable source facts
- Relevant term ledger entries
- Market and audience context
- Instructor truth limits
- Demonstration and assets
- Phrase ledger
- Language teleprompter and strict output rules

Outputs

- First spoken draft
- Updated claim term and phrase proposals

The writer must not see irrelevant reference course prose
The writer must not invent missing experience examples facts results assets prices or current market values
The writer must not copy an internal expiry note into the speech

## Stage six lesson acceptance contract

Run in order

1. Deterministic validation
2. Domain meaning review
3. Complete payoff and earned continuation review
4. Evergreen spoken content review
5. Natural spoken language review
6. Terminology review
7. Hook close and repetition review
8. Teleprompter sentence boundary review
9. Rewrite
10. Spoken variety residue review on the complete rewritten sentence and lesson
11. Pre rewrite and post rewrite semantic comparison for every language repair
12. Phrase ledger check for repair induced repetition
13. Strict spoken output filter
14. Full local recheck

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
- Natural module bridge strength at every non final module boundary
- Absence of explicit next module advertising theatrical escalation fake stakes artificial cliffhangers and answer withholding
- Cross lesson semantic duplication
- Phrase hook close and module bridge diversity
- Claim and term consistency
- Project lesson alignment compactness attachment clarity self containment prior work reuse and attachment self evidence
- Final boundary integrated readiness coverage and final module resolution without a new promise critical proof gap
- Absence of rubrics evaluator prompts scores feedback logic platform and post upload operations from learner facing text
- Performance episode and real workflow coverage with absence of a missing middle
- Capability composition integrity adapter fit overlay coverage and accepted custom adapter status
- Practitioner reality coverage and source role integrity
- Instructor voice and truth consistency
- Theory practice feedback correction and transfer balance appropriate to each active capability adapter
- Mixed course composition preserves the native evidence of language interaction workflow teaching perception production analytical technical knowledge physical and other active modes
- Market fit
- Tool independence
- Absence of rapidly expiring spoken prices fees rates plans limits rankings interface locations and current values
- Total duration sufficiency and one to five minute reel compliance

Findings must change accepted state when serious
A review that only logs findings is invalid

Then run the independent adversarial passes defined in the quality protocol

After every course wide rewrite run one fresh spoken variety integrity pass over the complete course
Compare every resulting language edit with its accepted semantic record then rerun the affected meaning term sequence bridge evergreen repetition output filter and teleprompter gates

## Stage eight delivery contract

Inputs

- Fully accepted course
- Fully accepted project scripts
- Cleared blockers
- Final internal ledgers

Actions

1. Export permitted headings lecturer speech and project speech only
2. Validate content counts and order
3. Validate actual or estimated reel runtime including the one minute floor and five minute ceiling
4. Validate every non final module ends with its accepted natural bridge
5. Validate every project instruction names the task attachment type maximum count and visible result
6. Validate the final boundary project matches the accepted compact integrated readiness record and the final module introduces no new promise critical standalone capability
7. Validate no attachment self evidence field rubric evaluator prompt score feedback logic platform operation metadata unsupported claim or volatile value leaked
8. Confirm the exported text fingerprint is the exact version that passed final spoken variety semantic preservation evergreen and output filter gates
9. Validate DOCX package
10. Render every page
11. Inspect every page
12. Reopen and repair any visual or textual defect
13. Rebuild and rerender after any text change

Output

- One final camera ready DOCX

Only the final DOCX is the user visible course artefact
A minimal transfer message may identify the file but must not expose or attach course maps ledgers research generation configuration or internal pass reports

## Reference non imitation firewall

An approved reference may influence only abstract quality targets

- Depth
- Signal density
- Naturalness
- Progression strength
- Project realism proportional effort and attachment clarity
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
- Module bridge wording
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
- Which capability was classified from the course title rather than its observable action
- Which required supporting adapter or context overlay disappeared because the course was treated as one family
- Which unfamiliar capability was reduced to generic explanation instead of receiving an evidence grounded custom adapter
- Which language for work lesson teaches phrases without the role input branch decision documentation or handoff
- Which sales service or call handling lesson uses a memorised script where listening adaptation or case action is required
- Which teaching lesson explains content without eliciting diagnosing correcting and checking transfer
- Which perceptual skill asks for rule recall without close contrasts changed conditions and action on the detected signal
- Which lesson could be deleted without reducing competence
- Which lesson gives only setup instead of a complete payoff
- Which adjacent lessons can be swapped without breaking a real capability dependency
- Which lesson close advertises continuation instead of earning it
- Which non final module ends without a natural forward pull
- Which module bridge says or implies in the next module rather than exposing a real work limit
- Which module bridge withholds the current answer or sounds theatrical
- Where the lecturer sounds like an entertainer actor or reaction personality
- Whether the peak is earned by accumulated capability rather than size noise or duration
- Which two lessons secretly teach the same outcome
- Which project can be completed without understanding
- Which standard project is too large for a progression checkpoint or tests more than the module exit
- Whether the final boundary project integrates every promise critical capability through one bounded performance without becoming an oversized capstone
- Which promise critical capability first appears in the final module after formal proof has ended
- Which project attachment fails to show the required result or requires hidden context external access unseen process unsupported parsing or a long explanation
- Which project instruction omits the exact upload type maximum count or visible content
- Which project depends on a separate unrequested brief or external link
- Where rubric evaluator score feedback attachment self evidence metadata platform or post upload operations leaked into the course
- Which spoken claim depends on a current price rate salary subscription plan quota ranking interface path version or trend
- Which volatile fact can be replaced by a durable decision method or learner supplied current input
- Which lecturer statement invents authority
- Which visible demonstration cannot actually be filmed
- Which required asset is missing
- Where the first real client or professional task reaches an unintroduced action access permission feedback revision delivery or handoff
- Which core capability is supported only by manuals catalogues or ideal examples without practitioner attempts failures and corrections
- Which teaching reel is below one minute above five minutes padded fragmented or compressed for count optics
- Where the course is weaker than a strong accessible alternative inside the same promise
- Whether the final boundary integrated readiness performance proves the promised exit level
- Whether the final module only resolves diagnoses refines transfers packages communicates delivers or closes already practised capability rather than introducing an unproved standalone requirement
- Whether the DOCX contains anything the lecturer will not say

Any non empty defect answer reopens the relevant stage

## Final return rule

Return a final course on the first user request only when all stages pass

If a user decision is genuinely required return the decision request rather than a compromised course
After the decision continue from saved state without asking the user to repeat prior requirements

The production target is one file the instructor can read and record directly
Make all research mapping checking and correction internal so the user does not need to remove machinery from the final script
