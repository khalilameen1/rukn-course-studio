# Task: Review a Single Reel

Check one generated reel against its plan and the rules. This is an internal check to catch laziness/repetition/hallucination before the user ever sees anything - never write for the user here, never explain at length.

## Check for

- Missing `reel_plan.must_cover` points, or violated `reel_plan.must_avoid` points.
- Generic filler, a forbidden phrase, or any other `rules_context` violation.
- A claim not grounded in the reel's sources (hallucination) - flag anything invented.
- A repeated opening, example, or idea inconsistent with what the reel itself claims to have used.

## Output

Call the `review_result` tool, `scope` = "reel".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse `ReviewAction` per issue - `action` = "rewrite", `target_id` = the reel's `reel_id`, a short `reason_code`, one-sentence `instruction`.
