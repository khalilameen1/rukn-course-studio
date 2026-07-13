# Task: Final Full-Course Review

Last check before export. Re-verify the whole course yourself - do not assume every earlier stage caught everything. The user will only ever see the final DOCX; this is the last chance to catch a problem before it reaches them.

## Check for

- Repetition anywhere across the whole course (examples, openings, ideas).
- Slow depth/effort drift from the first module to the last - laziness that adjacent-pair checks can miss.
- Any claim not grounded in `sources` when sources were provided, or any invented specific when they weren't.
- Full `rules_context` compliance, including forbidden phrases and structure/pedagogy rules.
- Whether the course actually delivers on `course_map.main_thread`, front to back.

## Output

Call the `review_result` tool, `scope` = "final".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse, concrete `ReviewAction` per issue - `target_id` = the affected `module_id` or `reel_id`, short `reason_code`, one-sentence `instruction`. `rebuild_final_course` will execute these exactly, so make each one actionable.
