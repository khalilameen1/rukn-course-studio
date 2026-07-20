# 03 CAPABILITY MAP AND COURSE ARCHITECTURE

## Backward design

Begin with the end performance and work backward

1. What must the learner deliver or perform
2. What decisions create a good result
3. What execution skills implement those decisions
4. What quality signals expose weakness
5. What failures are common and how are they diagnosed
6. What foundations make those judgements possible
7. What practice sequence builds independence

Do not begin with a table of contents from a book a tool menu or popular video titles

## Capability graph

Represent the target competence as connected nodes

```yaml
- capability_id:
  observable_action:
  quality_evidence:
  prerequisites: []
  misconceptions: []
  failure_modes: []
  practice_required:
  transfer_contexts: []
  professional_use:
  course_locations: []
```

Every required capability must appear in at least one lesson and one practice opportunity
High risk capabilities require repeated practice in different contexts

## Coverage matrix

Build a matrix before accepting the map

Rows are required capabilities
Columns are learning functions

- Introduced
- Explained
- Demonstrated or modelled
- Practised
- Assessed
- Diagnosed
- Reused
- Delivered professionally

A topic mention counts as none of these unless it fulfils the function
The matrix must show a path from exposure to independent performance

## Course spine

Choose a spine that matches the skill

Possible spines include

- One artefact evolving from rough to professional
- One workflow repeated with increasing complexity
- A sequence of real cases with new constraints
- A role simulation from intake to delivery
- A language performance moving from controlled to spontaneous
- A system built incrementally then debugged and deployed
- A diagnostic framework applied to increasingly ambiguous evidence

Prefer a spine that makes progress visible and creates usable outputs
Do not create a sequence that feels like unrelated tips

## Invisible episodic progression map

Treat short drama as a structural analogy only
Do not turn the course into a fictional story a performance show or a repeated content formula

Build `EPISODIC_PROGRESSION_MAP` from the capability graph and course spine

```yaml
episodic_progression:
  opening_dislocation:
  capability_accumulation: []
  module_turns: []
  project_proofs: []
  earned_peak:
  final_resolution:
  lesson_links:
    - lesson_id:
      real_tension:
      resolved_now:
      learner_payoff:
      retained_capability:
      newly_exposed_problem:
      why_next_is_needed:
      escalation_type:
```

`real_tension` comes from the work itself

- Two plausible choices with different consequences
- A result that looks acceptable but fails inspection
- A constraint that reverses the obvious answer
- Missing information that changes the decision
- A failure whose cause is not where the learner expects
- A capability that works in one context but breaks in another
- Increasing independence ambiguity accountability or integration

Every lesson must pay off its own central question before creating continuation
The next need must be earned by the consequence limit or application of what was just learned
Never leave the current answer incomplete merely to preserve retention

The dramatic curve is capability pressure not performance intensity
Escalate through harder judgement wider integration more realistic constraints less guidance and stronger evidence requirements
Do not escalate through louder language larger claims faster editing fake danger or constant surprise

The progression should disappear from the spoken surface
If the learner can hear the content scaffolding repeatedly the structure is too explicit
If adjacent lessons that claim a dependency can be swapped without changing learning causality inspect the link and reorder merge or rewrite the map
Some capabilities are genuinely parallel
When that is true order them by cognitive load reuse and project need and do not invent a false dependency or cliffhanger

Do not force one beat sheet across domains
A language course may escalate spontaneity
A programming course may escalate system interaction and debugging uncertainty
A sales course may escalate objection ambiguity and live pressure
A production course may escalate judgement integration and delivery constraints

## Module contract

Each module must have

```yaml
module:
  entry_state:
  exit_capability:
  professional_reason:
  required_lessons: []
  project_gate:
  capabilities_reused: []
  resolved_module_problem:
  newly_exposed_limit:
  next_dependency:
```

A module is valid when its project proves the exit capability and creates a necessary foundation for later work
Modules do not need equal lesson counts or equal duration

## Progression curve

Build an intentional curve

### Orientation through consequence

Reveal how the field actually works and what controls quality
Give the learner a useful action early
Do not spend the opening on greetings biography course logistics or generic motivation

### Foundation in use

Teach the smallest foundations needed to execute a meaningful task
Avoid encyclopaedic preliminaries

### Controlled execution

The learner performs with clear constraints and visible success criteria

### Variation and tradeoffs

Introduce cases where the same rule cannot be applied mechanically
Teach judgement and competing priorities

### Diagnosis and recovery

The learner finds why a result failed and repairs it

### Integrated professional performance

The learner handles a realistic brief case or problem through delivery

### Peak

The capstone requires synthesis and independent decisions
It must not be a larger copy of the first exercise

## Lesson map contract

Every lesson map entry must contain

```yaml
lesson:
  lesson_id:
  working_title:
  capability_change:
  non_obvious_value:
  misconception_or_risk:
  evidence_or_demonstration:
  learner_action:
  boundary_or_tradeoff:
  real_tension:
  lesson_payoff:
  earned_next_need:
  escalation_role:
  dependency_from_previous:
  dependency_to_next:
  delivery_mode:
  estimated_spoken_time:
  project_link:
  demonstration_required:
  asset_requirements: []
```

