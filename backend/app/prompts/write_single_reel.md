# Task: Write a Single Reel Script

Write the lecturer script for exactly one reel. This is an internal generation step that exists only to prevent laziness and repetition across the course - the user never sees this reel on its own, only the final assembled DOCX.

## Golden rules

- If `previous_review_feedback` is non-empty, this is a retry: fix exactly those issues while rewriting, don't just regenerate from scratch.
- No generic filler: no throat-clearing openers, no "in this reel"/"in this video" references, no motivational fluff, no cliché endings.
- Cover every point in `reel.must_cover`. Avoid every point in `reel.must_avoid`.
- If `sources` is empty, write from `reel`/`module` context and `rules_context` only - never invent a fact as if a source supports it.
- If `sources` is non-empty, ground specific claims in them; do not go beyond what they actually support.
- Do not reuse an opening, example, or idea already listed in `prior_reels_in_module`'s `used_ideas`/`used_examples`.
- Practical-skill focus: real, realistic application - not a toy or invented scenario.
- Follow every voice/style rule in `rules_context`.

## Output

Call the `generated_reel` tool. `script_text` is the only field that should contain real lecture content - keep `used_ideas`/`used_examples` to short tags, not sentences.
