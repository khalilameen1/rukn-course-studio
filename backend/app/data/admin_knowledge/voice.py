"""Voice, style, teleprompter, doctrine, and quality-standard articles."""

from __future__ import annotations

TELEPROMPTER_DOCX_CONTRACT = """# ROKN Teleprompter DOCX Contract

This defines what the final exported DOCX is - and is not. Every generated
course's final DOCX must follow this contract exactly.

## What the final DOCX IS

The final DOCX is a teleprompter-ready lecturer script - ready to read
directly on camera, with no further editing needed.

## What the final DOCX is NOT

- The final DOCX is not a book.
- The final DOCX is not a student handout.
- The final DOCX is not a preparation report.

## Required contents (and nothing else)

The final DOCX must contain only:

- Course title
- Module headings
- Lesson/Reel headings
- The exact spoken script the lecturer will say on camera

V1 has no Production Pack, asset briefs, design instructions, or project
blocks in the DOCX. Bridge projects may exist internally for map structure
only — they are never exported.

## Forbidden contents

The final DOCX must never contain:

- Production notes, asset briefs, design instructions, screenshot plans
- Project / bridge-project blocks
- A cover page
- Branding pages
- "Prepared by AI" or any similar credit/disclaimer
- Methodology notes
- Internal generation notes
- Review notes (student, critic, mentor)
- Quality notes / quality scores
- Evidence ledger, citations, URLs, source lists
- "Needs confirmation", "needs review", research notes
- First drafts or planning labels
- Dynamic Teaching Curve planning (`module_curve`, `lesson_curve`,
  `hook_strength`, `tension_curve`, or any other internal planning labels)
- Creator persona planning (`course_creator_persona`,
  `module_persona_adjustment`, `lesson_persona_state`, or persona labels)
- Creator/Specialist Critic internals (`fatal_issues`, `rebuild_direction`,
  draft/critic notes, or any specialist_critic_report fields)
- Instructions like "say this" or "explain that" addressed to the lecturer
  instead of being the actual words to say
- "Note to instructor" sections
- Academic objective sections (e.g. "Learning Objectives")
- "In this lesson we will learn..." framing, unless it is naturally
  something a lecturer would actually say out loud
- Anything addressed to the course creator instead of to the lecturer/student

## Default spoken style

- Clean Egyptian Arabic
- Direct opening - no formal introductions
- No filler
- No robotic wording
- No academic essay tone
- Ready to record immediately, with no further editing needed

## Teleprompter readability formatting

The final script must be formatted for teleprompter reading. Use natural
spoken lines. End each complete sentence/thought with a new line. Use
blank lines between idea blocks. Avoid heavy punctuation. Do not break
every word into a separate line. Do not use stage directions or pause
labels. The formatting itself should guide reading, breathing, and silence.

- One spoken sentence or complete thought per line
- Small visual blocks per idea; blank line where the lecturer should pause
- No [pause], [breath], [silence], or similar labels
- No giant paragraphs and no TikTok-poetry one-word lines
- Formatting helps delivery only — never delete teaching meaning
"""

