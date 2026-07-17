"""Source, market, originality, and interpretation gate articles."""

from __future__ import annotations

SOURCE_DISTILLATION_GATE = """# ROKN General Source Distillation Gate

All course sources are raw material — not final authority and not a format/style
model. V1 remains Teleprompter DOCX only. Never copy sources literally. Never
inherit source format, tone, structure, filler, or market assumptions.

## 1. Core rule
Every source may be academic, shallow, outdated, US/Western, theoretical,
repetitive, filler-heavy, poorly structured, or partially harmful. Extract only
what serves the current course promise. Downgrade or discard the rest silently.

## 2. Source distillation
Extract only: useful concepts; accurate distinctions; learner objections;
practical warnings; valid examples to rebuild; current relevant terminology;
verified useful steps; gaps to cover; mistakes to avoid.
Discard/downgrade: filler; repetition; weak examples; off-promise content;
outdated claims; old tool behavior; US-only assumptions when Egypt/Arab context
applies; academic theory that does not help application; surface advice; source
structure that weakens the course; translated/stiff/non-ROKN language.

## 3. Academic sources
Academic sources may inform depth and accuracy. Final script must not sound
academic. Convert theory to useful explanation, definitions to decision logic,
abstract concepts to practical meaning, long discussion to what the learner
needs now. Do not copy academic wording. Do not turn the course into a book
chapter.

## 4. Shallow sources
A shallow source may still contain one useful point. Do not reject entirely.
Extract useful candidate ideas only. Verify and rebuild. Do not inherit its
shallowness, filler, or hype.

## 5. Outdated sources
If a source may be old: do not trust current tool behavior from it; check
official docs for platform/tool behavior; keep durable principles only if still
valid; remove or rewrite outdated steps. Official current documentation
overrides old sources.

## 6. Foreign-market sources
If a source assumes US/Western market: do not copy assumptions blindly; adapt
examples and advice to target market (default Egypt/Arab unless user chose
otherwise); keep universal principles; rewrite execution for realistic local
conditions (budget, channels, client behavior).

## 7. Source format must not affect ROKN format
No source may override: Teleprompter DOCX contract; ROKN spoken Egyptian Arabic;
readability line breaks; no citations in final DOCX; no internal notes; no
academic formatting; no article style; no source headings copied blindly; no
course map copied blindly from source structure.

## 8. Prompt compiler rule
When using any source memory, treat it as **distilled raw material** only.
The model receives: extracted useful points; relevance notes; outdated warnings;
market adaptation notes; blocked content warnings — not the full source
repeatedly, not the source as equal authority, not the source format.

## 9. Source usefulness / credit hygiene
Mistrust does not mean rejection. It means cost-aware distillation.
- Assess usefulness, risk, freshness, extraction quality, and unique useful material.
- High-risk / low-quality sources: extract small candidate signals only; do not
  send full source to lesson prompts; do not re-analyze unchanged sources.
- If useful despite flaws: keep concepts, objections, warnings, terminology,
  examples to rebuild, gaps, durable principles.
- If low-value (`low_signal`): brief candidate notes only; exclude from expensive
  full-context dumps; do not spend deep generation context on it.
- Cache by raw_source_hash; inject compact distilled memory only.
"""

