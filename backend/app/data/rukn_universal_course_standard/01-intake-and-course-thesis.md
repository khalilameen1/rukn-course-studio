# 01 INTAKE AND COURSE THESIS

## Required intake model

Resolve the following fields before mapping
Values may come from the user product configuration verified sources or a justified explicit default
Never silently invent a value that changes the promise

```yaml
course_identity:
  working_title:
  domain:
  subdomain:
  course_families: []
  capability_mode_summary: []
  authority_or_risk_overlays: []
  context_overlay_hints: []
  target_market:
  learner_language:
  instruction_language:
  target_performance_language:
  required_registers: []
  listening_or_input_varieties: []
  code_switch_policy:
  spoken_variety:
  address_form:
  instructor_identity:
  instructor_verified_capabilities: []
  instructor_demonstration_capabilities: []
  instructor_verified_experience: []
  prohibited_first_person_claims: []

learner:
  entry_capabilities: []
  missing_foundations: []
  prior_exposure_likely: []
  access_constraints: []
  budget_constraints: []
  device_or_tool_constraints: []
  job_contexts: []
  likely_client_or_stakeholder_contexts: []
  client_access_constraints: []

transformation:
  target_role_or_task:
  observable_end_performance:
  promised_performance_episode:
  quality_level:
  conditions_of_performance:
  performance_environment:
  actors_counterparts_systems_or_materials: []
  incoming_inputs_or_stimuli: []
  time_pressure_or_pacing: []
  likely_variations: []
  quality_signals: []
  common_failure_and_recovery_conditions: []
  required_deliverables: []
  professional_behaviours: []
  real_workflow_start:
  real_workflow_end:
  required_client_or_stakeholder_touchpoints: []
  required_operational_steps: []
  required_perception_or_listening_steps: []
  required_interaction_steps: []
  required_documentation_or_escalation_steps: []
  excluded_outcomes: []

production:
  delivery_modes_allowed: []
  project_policy:
  inter_module_project_policy:
  final_boundary_readiness_policy:
  attachment_self_evidence_policy:
  platform_upload_categories:
    - IMAGE
    - SCREENSHOT
    - FILE
  checkpoint_effort_policy:
  estimated_total_time:
  default_total_time_anchor:
  lesson_duration_policy:
  reel_count_ceiling:
  episodic_progression_policy:
  module_closure_policy:
  instructor_presence_policy:
  export_contract: SINGLE_LECTURER_DOCX
  generated_companion_files: false
  evergreen_script_policy: STRICT
  update_horizon:

evidence:
  supplied_sources: []
  web_research_policy:
  freshness_requirements: []
  authority_requirements: []
  practitioner_reality_requirements: []
  community_source_access_policy:
  style_references: []
```

`platform_upload_categories` defines only which attachment forms the learner can submit
Anything that happens after upload is outside this course authoring standard
The authoring process may verify that a planned attachment is self contained and directly inspectable but it must not design grading evaluator feedback safety routing or post upload behaviour

The default output contract is one DOCX
Do not infer that the user also wants the course map research report workbook or any companion project file

## Universal performance composition

Build a provisional `COURSE_PERFORMANCE_COMPOSITION` `PERFORMANCE_EPISODE_MAP` and `CAPABILITY_ADAPTER_MAP` before the course thesis is accepted
Build `CAPABILITY_MODE_MATRIX` as the validation view
Finalise every material adapter assignment and any `CUSTOM_ADAPTER_REGISTRY` entry after evidence research and before architecture

Do not treat `course_families` capability summaries or user labels as an exhaustive taxonomy or as the architecture controller
They are optional intake and navigation hints only
The capability adapter map is canonical

For every promised performance identify

- The authentic trigger or input
- The learner role
- Any other person system material or environment involved
- What the learner must perceive retrieve decide say create operate teach diagnose or perform
- The required order or interaction pattern
- The quality signals
- The common variation failure correction escalation and completion conditions
- The evidence form that can honestly represent each capability

If the course combines language interaction operational procedure and domain knowledge preserve all four modes
Do not describe it only as a language course or only as a job course

If no listed adapter fits a capability mark a custom adapter requirement then derive and verify it from practitioner performance using the contract in `12-course-family-adapters.md`
Do not accept the custom loop before source evidence supports how capable people actually perform correct vary and complete the capability
Do not ask the user to choose from an incomplete taxonomy when the observable promise is already clear

