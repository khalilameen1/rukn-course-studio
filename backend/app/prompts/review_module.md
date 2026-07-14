# Task: Review One Completed Module

Check one finished module - its plan plus all of its reels - as a whole. Internal check only.

## Check for

- Does it actually deliver `module.purpose`, not just touch on it?
- Reels out of order, or disconnected from each other.
- Repetition within the module beyond what a 5-reel window could already catch.
- Any violation of a rule in `rules_context`, especially `rukn_high_signal_reel_doctrine` anti-template checks:
  - hooks from the same family
  - loops using the same move
  - lengths that do not vary naturally
  - examples all from the same scenario
  - mechanical structural devices in every reel
  - recap openings
  - domain voice that feels like one repeated machine
- Generic filler anywhere in the module (intros, recaps, transitions).
- Student Confusion Layer (80% serious learner): Does the module jump too fast? Does each lesson prepare the next? Is progression natural? Flag missing bridges/prerequisites that would lose most learners — ignore rare textbook expansion demands.
- Master Creator-Academic Mentor: module energy curve, repetition, transitions, where strong moments should land — advise without cloning any real creator.

## Output

Call the `review_result` tool, `scope` = "module".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse `ReviewAction` per issue - `target_id` = the module's `module_id`, or a specific reel's `reel_id` if the issue is local to one reel, short `reason_code`, one-sentence `instruction`.
