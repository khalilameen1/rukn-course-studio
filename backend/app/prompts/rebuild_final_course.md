# Task: Rebuild the Final Course

Apply `final_review.actions` to `course_map` and `all_reels`, and produce the corrected, export-ready course. This output becomes the DOCX - the only thing the user ever sees.

## Golden rules

- Apply every action exactly, only to the target it names. Leave everything else untouched.
- No generic filler anywhere in the result.
- Keep following every rule in `rules_context` while making corrections.
- Every module from `course_map` must appear, in order, with its final reels and its `bridge_project` if it has one.
- `full_text` must be the complete assembled script: for each module, a `# {module title}` line, then per reel a `## {reel title}` line followed by its script text, then a `[Bridge project] {text}` line if present.

## Output

Call the `final_course` tool. Nothing else - no text outside the tool call.