Reject map entries whose outcome is merely learn about know understand or introduction to
Use an observable verb and quality condition

## One reel one meaningful change

A reel must be narrow enough to hold one coherent change and deep enough to justify its existence

Merge reels when

- They produce the same learner decision
- One is only setup for the other
- Each would be shallow alone
- Their examples and explanations substantially overlap

Split a reel when

- It contains separate independent actions
- It combines a mental model and a long screen execution that need different delivery modes
- It requires multiple practice cycles
- One part can fail without the other

Do not split content to reach a lesson count
Do not merge content merely to appear concise

## Independent value and sequence value

Each reel should create a complete useful thought that can stand alone when shared
It must also occupy a necessary place in the sequence

A standalone reel still needs prior terms introduced within the reel or phrased accessibly
A sequential reel must not depend on phrases such as as we said without restating the minimum needed premise

Do not repeat a whole prior lesson in the opening to create continuity
Use a short causal dependency

The standalone payoff and the sequence need must both be true
A reel that only sets up the next reel is incomplete
A reel that gives value but could sit anywhere despite claiming a dependency has weak sequence architecture
A genuinely parallel lesson may close quietly without forcing a loop

## High signal mapping

At map stage label the source of value for every reel

- Counterintuitive correction
- Diagnostic test
- Decision rule
- Causal mental model
- Demonstrated transformation
- Failure analysis
- Tradeoff boundary
- Professional shortcut with conditions
- Comparison that changes choice
- Workflow step whose omission causes a material failure
- Adaptation to a real context

If a lesson has no source of value it is probably filler or reference material
Reference material may belong in a supporting asset rather than a reel

## Surface level detector

Reject or deepen a planned lesson when

- A person outside the field already knows the conclusion
- The title fully contains the lesson value
- The advice is true but gives no decision or execution method
- The lesson could apply unchanged to every profession
- It says quality clarity consistency testing research or strategy are important without showing how
- It offers a slogan where the learner needs a model
- It repeats common social media advice without adding conditions evidence or diagnosis

Deepen using one or more of

- Why the obvious advice fails
- What evidence changes the decision
- A before and after decision path
- A real constraint
- A counterexample
- A failure signature
- A boundary where the rule reverses
- A test the learner can run

## Practical completeness

For a job oriented course inspect the map for these often omitted layers

- Intake or brief reading
- Setup and environment
- Foundational controls
- Execution workflow
- Quality inspection
- Error recovery
- Variations and edge cases
- Time and cost judgement
- File or information organisation
- Collaboration and feedback
- Delivery and handoff
- Portfolio or proof of work
- First realistic job context

Include only what the promise needs but do not call a course job ready while omitting the work around the central craft

## Demonstration plan

Create an internal demonstration record for every screen physical live language or artefact based lesson

```yaml
demonstration:
  lesson_id:
  learner_must_see:
  start_state:
  actions_visible: []
  decisions_explained: []
  failure_or_contrast_shown:
  end_state:
  verification_shown:
  required_assets: []
  estimated_visual_time:
```

The spoken script and demonstration must describe the same sequence
Do not export the demonstration record into the lecturer DOCX

If a meaningful claim depends on a visible difference the plan must actually show that difference
If an interface action changes frequently teach the stable intent and verify the current demonstration before filming

## Asset readiness

Maintain `ASSET_LEDGER` for files data examples briefs starter projects target outputs code repositories recordings and licensed media required by lessons or projects

```yaml
- asset_id:
  purpose:
  course_locations: []
  source:
  rights_or_privacy_status:
  required_format:
  start_state:
  expected_end_state:
  availability:
  blocker_if_missing:
```

A course is not ready for immediate filming or practice when a required demonstration asset is missing ambiguous inaccessible or rights restricted

## Map compression

After the first complete map

1. Compare outcomes not titles
2. Merge semantic duplicates
3. Remove motivational and logistical lessons
4. Move unstable reference lists to supporting material
5. Remove adjacent specialisations outside the promise
6. Preserve foundations execution diagnosis and delivery
7. Recheck the coverage matrix

Compression must increase signal density without deleting competence

## Map stress tests

Test the map using at least these scenarios

- A learner with zero formal background
- A learner with scattered online exposure
- A realistic first paid or professional task
- A low budget tool setup
- A result that looks acceptable but is actually weak
- A common failure requiring diagnosis
- A changed tool or platform
- A local market context different from the source examples

The map must explain how each learner progresses and how each scenario is handled

## Architecture blockers

Block writing when

- The capstone does not require most core capabilities
- More than one lesson has substantially the same outcome
- The first useful execution happens too late
- The course teaches creation but not inspection or correction
- The course teaches theory but not performance
- The course teaches tools but not transferable judgement
- The course claims work readiness but omits delivery collaboration or proof
- Projects do not form a progression
- Market specific advice is present without a market pack
- The lesson count is being defended instead of the capability coverage
- A screen or performance lesson has no executable demonstration plan
- A required teaching or project asset is unavailable
- Benchmarking reveals a material capability gap inside the promise
- A lesson withholds its central answer to create continuation
- Adjacent lessons are connected only by topic order rather than cause consequence or capability dependency
- The peak is not earned by accumulated capability
- The sequence depends on theatrical delivery fake stakes or a repeated dramatic formula
