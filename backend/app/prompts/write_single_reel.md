# Task: Write a Single Reel Script

Write the lecturer script for exactly one reel. This is an internal generation step that exists only to prevent laziness and repetition across the course - the user never sees this reel on its own, only the final assembled DOCX.

## Adversarial self-review (mandatory process)

Internally produce, in order:
1. **Draft A**
2. **Draft B** (a genuinely different angle, not a paraphrase of A)
3. **Adversarial Critic** against both drafts using `rukn_high_signal_reel_doctrine`
4. **Master Version** - a new rewrite that survives the critic

Only the Master Version may appear in `script_text`. Never ship Draft A or Draft B.

Critic must reject: overhyped hooks, forced "next reel" loops, removable filler, generic advice, academic/poetic tone, fake street slang, unrealistic imported examples, disguised recaps, template copying, desperate selling, equal-length padding, shallow cuts.

## Golden rules

- If `previous_review_feedback` is non-empty, this is a retry: fix exactly those issues while rewriting, don't just regenerate from scratch.
- Follow `rukn_high_signal_reel_doctrine` and every voice/style rule in `rules_context`.
- Hook = meaningful first idea, not bait. Loop = organic cut, never "in the next reel".
- Standalone for a stranger; no recap of prior reels at the opening.
- Length follows the idea - do not pad or force equal word counts.
- High-signal only: non-obvious distinction, correction, realistic local example, or usable mental model.
- Examples fit Egyptian/Arab learner reality (shops, phones, freelancers, low budgets) - not luxury/imported defaults.
- Teacher dignity: may show course value honestly; never sound like a desperate seller.
- Domain-appropriate energy (designer ≠ marketer ≠ programmer).
- No generic filler: no throat-clearing openers, no "in this reel"/"in this video" references, no motivational fluff, no cliché endings.
- Cover every point in `reel.must_cover`. Avoid every point in `reel.must_avoid`.
- If `sources` is empty, write from `reel`/`module` context and `rules_context` only - never invent a fact as if a source supports it.
- If `sources` is non-empty: scientific sources are knowledge only (never tone/structure); flow_reference is human_flow_profile only (never a format template, never copy catchphrases).
- Do not reuse an opening, example, or idea already listed in `prior_reels_in_module`'s `used_ideas`/`used_examples`.
- Practical-skill focus: real, realistic application - not a toy scenario.

## Output

Call the `generated_reel` tool. `script_text` is only the Master Version spoken script - keep `used_ideas`/`used_examples` to short tags, not sentences. Never include draft/critic notes in `script_text`.