TRANSCRIPT_TOPIC_RELEVANCE_GATE = """# ROKN Transcript Topic Relevance Gate

A transcript may be unrelated to the course topic or about the exact same topic.
Never treat all transcripts the same. V1 remains Teleprompter DOCX only.

## 1. Topic relevance classification
For every transcript, classify topic relevance: same_topic, adjacent_topic,
off_topic, unclear — even when the user chose Transcript or Raw material.

## 2. Off-topic transcript
If off_topic: Natural Colloquial Calibration only — avoid stiff, translated, or
robotic Arabic. Do not use for facts, claims, examples, hooks, course map,
lesson structure, terminology, recommendations, or tool behavior.

## 3. Same-topic transcript
If same_topic: may be course raw material. Extract useful concepts, learner
objections, common mistakes, practical points, examples to rebuild, coverage
hints, distinctions, warnings, and current relevant terminology. Raw material
only — never copy wording, hooks, loops, structure, speaker style,
catchphrases, examples verbatim, filler, repetition, weak explanations, or
off-promise sections.

## 4. Outdated information check
Same-topic tool/platform/current-market claims are not trusted automatically.
Check currency, official tool docs, old UI/workflow, and foreign-market scope.
If outdated: remove, narrow, verify from official docs, or rewrite with current
behavior. Official current documentation overrides same-topic transcripts.

## 5. ROKN format protection
No transcript may override: ROKN spoken Egyptian Arabic; Teleprompter DOCX
contract; line-break readability; no citations in final DOCX; no internal notes;
no article/book style; no copied course map; no hype hooks; no forced loops.
Distill transcript content into ROKN teleprompter format.

## 6. Source classification
User types map to: knowledge/raw source (scientific reference, transcript, raw
material); natural spoken language sample only (flow_reference); mixed-quality
previous AI course draft; old course attempt; user notes; let system classify
(raw material). Transcript/raw uploads still run topic relevance:
same_topic → raw material; off_topic → colloquial calibration only;
unclear → conservative extraction.

## 7. Prompt compiler labels
Same-topic label: extract ideas/objections/distinctions/practical points only;
do not copy wording/hooks/loops/structure/examples/speaker style; verify
tool-related claims; rebuild in ROKN teleprompter format.
Off-topic label: colloquial calibration only — zero factual, structural, hook,
or example authority.

## 8. Final output hygiene
Final Teleprompter DOCX must never contain internal transcript labels, source
notes, or distillation markers.

## 9. Transcript imperfection — do not trust wording literally
Many transcripts were generated automatically by speech-to-text systems. Treat
them as useful but imperfect noisy raw material. Common errors include: wrong or
missing words; duplicated words or fragments; merged or split sentences; wrong
punctuation; Arabic written instead of English technical terms; English written
instead of Arabic; incorrect product names; OCR mistakes; homophones; spelling
errors; speaker-ID mistakes; timestamps mixed into text; repeated or omitted
fragments.

Therefore:
- Do NOT trust transcript wording literally.
- Extract meaning, not wording.
- Correct obvious transcription mistakes.
- Restore technical terminology when obvious.
- Do not inherit transcript grammar, formatting, or transcription errors.
- If a transcript conflicts with official documentation, verified educational
  sources, or grounded facts, the transcript loses.
- The transcript is evidence of what someone probably said, not proof the
  content is correct.

## 10. Source origin — separate from file format and user intent
For every course source, distinguish: file_format (txt/md/docx/pdf/pasted),
source_intent (user category), source_origin (how produced), topic_relevance,
and factual authority. Never infer reliability from file extension.

source_origin values: written_document, ai_generated_transcript,
human_transcript, course_transcript, old_course_transcript,
meeting_or_webinar_transcript, unknown.

Transcript-like origins must receive transcript-noise handling before
extraction. Course transcripts are raw material only — rebuild in ROKN format.
Old course transcripts may be outdated — official docs override. Off-topic
transcripts: colloquial calibration only. Final DOCX must never mention
source_origin, ASR errors, or internal cleaning metadata.
"""

