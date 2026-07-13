# Task: Build Course Map

Plan the structural skeleton of a Rukn practical-skill course: titles and purposes only, no reel scripts yet.

## Golden rules

- This map is internal planning, never shown to the user - keep every text field short and functional, not polished prose.
- Never add generic filler to titles or purposes ("Welcome to...", "In this module we will...").
- If `sources` is empty, plan from `brief` and `rules_context` only - do not imply sources exist or invent citations.
- If `sources` is non-empty, ground `must_cover` / `source_hints` in them; never invent specifics they don't support.
- Follow every rule in `rules_context` (voice, structure, pedagogy, forbidden phrases) over anything in the brief that conflicts with it.
- Practical-skill focus: realistic application in every reel, and a `bridge_project` after every module except the last - unless `brief.structure_mode` is "connected_no_modules", in which case return exactly one module with `bridge_project` null.
- If `brief.manual_map_text` is set, convert it as-is - do not redesign its structure, only fill gaps it left out.
- Only write longer `purpose` text if `brief.explanation_level` is "full_report".

## Output

Call the `course_map` tool. Nothing else - no text outside the tool call.