## Audience model

Build one audience model that avoids both false extremes

### Entry door

The first lesson must not require unintroduced background
It must not announce a remedial course that makes exposed learners feel excluded
Start with a consequential truth decision or demonstration that matters to both groups
Explain foundations at the moment they become necessary

### Exit door

Define the level the course can honestly produce after practice
Use role and task evidence rather than adjectives such as professional complete or advanced

Bad exit definition

`understands marketing`

Valid exit definition

`can receive a local business brief choose a campaign hypothesis build a measurable campaign structure launch within an approved budget diagnose early signals and communicate the next decision without inventing performance`

### Learner access reality

Model what the learner can realistically afford and access in the target market
Do not make essential learning depend on a stack of expensive subscriptions unless that stack is genuinely required for paid work
Do not turn cost awareness into visibly inferior teaching

For every paid dependency decide internally

- Is it essential to the promised professional outcome
- Is a trial free tier open alternative or manual method sufficient for learning
- Does the paid option materially change output quality reliability rights or delivery speed
- Can the principle be learned independently of the vendor

Do not place the current subscription price in the recorded course
Teach how the learner decides whether the live offer is necessary

## Instructor truth profile

Build `INSTRUCTOR_PROFILE` before writing first person speech

```yaml
instructor_profile:
  role:
  verified_qualifications: []
  verified_work_contexts: []
  skills_the_instructor_can_demonstrate: []
  tools_the_instructor_can_use_on_camera: []
  supplied_personal_cases: []
  allowed_first_person_claims: []
  prohibited_or_unverified_claims: []
  preferred_stance:
```

Never invent a client project personal result income failure success anecdote credential years of experience or access to confidential work

When the teaching needs a case but no personal case is supplied use a clearly neutral or internally synthetic case without making the lecturer claim it happened to them

Do not write phrases equivalent to in my experience with my clients or when I did this unless the profile supports the exact claim

The instructor may confidently explain verified domain reasoning without pretending to have lived every example

## Course promise construction

Write the promise as an observable contract

```text
Given INPUTS and CONSTRAINTS
the learner will be able to PERFORM
to QUALITY EVIDENCE
and DELIVER OUTPUTS
in TARGET CONTEXTS
without claiming EXCLUSIONS
```

The promise must include

- A real task or role
- The object being created operated decided or communicated
- The quality evidence
- The target context
- The boundary of the course

Reject a promise based only on knowing understanding exploring discovering or mastering

The promise must also be compatible with an evergreen recorded course
When fulfilling it would require freezing current prices temporary platform rules or frequently changing interface paths into the speech reframe the promise around durable judgement workflow and live verification

## Capability dimensions

Derive capabilities across all dimensions relevant to the course

- Perceive hear read or recognise what matters
- Retrieve or explain the causal or authoritative model
- Choose between options
- Execute the procedure or workflow
- Create or transform an output
- Interact adapt or teach another person where required
- Inspect quality
- Diagnose failure misunderstanding or mismatch
- Correct recover escalate or refer
- Adapt to a new case
- Communicate document close or hand off appropriately

Not every course needs every dimension at equal depth
Use only the dimensions required by the promise but do not omit an invisible perception interaction documentation correction or completion step
A job ready practical promise normally needs the complete real episode rather than the central craft alone

## Course thesis object

Produce a compact thesis before the map

```yaml
thesis:
  learner_start:
  learner_finish:
  central_transformation:
  promised_performance_episode:
  performance_episode_map_summary: []
  course_performance_composition:
  capability_adapter_map_summary: []
  capability_mode_matrix_status:
  custom_adapter_requirements: []
  first_real_task:
  final_integrated_performance:
  final_boundary_integrated_readiness_project:
  final_module_resolution_role:
  final_module_new_promise_critical_capability: false
  proof_of_readiness:
  core_principles: []
  core_workflows: []
  core_interactions_or_application_sequences: []
  recurring_diagnostics: []
  professional_contexts: []
  real_performance_stages: []
  real_workflow_stages: []
  counterpart_client_stakeholder_or_system_touchpoints: []
  client_or_stakeholder_touchpoints: []
  completion_handoff_escalation_or_referral:
  required_foundations: []
  excluded_scope: []
  project_spine: []
  checkpoint_strategy:
  attachment_self_evidence_strategy:
  final_boundary_readiness_strategy:
  module_closure_strategy:
  duration_budget:
  progression_engine:
  earned_peak:
  market_specific_constraints: []
  evergreen_strategy:
  volatile_content_exclusions: []
  single_docx_strategy:
  course_risks: []
```

