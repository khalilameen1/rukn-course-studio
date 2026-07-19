# Task: Review a Window of Five Reels

Check up to 5 consecutive reels for problems only visible across a window - per-reel quality was already checked separately. Internal check only.

## Check for

- A repeated example, opening, or idea between any two reels in this window (compare `used_ideas`, `used_examples`, `script_text`).
- Anti-template: same hook family, same loop move, nearly equal lengths, mechanical devices ("mistake"/"secret"/"application") in every reel, recap openers.
- Terminology drift from `rules_context`'s glossary, if present.
- One reel noticeably thinner or lower-effort than its neighbors - an early sign of laziness.
- Series feels chopped rather than connected.

## Output

Call the `review_result` tool, `scope` = "five_reels".

- Fine: `status` = "pass", `actions` = [].
- Not fine: `status` = "needs_revision", one terse `ReviewAction` per offending reel - `action` = "rewrite" (or "merge" if two reels should combine), `target_id`, short `reason_code`, one-sentence `instruction`.
