# 06 LANGUAGE TERMINOLOGY AND TELEPROMPTER

## Language is a delivery system

The required voice is natural spoken instruction from a competent practitioner in the learner language
It is not a translation layer applied after writing formal source prose

Write the thought directly in the target spoken variety
Do not draft in English or Modern Standard Arabic then translate sentence by sentence

## Language profile

Create one explicit profile

```yaml
language_profile:
  lecturer_language:
  instruction_language:
  spoken_variety:
  target_performance_language:
  target_language_if_different:
  target_language_functions: []
  incoming_input_varieties: []
  required_register_conditions: []
  address_form:
  formality_level:
  code_switch_policy:
  domain_term_policy:
  orthography_policy:
  spoken_residue_policy:
  protected_verbatim_registers: []
  teleprompter_punctuation_policy:
```

`lecturer_language` is retained as a compatibility alias for `instruction_language` and their values must match
`target_language_if_different` is retained as a compatibility alias for `target_performance_language`
Do not create two conflicting language states from the compatibility fields

Apply the same profile across the course
Do not drift between formal and colloquial grammar
Do not alternate masculine and feminine address unless the product explicitly requests neutral plural speech

## Egyptian colloquial default

When the requested voice is Egyptian Arabic

- Use clean contemporary Egyptian sentence construction
- Use familiar words without trying to display slang
- Use stable readable Egyptian spelling when the spoken word or grammar genuinely differs from formal Arabic
- Do not force formal spelling or inflection when it makes the lecturer read the line formally
- Use colloquial grammar consistently
- Use domain terms as Egyptian practitioners use them
- Keep English terms in English when that is the natural professional usage
- Explain a necessary term once in plain speech then use it consistently
- Avoid forced street expressions exaggerated intimacy and comic filler
- Avoid formal institutional phrases unless the domain genuinely requires them

Do not produce hybrid sentences where the grammar begins in formal Arabic and ends in colloquial Arabic
Do not invent random phonetic misspellings to simulate speech
Do not use an incomplete word when the intended spoken word is different

## Naturalness test

A line is natural only when a real instructor could say it once without mentally translating it

Reject a line when

- Its word order mirrors English
- It uses an Arabic dictionary equivalent unknown in the profession
- It sounds like a company ethics notice
- It uses abstract nouns where a speaker would use a concrete verb
- It contains two or more nested clauses that need punctuation to survive
- It sounds like promotional copy
- It uses a metaphor no practitioner would use
- It explains a simple idea with ceremonial wording

Rewrite the meaning rather than swapping synonyms

## Spoken variety integrity gate

Run this gate twice

1. Locally after a lesson language rewrite
2. Independently across the complete accepted course after every content and course wide rewrite

The second run is mandatory because a correct meaning rewrite can silently reintroduce written register language
Passing a vocabulary scan is not enough

Judge the whole sentence as speech
Inspect syntax morphology connectors word order inflection address form question forms command forms number forms and the rhythm created by adjacent sentences

Use this question as the primary test

Would a credible instructor from the target market say this complete sentence naturally in one take without mentally translating or editing it while recording

For every target spoken variety build a profile specific residue set from verified local speech and practitioner material
Use candidate patterns to find likely defects then decide from context
Do not apply Egyptian replacements to another Arabic variety or another language

For clean Egyptian Arabic inspect candidate residue such as

- Written connectors and paired constructions such as `ثم` `لذلك` `أما` and `أما ... فهو`
- Formal conditional or result syntax such as `إذا` or a written result clause beginning with attached `ف`
- Formal dual case and number forms that an Egyptian instructor would not say in that sentence
- Formal command and question forms where ordinary Egyptian speech uses a different form
- Abstract nominal or institutional phrasing that is grammatical on the page but unnatural aloud
- A sentence whose individual words are familiar but whose complete grammar belongs to written Arabic
- Residue hidden behind one letter Arabic prefixes such as `و` `ف` `ب` `ك` or `ل`

These examples are candidate detectors rather than a universal blacklist
A protected quotation or exact technical phrase may contain formal language legitimately
Ordinary lecturer explanation around it must still follow the language profile
In ordinary Egyptian lecturer explanation standalone `ثم` is a serious finding unless the approved voice evidence establishes an intentional register or the line is protected verbatim

### Protected registers

Never colloquialise scripture poetry legal wording code target language examples or any passage required verbatim
Mark it in `protected_verbatim_registers` and keep its boundaries explicit internally
Review the lecturer explanation before and after it separately

