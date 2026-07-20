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
  target_market:
  learner_language:
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

transformation:
  target_role_or_task:
  observable_end_performance:
  quality_level:
  conditions_of_performance:
  required_deliverables: []
  professional_behaviours: []
  excluded_outcomes: []

production:
  delivery_modes_allowed: []
  project_policy:
  estimated_total_time:
  lesson_duration_policy:
  episodic_progression_policy:
  instructor_presence_policy:
  export_contract:
  update_horizon:

evidence:
  supplied_sources: []
  web_research_policy:
  freshness_requirements: []
  authority_requirements: []
  style_references: []
```

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

For every paid dependency decide

- Is it essential to the promised professional outcome
- Is a trial free tier open alternative or manual method sufficient for learning
- Does the paid option materially change output quality reliability rights or delivery speed
- Can the principle be learned independently of the vendor

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

## Capability dimensions

Derive capabilities across all dimensions relevant to the course

- Recognise what matters
- Explain the causal model
- Choose between options
- Execute the workflow
- Inspect quality
- Diagnose failure
- Correct or recover
- Adapt to a new case
- Communicate the decision
- Deliver work professionally

Not every course needs every dimension at equal depth
A job ready practical promise normally needs all ten

## Course thesis object

Produce a compact thesis before the map

```yaml
thesis:
  learner_start:
  learner_finish:
  central_transformation:
  first_real_task:
  capstone_performance:
  proof_of_readiness:
  core_principles: []
  core_workflows: []
  recurring_diagnostics: []
  professional_contexts: []
  required_foundations: []
  excluded_scope: []
  project_spine: []
  progression_engine:
  earned_peak:
  market_specific_constraints: []
  evergreen_strategy:
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
- The detail changes frequently and can be verified when needed
- The learner can infer it safely from an established model

## Theory and practice policy

Theory is allowed only when it improves a later decision execution diagnosis or adaptation
Attach theory to a case demonstration contrast or exercise
Do not create theory modules that postpone all making until the second half

For practical career courses prefer a project anchored structure with repeated execution from early modules
For language or communication courses prefer repeated performance from the first module
For analytical courses prefer repeated case decisions rather than long conceptual lectures

## Duration and lesson count

Do not select a lesson count because another successful course used it

Estimate from

- Capability graph size
- Number of distinct practice loops
- Demonstration time
- Required cases and variation
- Project instruction and feedback needs
- Product duration constraints

One lesson must contain one meaningful capability change
Merge lessons with the same outcome
Split a lesson only when it contains independently teachable outcomes or incompatible delivery modes

When the map exceeds the time budget compress duplication before removing essential competence
If essential competence still does not fit narrow the promise

## Thesis gates

Block mapping when

- The learner finish cannot be observed
- The promise needs undisclosed prerequisites
- The capstone does not prove the promise
- The target market is missing where market conditions affect the skill
- Tool and budget assumptions are unrealistic
- The excluded scope contradicts product messaging
- The intended instructor cannot credibly deliver the required voice or demonstrations
- The script would require unverified first person authority or invented experience
- The course is described as practical while practice is optional or delayed
- Progression depends on artificial suspense entertainment performance or answer withholding rather than accumulating capability
- The intended peak is only louder longer or larger rather than more integrated independent and consequential