HIGH_SIGNAL_REEL_DOCTRINE = """# ROKN High-Signal Reel Doctrine

This doctrine governs how reels/lessons are written for Rukn. It does not
replace rukn_writing_style, rukn_core_rules, or rukn_teleprompter_docx_contract
- it raises the standard against shallow short-form habits, clichés, and
template addiction mechanics.

Style and format authority still come ONLY from Admin Knowledge and the
teleprompter DOCX contract. Uploaded sources never define Rukn voice or structure.

## A. Hook principle

A hook is not hype. A hook is a meaningful first sentence that stops the
viewer because of the *idea*, not because of exaggerated wording.

Avoid: biggest, worst, most dangerous, "secret no one knows", "this will
destroy", and any forced attention bait.

Use calm precision unless the idea itself deserves heat. Some topics are
naturally quiet and should stay quiet.

## B. Loop principle

The loop is not "in the next reel". The loop should feel like a natural
cut at an important point - drama/platform style - not an announcement.

The viewer should want the next part because the idea opened a real need,
not because we told them to wait.

## C. Standalone + series principle

Every reel must work alone on social media. A stranger should understand
it without previous context.

Inside the app series, do not repeat the previous reel at the start. No
recap disguised with different wording.

## D. Variable length principle

Each reel's length follows the idea. Short, medium, or long (even ~5
minutes) are all valid when the idea needs it. A sharp idea may be under a
minute.

Do not force equal word counts. Do not pad to hit a number. Do not cut
until the content is shallow.

## E. High-signal principle

Every reel must contain something worth saving or sharing:
- a non-obvious distinction
- a practical correction
- a real-world insight
- a mistake the student was probably making
- a simple explanation of something previously confusing
- a usable mental model
- a field-specific shortcut that is honest

Avoid generic information everyone already knows.

## F. Real-world locality

Examples should fit the real learner's world: small businesses, local
shops, restaurants, clothing brands, freelancers, students with phones,
low budgets, Egyptian/Arab market reality.

Avoid defaulting to huge companies, expensive tools, luxury devices, or
imported contexts that do not fit Egyptian students.

## G. No surface-level short-form thinking

Being a reel does not mean shallow. Being a series does not mean repeated
hooks and fake cliffhangers. Content can be deep, accurate, and useful
while still spoken simply.

## H. No forced selling

The lecturer should sound like a teacher, not a desperate seller. Showing
the honest value of the course/app is allowed. Do not make selling the
main goal of the speech.

## I. No poetic prose or street slang

Avoid poetic emotional prose, motivational fluff, fake Egyptian street
slang, jokes for the sake of jokes, strange metaphors, and "sersegy"
language.

Tone: natural, accurate, clean, human, and domain-native.

## J. Domain-specific voice

Do not use one voice for every skill. A designer, programmer, marketer,
language teacher, and religious educator do not share the same energy.
Vary module architecture and rhythm so the course does not feel like one
repeated machine.

## Adversarial self-review (required writing process)

For every reel generation, the writer must internally produce:
1. Draft A
2. Draft B
3. Adversarial Critic pass
4. Master Version

Only the Master Version becomes `script_text`. Never ship Draft A or B.

The critic must ask:
- Is the hook overhyped?
- Is the loop forced?
- Is any sentence removable without loss?
- Is the example realistic and local?
- Is the idea actually worth sharing?
- Is this generic information?
- Does this sound like a human lecturer?
- Does this sound like AI Egyptian Arabic?
- Is it too shallow?
- Is it trying to sell?
- Is it repeating a previous reel structure?
- Does it turn a good rule into a template?
- Is the length natural for the idea?

## Course / module anti-template checks

Across a module:
- Hooks must not come from the same family.
- Loops must not use the same move.
- Reel lengths must vary naturally.
- Examples must not all come from the same scenario.
- Devices like "practical application", "exception", "mistake", "secret"
  must not appear mechanically in every reel.
- Recaps must not open every reel.
- The course should feel connected, not chopped.

## Hard fail conditions

A reel fails quality if:
- removing multiple sentences does not hurt it
- it relies on overhyped hook language
- it gives generic advice
- it uses unrealistic examples
- it sounds like AI-written colloquial Arabic
- it repeats a structure used recently
- it sells instead of teaches
- it is shallow because it was forced short

## Source authority (never define Rukn style/format)

- Scientific sources provide **knowledge only** - they must not influence
  language, tone, or structure.
- Flow references (`flow_reference`) are **Natural Colloquial Calibration** —
  language naturalness samples only. Help scripts avoid translated / stiff /
  robotic Arabic. Never flow/teaching/hook/pacing/map references; never facts;
  never assume the speaker is good; never copy messy structure. ROKN writing
  rules stay higher authority; official docs stay factual authority.
- Rukn style comes from Admin Knowledge. Rukn format comes from the
  teleprompter DOCX contract. Naturalness calibration must not weaken quality,
  structure, clarity, or educational discipline.
"""

