"""Deterministic lesson/module/adjacent/course review with blocking findings.

Unlike the retired log-only AI checkpoints, every fatal or serious finding
returned here is consumed by the export gate.  The course therefore cannot be
accepted until the affected lesson is rewritten or the map/project is revised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from app.schemas.generation import CourseMap, GeneratedReel, LessonSemanticContract
from app.validators.similarity import text_similarity

_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_GENERIC_COLLAPSE = re.compile(
    r"(?:important concept|learn more|apply the skill|do the task|"
    r"مفهوم مهم|معلومة مهمة|ببساطة(?: شديدة)?|الموضوع بسيط|طبق المهارة)",
    re.IGNORECASE,
)
_NEGATION_MARKERS = (
    "never ",
    "always ",
    "do not ",
    "don't ",
    "ممنوع ",
    "ما تعملش ",
    "دايما ",
    "دائمًا ",
)


@dataclass(frozen=True)
class CrossScopeFinding:
    scope: str
    code: str
    detail: str
    target_reel_ids: tuple[str, ...] = ()
    severity: str = "serious"
    required_action: str = "rewrite"


@dataclass
class CrossScopeReport:
    findings: list[CrossScopeFinding] = field(default_factory=list)

    @property
    def blocking_findings(self) -> list[CrossScopeFinding]:
        return [
            finding
            for finding in self.findings
            if finding.severity in {"fatal", "serious"}
        ]

    @property
    def ok(self) -> bool:
        return not self.blocking_findings

    def model_dump(self) -> dict:
        return {
            "ok": self.ok,
            "findings": [
                {
                    "scope": finding.scope,
                    "code": finding.code,
                    "detail": finding.detail,
                    "target_reel_ids": list(finding.target_reel_ids),
                    "severity": finding.severity,
                    "required_action": finding.required_action,
                }
                for finding in self.findings
            ],
        }


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(value or "")
        if len(token) >= 3
    }


def _nonempty_lines(value: str) -> list[str]:
    return [" ".join(line.split()) for line in (value or "").splitlines() if line.strip()]


def _near_duplicate(left: str, right: str, *, threshold: float = 0.9) -> bool:
    if not left.strip() or not right.strip():
        return False
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return False
    containment = len(left_tokens & right_tokens) / max(
        1,
        min(len(left_tokens), len(right_tokens)),
    )
    return containment >= 0.8 and text_similarity(left, right) >= threshold


def _contract_capability(contract: LessonSemanticContract | None) -> str:
    return (contract.exact_capability_change if contract is not None else "").strip()


def _language_ratio(value: str) -> float:
    arabic = len(_ARABIC_RE.findall(value or ""))
    latin = len(_LATIN_RE.findall(value or ""))
    return arabic / max(1, arabic + latin)


def _contradiction_key(line: str) -> tuple[str, bool] | None:
    normalized = " ".join(line.casefold().split()).strip(" .،؛:!؟")
    marker = next((item for item in _NEGATION_MARKERS if normalized.startswith(item)), None)
    if marker is None:
        return None
    negative = marker.startswith(("never", "do not", "don't", "ممنوع", "ما تعملش"))
    key = normalized[len(marker) :].strip()
    return (key, negative) if len(_tokens(key)) >= 3 else None


def _project_alignment_findings(course_map: CourseMap) -> list[CrossScopeFinding]:
    findings: list[CrossScopeFinding] = []
    all_taught: list[str] = []
    for module in course_map.modules:
        taught = " ".join(
            " ".join(
                (
                    reel.new_skill_or_decision,
                    reel.distinct_teaching_outcome,
                    _contract_capability(reel.lesson_semantic_contract),
                )
            )
            for reel in module.reels
        )
        all_taught.append(taught)
        project = module.module_project
        if project is None or not project.skills_tested:
            continue
        taught_tokens = _tokens(taught)
        unmatched = [
            skill
            for skill in project.skills_tested
            if not (_tokens(skill) & taught_tokens)
        ]
        if len(unmatched) == len(project.skills_tested):
            findings.append(
                CrossScopeFinding(
                    scope="module",
                    code="project_teaching_mismatch",
                    detail=(
                        f"Module {module.module_id} project tests no capability "
                        "taught in its lessons; revise the map/project before export."
                    ),
                    target_reel_ids=tuple(reel.reel_id for reel in module.reels),
                    required_action="revise_map_or_project",
                )
            )

    graduation = course_map.graduation_project
    if graduation is not None and graduation.skills_tested:
        taught_tokens = _tokens(" ".join(all_taught))
        if not any(_tokens(skill) & taught_tokens for skill in graduation.skills_tested):
            findings.append(
                CrossScopeFinding(
                    scope="whole_course",
                    code="graduation_project_teaching_mismatch",
                    detail=(
                        "Graduation project tests no capability taught by the course; "
                        "revise the map or project before export."
                    ),
                    required_action="revise_map_or_project",
                )
            )
    return findings


def review_cross_scope(
    *,
    course_map: CourseMap,
    generated_reels: list[GeneratedReel],
) -> CrossScopeReport:
    """Review four scopes and return only actionable, export-blocking findings."""
    report = CrossScopeReport()
    generated_by_id = {reel.reel_id: reel for reel in generated_reels}
    ordered_plans = [reel for module in course_map.modules for reel in module.reels]
    plan_index = {reel.reel_id: index for index, reel in enumerate(ordered_plans)}

    # Lesson scope: accepted lessons must exist, pass, and retain their contract.
    for plan in ordered_plans:
        generated = generated_by_id.get(plan.reel_id)
        if generated is None:
            report.findings.append(
                CrossScopeFinding(
                    scope="lesson",
                    code="missing_generated_lesson",
                    detail=f"Lesson {plan.reel_id} has no generated Final Master.",
                    target_reel_ids=(plan.reel_id,),
                    severity="fatal",
                )
            )
            continue
        if plan.lesson_semantic_contract is None:
            report.findings.append(
                CrossScopeFinding(
                    scope="lesson",
                    code="semantic_contract_missing",
                    detail=f"Lesson {plan.reel_id} lost its frozen semantic contract.",
                    target_reel_ids=(plan.reel_id,),
                    severity="fatal",
                    required_action="revise_map",
                )
            )
        if (generated.quality_status or "").lower() in {"needs_review", "fail"}:
            report.findings.append(
                CrossScopeFinding(
                    scope="lesson",
                    code="unresolved_lesson_finding",
                    detail=f"Lesson {plan.reel_id} still requires a creator rewrite.",
                    target_reel_ids=(plan.reel_id,),
                )
            )

    # Lost prerequisites are a sequence failure, not a cosmetic warning.
    for plan in ordered_plans:
        current = plan_index[plan.reel_id]
        lost = [
            prerequisite
            for prerequisite in plan.prerequisite_lesson_ids
            if prerequisite not in plan_index or plan_index[prerequisite] >= current
        ]
        if lost:
            report.findings.append(
                CrossScopeFinding(
                    scope="lesson",
                    code="lost_prerequisite",
                    detail=(
                        f"Lesson {plan.reel_id} has unavailable/non-prior prerequisites: "
                        + ", ".join(lost)
                    ),
                    target_reel_ids=(plan.reel_id,),
                    required_action="revise_map",
                )
            )

    # Module and adjacent-module scope: semantic, hook, and ending diversity.
    for module_index, module in enumerate(course_map.modules):
        module_plans = list(module.reels)
        module_generated = [
            generated_by_id[plan.reel_id]
            for plan in module_plans
            if plan.reel_id in generated_by_id
        ]
        for index, plan in enumerate(module_plans):
            capability = _contract_capability(plan.lesson_semantic_contract)
            for previous in module_plans[:index]:
                previous_capability = _contract_capability(
                    previous.lesson_semantic_contract
                )
                if capability and _near_duplicate(
                    capability,
                    previous_capability,
                    threshold=0.94,
                ):
                    report.findings.append(
                        CrossScopeFinding(
                            scope="module",
                            code="semantic_duplication",
                            detail=(
                                f"{plan.reel_id} duplicates the capability change "
                                f"of {previous.reel_id}; merge or rewrite the map."
                            ),
                            target_reel_ids=(previous.reel_id, plan.reel_id),
                            required_action="merge_or_rewrite_map",
                        )
                    )
        for index, generated in enumerate(module_generated):
            lines = _nonempty_lines(generated.script_text)
            if not lines:
                continue
            for previous in module_generated[:index]:
                previous_lines = _nonempty_lines(previous.script_text)
                if not previous_lines:
                    continue
                if _near_duplicate(lines[0], previous_lines[0], threshold=0.92):
                    report.findings.append(
                        CrossScopeFinding(
                            scope="module",
                            code="repeated_hook",
                            detail=(
                                f"{generated.reel_id} repeats the opening of "
                                f"{previous.reel_id}; creator rewrite required."
                            ),
                            target_reel_ids=(generated.reel_id,),
                        )
                    )
                if _near_duplicate(lines[-1], previous_lines[-1], threshold=0.92):
                    report.findings.append(
                        CrossScopeFinding(
                            scope="module",
                            code="repeated_ending",
                            detail=(
                                f"{generated.reel_id} repeats the ending of "
                                f"{previous.reel_id}; creator rewrite required."
                            ),
                            target_reel_ids=(generated.reel_id,),
                        )
                    )

        if module_index > 0:
            previous_module = course_map.modules[module_index - 1]
            if previous_module.reels and module.reels:
                left_plan = previous_module.reels[-1]
                right_plan = module.reels[0]
                left = generated_by_id.get(left_plan.reel_id)
                right = generated_by_id.get(right_plan.reel_id)
                if left is not None and right is not None:
                    left_lines = _nonempty_lines(left.script_text)
                    right_lines = _nonempty_lines(right.script_text)
                    if left_lines and right_lines and _near_duplicate(
                        left_lines[0], right_lines[0], threshold=0.92
                    ):
                        report.findings.append(
                            CrossScopeFinding(
                                scope="adjacent_modules",
                                code="repeated_hook",
                                detail=(
                                    f"Boundary lessons {left.reel_id}/{right.reel_id} "
                                    "reuse the same hook; rewrite the latter."
                                ),
                                target_reel_ids=(right.reel_id,),
                            )
                        )
                    if left_lines and right_lines and _near_duplicate(
                        left_lines[-1], right_lines[-1], threshold=0.92
                    ):
                        report.findings.append(
                            CrossScopeFinding(
                                scope="adjacent_modules",
                                code="repeated_ending",
                                detail=(
                                    f"Boundary lessons {left.reel_id}/{right.reel_id} "
                                    "reuse the same ending; rewrite the latter."
                                ),
                                target_reel_ids=(right.reel_id,),
                            )
                        )
                if _near_duplicate(
                    _contract_capability(left_plan.lesson_semantic_contract),
                    _contract_capability(right_plan.lesson_semantic_contract),
                    threshold=0.94,
                ):
                    report.findings.append(
                        CrossScopeFinding(
                            scope="adjacent_modules",
                            code="semantic_duplication",
                            detail=(
                                f"Boundary lessons {left_plan.reel_id}/{right_plan.reel_id} "
                                "teach the same capability; merge or revise the map."
                            ),
                            target_reel_ids=(left_plan.reel_id, right_plan.reel_id),
                            required_action="merge_or_rewrite_map",
                        )
                    )

    report.findings.extend(_project_alignment_findings(course_map))

    ordered_generated = [
        generated_by_id[plan.reel_id]
        for plan in ordered_plans
        if plan.reel_id in generated_by_id
    ]
    if len(ordered_generated) >= 4:
        split = max(1, len(ordered_generated) // 3)
        early = ordered_generated[:split]
        late = ordered_generated[-split:]
        early_words = [len(reel.script_text.split()) for reel in early]
        late_words = [len(reel.script_text.split()) for reel in late]
        if (
            median(late_words) < 24
            and median(late_words) < median(early_words) * 0.55
        ):
            report.findings.append(
                CrossScopeFinding(
                    scope="whole_course",
                    code="late_course_quality_decline",
                    detail=(
                        "Late lessons collapse below the teaching depth established "
                        "early in the course; rewrite the affected Final Masters."
                    ),
                    target_reel_ids=tuple(reel.reel_id for reel in late),
                )
            )
        generic_late = [
            reel.reel_id
            for reel in late
            if _GENERIC_COLLAPSE.search(reel.script_text or "")
        ]
        if len(generic_late) >= max(1, len(late) // 2):
            report.findings.append(
                CrossScopeFinding(
                    scope="whole_course",
                    code="generic_late_course_collapse",
                    detail="Late lessons fall back to generic teaching language.",
                    target_reel_ids=tuple(generic_late),
                )
            )
        early_ratio = median(_language_ratio(reel.script_text) for reel in early)
        late_ratio = median(_language_ratio(reel.script_text) for reel in late)
        if abs(early_ratio - late_ratio) > 0.45:
            report.findings.append(
                CrossScopeFinding(
                    scope="whole_course",
                    code="voice_drift",
                    detail=(
                        "The language/voice profile changes sharply between early "
                        "and late lessons; rewrite the late lessons."
                    ),
                    target_reel_ids=tuple(reel.reel_id for reel in late),
                )
            )
        early_ideas = sum(bool(reel.used_ideas) for reel in early)
        late_ideas = sum(bool(reel.used_ideas) for reel in late)
        if early_ideas == len(early) and late_ideas == 0:
            report.findings.append(
                CrossScopeFinding(
                    scope="whole_course",
                    code="phrase_drift",
                    detail=(
                        "Late lessons stop carrying the declared teaching ideas; "
                        "rewrite them against the lesson ledger."
                    ),
                    target_reel_ids=tuple(reel.reel_id for reel in late),
                )
            )

    contradiction_index: dict[str, tuple[bool, str]] = {}
    for generated in ordered_generated:
        for line in _nonempty_lines(generated.script_text):
            parsed = _contradiction_key(line)
            if parsed is None:
                continue
            key, negative = parsed
            previous = contradiction_index.get(key)
            if previous is not None and previous[0] != negative:
                report.findings.append(
                    CrossScopeFinding(
                        scope="whole_course",
                        code="contradiction",
                        detail=(
                            f"{generated.reel_id} contradicts {previous[1]} on: {key}"
                        ),
                        target_reel_ids=(previous[1], generated.reel_id),
                    )
                )
            else:
                contradiction_index[key] = (negative, generated.reel_id)

    return report


__all__ = [
    "CrossScopeFinding",
    "CrossScopeReport",
    "review_cross_scope",
]