Each field must change a later mapping or writing decision
Delete decorative thesis prose

## Scope by competence not topic popularity

Include a topic only when it is required to

- Perform the promise
- Prevent a common material failure
- Diagnose or recover from failure
- Adapt the skill to a likely real context
- Deliver or communicate work professionally

Exclude a topic when it is merely adjacent fashionable impressive or easy to teach

If an excluded topic changes the promise make the exclusion visible internally and if necessary in the product description

Do not include a temporary trend merely because practitioners are discussing it during research
Extract the durable mechanism or leave it out

## Depth allocation

Allocate depth according to risk and transfer value

Use more time where

- A wrong mental model poisons later decisions
- The action is difficult to observe or diagnose
- Beginners commonly imitate without understanding
- Real work introduces tradeoffs absent from tutorials
- Failure is costly difficult to reverse or unsafe
- The capability appears in multiple projects

Use less time where

- The information is reference material
- A tool interface exposes the answer clearly
- The detail changes frequently and should be checked live rather than recorded
- The learner can infer it safely from an established model

Remove fast changing reference values from the spoken course rather than moving them into another delivered file

## Theory and practice policy

Theory is allowed only when it improves a later decision execution diagnosis or adaptation
Attach theory to a case demonstration contrast or exercise
Do not create theory modules that postpone all making until the second half

For practical career courses prefer a project anchored structure with repeated execution from early modules
For language or communication courses prefer repeated listening retrieval production and adaptive performance from the first module
For teaching courses prefer modelling elicitation diagnosis correction and transfer rather than explanation alone
For knowledge courses prefer retrieval distinction misconception repair and bounded application rather than catalogue lectures
For analytical courses prefer repeated case decisions rather than long conceptual lectures
For mixed courses switch teaching mode at capability level rather than averaging everything into explanation

## Inter module project policy

Inter module projects are compact action boundaries rather than large portfolio assignments
A standard boundary project makes the learner use the most important completed module capability before later work depends on it
The final boundary project instead integrates the accepted promise critical capability set through one bounded real performance episode

Required policy for every generated course

- One compact task using concepts tools and inputs already taught supplied or created
- One dominant exit capability or the smallest inseparable capability cluster for standard boundaries
- One bounded integrated performance episode covering the accepted promise critical capability set at the final boundary
- One primary output
- One to three uploads only when one is insufficient
- An image screenshot or file according to the capability
- Ten to twenty five minutes of expected active learner effort
- Mandatory design review when expected effort exceeds thirty minutes
- A visible result that represents the action without relying on hidden process
- An internal attachment self evidence check confirming that the submitted bytes contain the decisive result and can be inspected without an external link private state long explanation
- Complete learner instructions inside the lecturer DOCX
- No rubric evaluator prompt score feedback logic platform operation or post upload behaviour in the script
- A short natural closure bridge after every non final module project

Do not introduce a new tool research task external client dependency long asset search or multi day result inside a module project
A checkpoint does not need to look like paid client work in scale
It needs to require the decision or execution that later work cannot safely assume

The final spoken project instruction tells the learner what to do what to produce and what to upload
It stops there

For every course with at least two modules designate the last project before the final module as the compact integrated readiness project
It must reuse prior work or a bounded supplied case and represent most core capabilities plus every promise critical capability that would make the readiness claim false if absent
Keep it inside the same compact effort and upload policy whenever possible
Do not turn it into a large portfolio capstone

The final module may diagnose compare refine transfer package communicate deliver hand off or close this integrated performance
It must not introduce a new promise critical standalone capability whose honest proof would require a project after the final module
Move such a capability earlier or narrow the promise before mapping

## Module closure policy

Every non final module must close after its project with one to three natural spoken sentences

The closure must

