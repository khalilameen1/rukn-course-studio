# Task: Review One Completed Module

Check one finished module - its plan plus all of its reels - as a whole. Internal check only.

## Check for

- Does it actually deliver `module.purpose`, not just touch on it?
- Reels out of order, or disconnected from each other.
- Repetition within the module beyond what a 5-reel window could already catch.
- Any violation of a rule in `rules_context`.
- Generic filler anywhere in the module (intros, recaps, transitions).

## Output

Call the `review_result` tool, `scope` = "module".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse `ReviewAction` per issue - `target_id` = the module's `module_id`, or a specific reel's `reel_id` if the issue is local to one reel, short `reason_code`, one-sentence `instruction`.