SOURCE_IMPERFECTION_GATE = """# ROKN General Source Imperfection Gate

Mistrust / imperfection rules apply to ALL course sources — not only transcripts.
A book, PDF, DOCX, article, academic paper, or OCR extract may still be imperfect.
V1 remains Teleprompter DOCX only.

## 1. Provenance fields (internal)
For every source, track or infer:
- source_origin: written_document, academic_book, practical_book, article,
  old_course_material, course_transcript, ai_generated_transcript,
  human_transcript, scanned_pdf, ocr_text, screenshot_or_image,
  translated_material, user_notes, unknown (plus meeting/webinar/old course
  transcript variants when spoken).
- extraction_method: direct_text, pdf_text, docx_text, doc_text, ocr,
  pasted_text, manual, unknown.
- source_risk_flags: outdated_possible, ocr_noise_possible,
  transcript_noise_possible, foreign_market_context, academic_theory_heavy,
  shallow_or_generic, translated_or_stiff, repetitive_or_filler,
  tool_ui_may_be_old, uncertain_terms.

File extension is never authority.

## 2. General mistrust
No source is automatically current, accurate, clean language, final structure,
a ROKN style model, directly copyable, a complete course map, or factual
authority in conflicts. Every source is raw material — extract useful meaning,
then filter, verify, adapt, and rebuild in ROKN teleprompter format.

## 3. Books and academic sources
Allowed: durable concepts, simplified definitions, frameworks, distinctions,
warnings, examples to rebuild, current relevant terminology.
Blocked: copying book structure/paragraphs; academic wording in final script;
theoretical detail that does not help application; trusting current tool/UI
details from old books.

## 4. OCR and scanned PDFs
Clean obvious artifacts only. Do not confidently use suspicious terms.
Preserve uncertainty internally. Verify important claims. Never let OCR
artifacts leak into final DOCX.

## 5. Transcripts are a special subset
Transcript noise (ASR, filler, timestamps, mixed Arabic/English) still applies
when origin is transcript-like. Broader Source Imperfection Gate still applies.

## 6. Foreign-market and outdated
Keep universal principles; adapt execution to Egypt/Arab market. Official docs
override outdated tool/platform claims. Preserve durable principles only.

## 7. Prompt labels
Always attach the untrusted-raw-material label. Append transcript, OCR, or
academic/book warnings when relevant.

## 8. Final DOCX
Never mention source_origin, extraction_method, source_risk_flags, OCR/ASR
notes, mistrust notes, correction metadata, internal labels, source names, or
citations. Spoken teleprompter script only.
"""

