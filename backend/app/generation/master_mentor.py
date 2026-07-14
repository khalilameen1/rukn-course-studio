"""Master Creator-Academic Mentor — synthetic advisor (internal only).

Not a real named creator. Does not write instead of the course creator.
Advises on hooks, loops, pacing, retention, academic nuance, and dignity.
Never appears in final teleprompter DOCX or normal UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field


class MentorReview(BaseModel):
    """Compact internal mentor_review (never user-facing / never DOCX)."""

    strongest_hidden_angle: str = ""
    hook_advice: str = ""
    pacing_advice: str = ""
    loop_advice: str = ""
    academic_gap: str = ""
    content_instinct_note: str = ""
    what_to_make_bolder: str = ""
    what_to_make_quieter: str = ""
    what_to_remove: str = ""
    rebuild_instruction: str = ""


MENTOR_LEAK_SUBSTRINGS: tuple[str, ...] = (
    "mentor_review",
    "strongest_hidden_angle",
    "hook_advice",
    "pacing_advice",
    "loop_advice",
    "academic_gap",
    "content_instinct_note",
    "what_to_make_bolder",
    "what_to_make_quieter",
    "rebuild_instruction",
    "master creator-academic mentor",
    "consulting master mentor",
)

# Local heuristics that echo mentor advice directions (tests + optional local review).
FORCED_LOOP_CUE = re.compile(
    r"(في الريل الجاي|في الجزء الجاي|in the next reel|stay tuned)",
    re.IGNORECASE,
)
OVERHYPE_CUE = re.compile(
    r"(السر اللي محدش|هيغير حيات|أخطر حاجة|أكبر غلط|biggest mistake|most dangerous)",
    re.IGNORECASE,
)
SUBTLE_ACADEMIC_GAP_CUE = re.compile(
    r"(always works|دائماً بيشتغل|مفيش استثناء|100% guaranteed)",
    re.IGNORECASE,
)


@dataclass
class MentorAdviceIssue:
    reason_code: str
    detail: str


def mentor_advice_hints_for_script(script_text: str) -> list[MentorAdviceIssue]:
    """Lightweight local mentor-shaped hints (no named-creator imitation)."""
    text = script_text or ""
    issues: list[MentorAdviceIssue] = []

    if OVERHYPE_CUE.search(text):
        issues.append(
            MentorAdviceIssue(
                reason_code="mentor_quieter_hook",
                detail=(
                    "Mentor: opening leans on hype — prefer a quieter first sentence "
                    "whose meaning stops the right viewer; do not overperform."
                ),
            )
        )

    if FORCED_LOOP_CUE.search(text):
        issues.append(
            MentorAdviceIssue(
                reason_code="mentor_no_fake_loop",
                detail=(
                    "Mentor: ending uses a fake next-part loop — close cleanly or "
                    "pull the next lesson with a real unresolved need, no announcement."
                ),
            )
        )

    if SUBTLE_ACADEMIC_GAP_CUE.search(text):
        issues.append(
            MentorAdviceIssue(
                reason_code="mentor_academic_gap",
                detail=(
                    "Mentor: absolute claim may hide a domain nuance — add the condition "
                    "or exception the specialist might miss because the draft sounds smooth."
                ),
            )
        )

    if re.search(r"(يا معلم يا برنس|يا نجم السوشيال)", text):
        issues.append(
            MentorAdviceIssue(
                reason_code="mentor_dignity",
                detail=(
                    "Mentor: theatrical slang sounds like acting — keep clean spoken "
                    "Egyptian with natural confidence, no costume performance."
                ),
            )
        )

    return issues


def mentor_advises_bolder(review: MentorReview) -> bool:
    return bool((review.what_to_make_bolder or "").strip())


def mentor_advises_quieter(review: MentorReview) -> bool:
    return bool((review.what_to_make_quieter or "").strip()) or "quiet" in (
        review.hook_advice or ""
    ).lower()


def mentor_advises_no_fake_loop(review: MentorReview) -> bool:
    blob = f"{review.loop_advice} {review.rebuild_instruction}".lower()
    return any(k in blob for k in ("no loop", "fake loop", "clean close", "no_loop"))


def mentor_forbids_named_creator_imitation(text: str) -> bool:
    """True when text clearly tries to clone a named creator / catchphrase pattern."""
    return bool(
        re.search(
            r"(زي ما بيقول\s+\w+|copy\s+\w+'s\s+style|signature catchphrase|imitate\s+creator)",
            text or "",
            re.IGNORECASE,
        )
    )