- Complete the capability the module delivered
- Expose a real limit changed condition or consequence
- Create an honest need for the following capability

The closure must not

- Say in the next module or equivalent
- Promise a secret reveal surprise or trick
- Withhold anything needed for the current project
- Repeat a standard teaser formula
- Convert the course into a fictional story or drama

The final module resolves rather than teases

## Strict evergreen policy

The course script must not contain exact volatile values that will force routine rerecording

Prohibit

- Current service prices client fee amounts and market rate claims
- Subscription prices plan quotas temporary discounts and free allowances
- Current salaries exchange rates advertising cost benchmarks or platform fees
- Current rankings temporary trends algorithm tricks and mutable statistics
- Fragile interface positions paths and release specific steps
- Current policy limits or thresholds when the skill can be taught through live verification

Use synthetic numbers for method demonstrations when needed
Teach variables and decision logic for pricing cost and budgeting
Teach the learner how to verify a live requirement without speaking its current value

If the promise cannot be fulfilled without a volatile spoken fact narrow or reframe the promise before mapping

## Duration and lesson count

Do not select a lesson count because another successful course used it
Do not use a small count or short runtime as evidence of efficiency

Use approximately 120 spoken minutes as the default planning anchor for a standard course when the product brief provides no stronger constraint
This is an average rather than a required minimum or maximum
A narrow promise may require less
A broad honest practical promise may require more

Estimate from

- Capability graph size
- Real performance episode stage count
- Real workflow stage count when applicable
- Number of distinct practice loops
- Demonstration time including visible action pauses
- Required cases variation failure diagnosis and recovery
- Project instruction and module closure needs
- Product duration constraints

Every standalone teaching reel must be at least 60 spoken seconds and no more than 300 spoken seconds
At approximately 135 spoken words per minute use 135 to 675 useful spoken words only as a rough check because screen action silence and demonstrations change runtime

One lesson must contain one meaningful capability change
Merge lessons with the same outcome
Split a lesson only when it contains independently teachable outcomes incompatible delivery modes or a natural complete phase of a longer demonstration
Never fragment one idea merely to increase reel count
Never merge distinct actions merely to appear concise

There is no default reel count ceiling
A map near 180 reels may be valid when every reel carries a distinct necessary capability change and the total scope requires it
It is never a target
A 30 reel 40 minute map fails when it only names the field while omitting the execution diagnosis correction client reality or delivery needed for the promise

When the map exceeds a product time budget compress duplication before removing essential competence
If essential competence still does not fit narrow the promise
Do not preserve the promise by converting the course into an overview

## Thesis gates

Block mapping when

- The learner finish cannot be observed
- The promise needs undisclosed prerequisites
- The final integrated performance does not represent the promise
- The target market is missing where market conditions affect the skill
- Tool and budget assumptions are unrealistic
- The excluded scope contradicts product messaging
- The intended instructor cannot credibly deliver the required voice or demonstrations
- The script would require unverified first person authority or invented experience
- The course is described as practical while practice is optional or delayed
- A client or job ready promise has no defined start to handoff workflow boundary
- A non business promise has no defined real performance episode from authentic input to completion or recovery
- One course family label is being used to hide multiple required capability modes
- A required capability has no provisional primary adapter or the chosen evidence cannot represent it
- A custom adapter requirement has no research path capable of validating its real performance loop
- A required workflow stage cannot be taught supported or practised before the learner meets it
- A module project cannot produce an image screenshot or file that honestly represents its dominant capability
- A planned attachment cannot pass the internal self evidence check without hidden context external access unseen process unsupported parsing or an evaluator assumption
- The last boundary project cannot compactly represent most core capabilities and every promise critical capability needed for readiness
- The final module introduces a new promise critical standalone capability that has no formal proof before course resolution
- A project requires a separately generated brief workbook or platform guide
- A non final module has no honest closure condition
- Progression depends on artificial suspense entertainment performance or answer withholding rather than accumulating capability
- Course duration or reel count is fixed by a brevity target rather than required competence
- A teaching reel is planned below one minute or above five minutes
- The intended peak is only louder longer or larger rather than more integrated independent and consequential
- The script requires exact prices subscriptions temporary limits current rankings or other fast expiring spoken content
- The requested delivery expects any generated course artefact besides the single lecturer DOCX