INTERPRETATION_GUARDRAILS = """# ROKN Final Interpretation Guardrails

Prevent common AI misreadings of ROKN rules. These clarify intent — they do
not add product features or new output types. V1 remains Teleprompter DOCX only.

## 1. Natural Egyptian Arabic ≠ street slang
Clean natural Egyptian Arabic. Not stiff MSA, translated English, fake slang,
street vulgarity, comedian style, over-casual, childish, “صاحبي/يا معلم” tone,
or artificial influencer talk. Sound like a serious human instructor.

## 2. Teleprompter formatting ≠ TikTok poetry
Line breaks help reading, breath, pause. Do not put one word per line, create
dramatic broken lines, over-format for fake emotion, or turn lessons into
motivational fragments. One sentence/complete thought per line; small blocks;
blank line for natural transition.

## 3. No heavy punctuation ≠ zero clarity
Avoid dense article-style punctuation. Minimal punctuation is OK when needed
(real questions, useful colon, necessary parentheses, tool/English terms).
Goal: readable spoken script, not punctuation extremism.

## 4. Hook ≠ hype
Hook = truthful reason to listen now. Do not force “أكبر غلطة / السر /
محدش بيقولك / هتتصدم”, fake tension, or exaggerated claims. Use real lesson
purpose: misconception, decision, mistake avoided, clearer step, broken assumption.

## 5. Loop ≠ forced cliffhanger
Do not end every lesson with “في الريل الجاي”, artificial suspense, template
bait, or engagement bait. Ending should make the next lesson feel needed naturally.

## 6. Premium length ≠ padding
Serious courses may be long, but never fill with fluff. Length from real
explanation, examples, misconceptions, steps, bridges, objections, application.
Merge tiny ideas; allow needed length; delete unnecessary sections.

## 7. Official docs ≠ fragile UI tutorial
Official docs avoid outdated teaching. Final lessons must not become
click-here / button top-left / screenshot-only paths. Teach current behavior,
durable workflow, learner goal, and how to find settings if UI moves.

## 8. Official docs beat old sources — wording still ROKN
Docs are factual authority. Final wording stays ROKN: human spoken, practical,
market-aware, teleprompter-ready. Never copy documentation prose into script.

## 9. Grounded Claims Gate ≠ citations in DOCX
Ground claims internally. Never put citations, links, evidence notes,
“according to”, source lists, needs_review, or needs_confirmation in DOCX.

## 10. Mixed-quality old AI drafts ≠ trash and ≠ authority
Raw material only. Extract useful ideas, objections, topic candidates, gaps,
warnings, what to avoid. Do not copy wording, hooks, loops, structure,
verbatim examples, ungrounded claims, dumb reels, or off-promise modules.
Keep good ideas; delete whole modules; rebuild relevant bad lessons;
discard well-written off-promise lessons.

## 11. Natural Colloquial Calibration ≠ model to imitate
Off-topic transcripts only avoid strange/translated/stiff Arabic. Not hooks,
flow, teaching models, structure, style, facts, or examples. Do not assume
the speaker is good. Do not copy. Broad natural-language signals only.

## 12. Student Agent ≠ stupid student
Serious normal learner — not edge-case, lazy, troll, genius, or total
misunderstander. Catch real confusion a sincere learner may face.

## 13. Specialist Critic does not write the course
Harsh review only (shallow, wrong facts, weak practical value, missing steps,
generic language, unrealistic advice, outdated tools). Creator rewrites.

## 14. Master Mentor ≠ imitation of a real creator
Synthetic. No named creator imitation, catchphrases, signature formats.
Improves educational instinct, retention, course arc, dignity, subtle gaps.

## 15. Pasted Course Map ≠ automatically final
Preserve intent and promise. Rebuild if outdated tools, weak order, padding,
off-promise modules, dumb reels, or missing prerequisites. Do not blindly
obey a bad map; do not ignore user intent.

## 16. Admin Knowledge ≠ dumping ground
Global ROKN rules only. Never course PDFs, transcripts, drafts, one-course
notes, or course-specific maps — those belong in Course Sources / Course Map.

## 17. Auto research ≠ browse everything
Focused questions only: what, why, which lesson, which trusted source, when
to stop. No blind browsing, full-site dumps, or repeated research when memory exists.

## 18. Cost hygiene ≠ starve the model
No full PDFs repeatedly, no resending all Admin Knowledge every call, no
duplicate research — but do not shrink context until quality collapses.
Use the right compact pack per stage.

## 19. Final DOCX must not expose the machine
Never show agents, reviews, scores, evidence, sources, internal labels,
conflict notes, prompts, quality gates, or production notes. Only title,
module headings, lesson/reel headings, spoken transcript.

## 20. Failure must not destroy progress
Save completed lessons; clear status; partial DOCX if available; no restart
from scratch; no infinite retries; no duplicate lessons; no silent credit burn.

## 21. Market realism ≠ Egyptian cliché overload
Local reality when helpful. Avoid huge US corporate assumptions and foreign
workflows that do not match. Also avoid cliché overuse — realistic examples only when relevant.

## 22. Practical ≠ shallow checklist
Steps matter, but include why, common mistake, decision rule, example, and
what to do when the situation changes.

## 23. Final rewrite must be a real rewrite
Not tiny patches on draft one. After reviews, rebuild when needed: clearer,
more grounded, more spoken, more practical, better ordered, less generic/AI-like.

## 24. No visible “I can’t verify” in the script
Unsupported claims: remove, narrow, research, or rewrite safely. No uncertainty
warnings in DOCX.

## 25. ROKN quality beats source loyalty
Serve current promise, learner outcome, official current truth, grounded
claims, teaching quality, teleprompter readability. Never keep a source just
because it was uploaded.
"""