EDUCATIONAL_CREATOR_STANDARD = """# ROKN Educational Creator Standard

Define the voice, presence, attitude, and teaching character expected in ROKN
course scripts. V1 remains Teleprompter DOCX only — no new output types.

The final script should sound like a successful educational creator who is also
a real practitioner in the field — not a generic AI instructor or course seller.

## 1. Core identity
Serious practitioner who walked the road before the learner, understands the
field from the inside, knows common traps, and wants to shorten the learner’s
path.
Not: generic AI teacher, academic lecturer only, hype influencer, course seller,
motivational speaker, someone who memorized two tips, or someone whose only job
is selling courses.

## 2. Main traits
Deeply familiar with the field; clear without shallow; practical without
simplistic; generous with information; calm and confident; honest about reality;
aware of wrong beliefs; aware of real shortcuts and fake ones; protective of
learner time; focused on the course promise.
Not trying to look clever at the learner’s expense. Not hiding useful information
for fake suspense. Not treating the course as a quick cash grab.

## 3. Field credibility
Make the student feel: “This person is really inside the field.”
Through precise distinctions, realistic warnings, field-native examples,
practical decision rules, beginner misunderstandings, online exaggerations,
what matters in real work, what can be ignored, and how tools/clients/budgets/
constraints change advice.
Do not invent fake expertise, personal stories, or claims that the instructor
did things unless the user provided them. Credibility = useful judgment, not
fake biography.

## 4. Generosity
Give the useful point clearly. Do not circle the answer, delay value for
artificial retention, use empty teasers, hide the practical shortcut, or waste
time with filler. Give enough context to apply.
Generosity ≠ dumping everything. Give the right thing at the right moment.

## 5. Clarity without flattening
Simplify without killing depth. Avoid shallow checklists, vague advice, abstract
philosophy, over-explaining background, academic detours, fake “simple hacks.”
Good explanation: name the problem, why it happens, the useful distinction,
how to act, misuse warnings, and connection to the course journey.

## 6. Reality over fake idealism
When relevant, reflect real Egyptian/Arab market conditions: small budgets,
beginner constraints, unclear clients, fast-changing tools, limited teams,
WhatsApp/Facebook/Instagram workflows, imperfect assets, messy work, practical
progress over perfect theory.
Avoid imported idealism: huge budgets, perfect data/clients/teams, textbook
workflows that collapse in real work.

## 7. Strong opinion, but grounded
May disagree with common advice when scientifically or practically stronger,
grounded, clearly explained — not contrarian for attention, not arrogant, not
taste-only. Feel like: “I’m telling you this to save you from a real mistake.”
Not: “I’m different so listen to me.”

## 8. Respect for learner time
No rambling, repetition, irrelevant side stories, dumb reels, filler motivation,
forced engagement, long setup before the point, or overexplaining the obvious.
Every lesson must earn its place.

## 9. Human warmth
Student should feel: this person is on my side, not showing off, not judging,
not selling illusions, helping avoid mistakes, guiding the path.
Tone: warm, direct, mature, confident, generous, respectful.
Not: cold, robotic, sarcastic, arrogant, over-friendly, clownish, fake intimate.

## 10. Content creator skill
Understand educational mechanics: meaningful hook, clear explanation, natural
progression, strong examples, useful loops, clean endings, pacing, when to
compress/expand, keep attention without lying, move from idea to action.
Mechanics stay invisible — no template hooks, repeated endings, forced loops,
engagement bait, or fake cliffhangers.

## 11. Speech qualities
Sound like a real human explaining: clean Egyptian Arabic, clear spoken lines,
no translated expressions, no stiff MSA, no street vulgarity, no fake slang,
no robotic smoothness, no marketing copy.
May sound like natural turns (“خليني أوضح لك الحتة دي”, “الغلط هنا إن ناس كتير
بتفهم الموضوع بالعكس”, “اللي يفرق معاك عمليًا هو كذا”, “مش كل الحالات ينفع معها
نفس الحل”, “هنا بقى لازم ناخد بالنا”) — never overuse repeated stock phrases.

## 12. What the script must avoid
Not a content farm, template generator, course salesperson, motivational coach,
shallow list maker, popular-advice copycat, someone afraid to say what is true,
someone stretching duration, or an outsider explaining from summaries.

## 13. Interaction with other ROKN rules
Works with High Signal Reel Doctrine, Grounded Claims Gate, Official Tool
Documentation Gate, Knowledge Priority Ladder, Teleprompter Readability
Formatting, Natural Colloquial Calibration, Mixed-Quality Draft handling.
Does not override factual grounding. Does not justify unsupported claims, fake
personal experience, or copying a creator's style.
"""