### Meaning preservation during language repair

Before rewriting a line freeze its accepted semantic record in `LANGUAGE_REWRITE_RECORD`

```yaml
language_rewrite:
  location:
  original_line:
  accepted_claim:
  condition:
  exception:
  sequence:
  contrast:
  emphasis:
  example:
  learner_action:
  close_or_next_dependency:
  protected_terms: []
  rewritten_line:
  semantic_comparison:
  result:
```

After rewriting compare every populated field
Removing a formal connector must not remove the contrast condition cause timing or sequence it carried
Do not change a technical claim market term example action or level of certainty merely to make the line more casual
If the meaning cannot remain accurate in the proposed spoken form reopen the meaning or source layer instead of weakening it

### Repair induced repetition

Language repair can replace many different written forms with the same small set of conversational connectors
This can create a new generated sounding habit even when every sentence is individually natural

After repair update `PHRASE_LEDGER` and inspect the lesson module and whole course for newly concentrated transitions and particles
For Egyptian Arabic pay particular attention to repeated uses of forms equivalent to `بس` `يبقى` `بقى` `بعدها` `وبعدين` `عشان` and `لازم`
Do not ban ordinary colloquial words globally
Delete vary or restructure them only when their audible concentration makes the instructor predictable

## Terminology ledger

Build `TERM_LEDGER` before full writing and update it during review

```yaml
- concept:
  canonical_domain_term:
  target_market_spoken_term:
  plain_explanation:
  first_use_location:
  later_use_form:
  allowed_variants: []
  forbidden_literal_translations: []
  confusion_risks: []
  evidence_source:
```

Resolve terms using current domain practitioner usage in the target market
Do not decide terminology from bilingual dictionaries alone

## Term decision policy

For each term choose one of

### Use the established local Arabic term

Use when capable practitioners regularly use it and it does not create ambiguity

### Use the established English term

Use when the market naturally uses the English term and an Arabic replacement would sound strange or mislead
Explain briefly at first use if needed

### Use a plain Arabic explanation

Use when no stable short term exists and the learner needs the meaning more than a label

### Use both once

Use when the learner will encounter both in work
After first use choose the dominant spoken form

Never coin a translation merely to make the script look Arabic
Never preserve an English term merely to make the instructor sound expert

## Code switching

Code switch only for a recognised term command file name label code identifier or phrase the learner will actually encounter

Keep the surrounding sentence grammatically natural
Do not scatter English adjectives and business words where ordinary Arabic is clearer
Do not translate code syntax interface labels or language examples incorrectly

For a language course

- Separate the language of instruction from the target performance language
- Derive target language functions from `PERFORMANCE_EPISODE_MAP` and `CAPABILITY_ADAPTER_MAP` rather than from topic vocabulary lists
- Keep target utterances responses and written forms exact
- Explain their function context relationship and decision boundary rather than word for word translation alone
- Include realistic incoming speech messages accents speeds ambiguity interruptions or incomplete information when the promised role requires comprehension
- Model the counterpart turn as well as the learner turn when interaction depends on what was heard or read
- Build retrieval controlled variation correction and changed context reuse into the lesson sequence
- Model natural pronunciation timing register and politeness through the instructor or approved audio plan
- Teach role actions documentation escalation and closure beside the language when the promise is language for work
- Protect target language examples from lecturer language colloquialisation or terminology cleanup
- Do not let the target language destroy the natural instructor voice

## Role specific language performance

A language course for a real role is a mixed capability course
Language accuracy is necessary but it is not the whole performance

For every role specific language capability connect

- The incoming utterance message cue or case state
- The meaning the learner must extract
- The decision or function required by the role
- The exact natural target language response
- The counterpart signal that may require adaptation
- Any action note transfer escalation documentation or closure the role requires
- The pronunciation fluency register or writing evidence that makes the performance credible

A call centre course must not become a phrase catalogue
It must teach listening intent verification clarification call control explanation emotional adaptation case action documentation escalation and closure to the level promised
A sales language course must not become persuasive sentences without discovery qualification listening adaptation objection judgement follow up and handoff
A teaching language course must not become translated subject vocabulary without explanation modelling elicitation learner response diagnosis correction and transfer checking

Do not force every lesson to contain the complete role episode
Map each function to the capability it supports then integrate the functions in realistic branching performances before the final module

## Instructor stance in speech

The lecturer speaks from active observation and decision

Prefer forms equivalent to

