# Task: Review a Pair of Modules

Compare two consecutive modules (`first`, `second`). This is the primary anti-laziness check: later modules must not get thinner or lazier purely because they come later in the course.

## Check for

- `second` noticeably thinner, vaguer, or lower-effort than `first` for no reason other than position in the course.
- A repeated example, opening, or idea between the two modules.
- The bridge project between them: is it a real, realistic project connecting both modules, or a token filler task?
- Terminology drift between the two modules.

## Output

Call the `review_result` tool, `scope` = "two_modules".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse `ReviewAction` per issue - `target_id` = the affected module's `module_id` or reel's `reel_id`, short `reason_code` (e.g. "laziness", "repetition"), one-sentence `instruction`.
