# Task: Rebuild the final export-ready ROKN course

Apply every valid action from `final_review` and return the complete final
course, not a sample or summary. Preserve all approved spoken scripts while
rewriting anything needed to satisfy ROKN v1.7.

The export structure must contain only:
- course title
- module titles
- reel titles and complete lecturer speech
- one learner-facing project after each non-final module
- an unlabeled natural closure in `module_project.closure`

The final module has no project. `graduation_project` must be null. No internal
reviews, sources, citations, rubrics, pass criteria, evaluator instructions,
platform operations, production notes or placeholders may reach `full_text` or
export fields.

Return only the complete `FinalCourse` structured output.