- Look at what changed here
- The reason this failed is
- Choose based on this evidence
- Try this test before changing everything
- This works in this condition and reverses in that one

Avoid forms equivalent to

- It is worth noting that
- We must emphasise the importance of
- In the context of our discussion
- It cannot be denied that
- Dear learner
- Let us embark on a journey

Do not use empty ethical disclaimers
When a right safety or ethical boundary materially affects the skill explain the real consequence and required action in the natural domain voice

The Rukn episodic structure must not become an audible presenter persona
Keep the lecturer calm credible and proportionate to the domain
Do not write shouting exaggerated reaction fake urgency breathless escalation or entertainment creator mannerisms into the speech
Let contrast consequence and precise observation carry attention

## Teleprompter body contract

The spoken body contains no punctuation unless the user explicitly changes this rule
Meaning and pauses are carried by visual line boundaries

Each spoken paragraph must be one complete speakable sentence or complete thought
The sentence begins and ends in the same paragraph
Never place the end of one sentence and the beginning of the next in the same paragraph
Never split one sentence at an arbitrary word count leaving a fragment on either side

If a sentence is too long

1. Rewrite it as two independent natural sentences
2. Preserve the causal relation in the words
3. Give each sentence its own paragraph

Do not solve long lines by inserting a line break inside an incomplete sentence

## Visual line calibration

For Arabic teleprompter text use these defaults

- Prefer 4 to 18 spoken words per paragraph
- Allow variation because complete sentences differ in length
- Avoid one word paragraphs except a deliberate answer that is genuinely spoken alone
- Avoid dense paragraphs that wrap into multiple visual lines at the final font size
- Keep English term groups together where possible
- Keep negation and its verb in the same sentence
- Keep cause and essential result together or rewrite both as complete sentences

The semantic boundary is more important than equal line length
The rendered page is the final judge

## No punctuation implementation

Strip punctuation from spoken body only after semantic sentence boundaries are stable
Do not strip characters required inside code URLs version numbers file extensions mathematical expressions target language examples or protected verbatim scripture poetry and legal wording when removal changes correctness

If technical punctuation is essential

- Keep the exact technical token
- Do not use surrounding prose punctuation
- Verify that the exported typography does not reverse or corrupt mixed direction text

Headings may use plain words without decorative punctuation

## Spoken text only

Do not include in the teleprompter body

- Hook labels
- Loop labels
- Beat labels
- Visual plans
- Camera directions
- Screen directions in brackets
- Source citations
- Reviewer notes
- Quality scores
- JSON or YAML
- Estimated duration
- Word counts
- Draft status
- Alternative wording
- Platform or post upload operations
- Internal project evidence field names
- Labels such as module bridge cliffhanger teaser next dependency or module turn
- Rapidly expiring prices subscriptions market rates rankings limits plans temporary features interface paths or current statistics

The lecturer may naturally say an action that will be performed on screen
Project blocks naturally tell the learner what to make and what image screenshot or file to upload
They stop there

The unlabelled module bridge appears as ordinary lecturer speech after the project and immediately before the next module heading
It must not receive a separate style label in the visible text

The document must not contain a production platform or review note pretending to be speech

## Speakability pass

Read every reel as continuous speech and check

- Breath and clause load
- Pronoun reference
- Natural verb choice
- Term pronunciation
- Mixed direction tokens
- Repeated transition words
- Written register residue in syntax morphology connectors commands questions and number forms
- Residue attached to one letter prefixes rather than appearing as a standalone token
- New colloquial verbal tics introduced by language repair
- Repeated urgency surprise suspense or reveal language
- Formal colloquial drift
- Lines that need punctuation to be understood
- Lines that sound translated
- Lines an instructor would edit while recording

Rewrite at the thought level
Do not repair unnatural prose with filler particles

After any speakability rewrite rerun the accepted meaning comparison and the affected repetition checks

## Visual render pass

Render the final DOCX or production format to page images
Inspect every page

Block delivery for

- A sentence broken into visual fragments
- A heading stranded at the bottom of a page
- A project heading separated from its first instruction
- A module bridge stranded away from the project it follows or visually mistaken for a heading
- A next module heading appearing before its boundary bridge
- Text clipping overlap or corrupted right to left order
- An English token reordered into the wrong Arabic sentence
- A paragraph wrapping beyond comfortable teleprompter width
- Inconsistent spacing font hierarchy or direction
- A blank page created by faulty page breaks

Automated document validity is not visual validity