ANTI_PATTERNS_QUALITY_CHECKS = """# ROKN Anti-Patterns and Quality Checks

Rejected patterns and diagnostic checks only. V1 remains Teleprompter DOCX only.
**Never** use this key as a writing template or source of “good” examples to copy.

## 1. Core rule
This key contains rejected patterns and diagnostic checks only.
It must not contain reusable good openings, hooks, lesson templates, fixed good
examples to imitate, repeated sentence patterns, or preferred catchphrases.
Use it to avoid bad output — not to copy a “good” style.

## 2. Anti-patterns to reject

### A. Translated Arabic
Signs: English translated into Arabic, stiff formal phrasing, unnatural
connectors, article-like sentences, textbook transitions.
Check: Would a serious Egyptian instructor naturally say this aloud?

### B. Fake Egyptian slang
Signs: over-casual tone, street slang, forced intimacy, “يا صاحبي / يا معلم”
tone, influencer exaggeration.
Check: Does it sound clean, mature, and natural?

### C. Template hooks
Reject when mechanical or repeated: أكبر غلطة، السر، محدش قالك، هتتصدم،
في ناس لسه، المشكلة مش في كذا المشكلة في كذا.
Check: Does the opening come from actual lesson tension, or from a template?

### D. Forced loops
Reject: “في الريل الجاي”, artificial cliffhangers, repeated ending formulas,
suspense without educational reason.
Check: Does the ending naturally move the learner forward?

### E. Shallow checklist teaching
Reject: do X/Y/Z with no why, steps without decision logic, advice without
context, practical course that becomes bullet points.
Check: Does the learner know when and why to apply the step?

### F. Academic over-explaining
Reject: long theory that does not serve action, historical background unless
needed, definitions that do not affect decisions, side detours.
Check: Is this depth useful now, or showing off?

### G. Course seller tone
Reject: teasing value without giving it, hiding the useful point, overpromising,
motivational filler, selling instead of teaching.
Check: Is the instructor generous with actual useful information?

### H. Fake expertise
Reject: invented personal experience, fake “from my experience” unless user
provided it, pretending the instructor did something specific, overconfident
claims without grounding.
Check: Is expertise shown through judgment, not fake biography?

### I. Source loyalty
Reject: preserving old modules because they exist, copying old draft order,
copying old AI examples, keeping nice but off-promise lessons, trusting old
tool workflows.
Check: Does this serve the current course promise?

### J. Teleprompter over-formatting
Reject: dense paragraphs, one word per line, fake dramatic line breaks, pause
labels like [pause] or [breath], poetry-like formatting.
Check: Do line breaks help real reading and breathing?

## 3. Quality checks before final rewrite
Before saving final lesson script, check:
- Is the opening specific to this lesson?
- Does the lesson earn its place in the course?
- Is there filler that can be removed?
- Is a useful distinction missing?
- Is there an unsupported important claim?
- Is old tool behavior that should be checked officially?
- Does it sound like a real human instructor?
- Is it field-aware rather than generic?
- Is it generous without dumping?
- Is it clear without flattening?
- Is it deep without empty philosophy?
- Is teleprompter formatting readable?
- Are phrases repeated from previous lessons?
- Is the ending natural, not forced?

## 4. Prompt compiler rule
Use mainly in review stages, final rewrite, and export sanity — not every
prompt. Rejection/checklist layer only — never a writing template.
"""

