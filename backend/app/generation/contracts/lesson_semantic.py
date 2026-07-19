"""Lesson semantic contract and conservative filler/meaning gates."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.models.enums import LessonDeliveryMode
from app.schemas.generation import (
    CourseMap,
    LessonSemanticContract,
    ModulePlan,
    ReelPlan,
)

_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "into",
    "lesson",
    "student",
    "learner",
    "course",
    "module",
    "because",
    "without",
    "الدرس",
    "الكورس",
    "الطالب",
    "اللي",
    "على",
    "من",
    "إلى",
    "الى",
    "في",
    "وده",
}
_GENERIC_VALUES = {
    "teaching outcome",
    "important concept",
    "learn more",
    "apply the skill",
    "do the task",
    "example",
    "next lesson",
    "مفهوم مهم",
    "طبق المهارة",
    "مثال",
    "الدرس التالي",
}
_SPOKEN_REQUIRED_FIELDS = (
    "exact_capability_change",
    "strongest_non_obvious_meaning",
    "misconception_or_failure",
    "causal_explanation",
    "proof_example_or_demonstration",
    "learner_test_or_action",
    "boundary_or_exception",
    "real_tension",
    "complete_payoff",
)
_SAFE_FILLER_PATTERNS = (
    re.compile(r"^(?:ببساطة|بكل بساطة|خلينا نبدأ|ركز معايا|الموضوع بسيط)[.!،, ]*$", re.I),
    re.compile(r"^(?:as you know|simply put|let'?s begin|this is very important)[.! ]*$", re.I),
)


@dataclass
class SemanticContractValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


@dataclass
class SemanticScriptReport:
    ok: bool
    missing_fields: list[str] = field(default_factory=list)
    filler_lines: list[str] = field(default_factory=list)


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(value or "")
        if len(token) >= 3 and token.casefold() not in _STOPWORDS
    }


def _specific(value: str, *, allow_state_label: bool = False) -> bool:
    normalized = " ".join((value or "").casefold().split())
    minimum_tokens = 1 if allow_state_label else 2
    minimum_length = 3 if allow_state_label else 8
    return (
        len(normalized) >= minimum_length
        and normalized not in _GENERIC_VALUES
        and len(_tokens(value)) >= minimum_tokens
    )


def _capability(reel: ReelPlan) -> str:
    return (
        reel.new_skill_or_decision
        or reel.distinct_teaching_outcome
        or reel.purpose
        or reel.title
    ).strip()


def build_lesson_semantic_contract(
    course_map: CourseMap,
    module: ModulePlan,
    reel: ReelPlan,
    *,
    previous_reel: ReelPlan | None = None,
    next_reel: ReelPlan | None = None,
) -> LessonSemanticContract:
    if reel.lesson_semantic_contract is not None:
        return reel.lesson_semantic_contract

    capability = _capability(reel)
    direct_arabic = bool(
        course_map.thesis is not None
        and str(course_map.thesis.student_language or "").lower().startswith("ar")
    )
    cover = [item.strip() for item in reel.must_cover if item.strip()]
    avoid = [item.strip() for item in reel.must_avoid if item.strip()]
    core = cover[0] if cover else capability
    support = cover[1] if len(cover) > 1 else capability
    prior_after = (
        previous_reel.student_can_do_after
        if previous_reel is not None
        else (
            course_map.thesis.learner_starting_state
            if course_map.thesis is not None
            else (
                "حالة المتعلم المعلنة في البريف"
                if direct_arabic
                else "the declared learner starting state"
            )
        )
    )
    if not _specific(prior_after, allow_state_label=True):
        prior_after = (
            f"حالة المتعلم المعلنة بوضوح {prior_after or 'غير محددة'}"
            if direct_arabic
            else (
                "the explicitly declared learner starting state: "
                f"{prior_after or 'not specified'}"
            )
        )
    learner_after = reel.student_can_do_after or reel.distinct_teaching_outcome or capability
    failure = avoid[0] if avoid else (
        f"تطبّق {capability} من غير شرط {core}"
        if direct_arabic
        else f"Applying {capability} while ignoring the condition {core}"
    )
    visual = (reel.internal_visual_plan or "").strip()
    if visual:
        proof = (
            f"{visual} وبيّن أثر {core} وانت بتنفذ {capability}"
            if direct_arabic
            else f"{visual}; demonstrate {core} while performing {capability}"
        )
    elif reel.delivery_mode in {
        LessonDeliveryMode.SCREEN_DEMO,
        LessonDeliveryMode.PROJECT_BUILD,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.DESIGN_CRITIQUE,
        LessonDeliveryMode.CRITIQUE,
    }:
        proof = (
            f"اعرض {core} وقارن النتيجة الظاهرة قبل وبعد"
            if direct_arabic
            else f"Demonstrate {core} and compare the observable result before and after"
        )
    else:
        proof = (
            f"استخدم حالة عملية يتغير فيها قرار {capability} بسبب {core}"
            if direct_arabic
            else f"Use one concrete case where {core} changes the decision {capability}"
        )
    if next_reel is not None:
        next_capability = _capability(next_reel)
        earned_next = (
            f"لما يكمّل {capability} تبقى نتيجته مدخل مطلوب عشان {next_capability}"
            if direct_arabic
            else (
                f"Once {capability} is complete, its result becomes the input needed "
                f"for {next_capability}"
            )
        )
    else:
        earned_next = (
            f"بعد إتقان {capability} يقدر المتعلم يستخدمه في "
            f"{reel.project_contribution or 'مشروع الموديول'}"
            if direct_arabic
            else (
                f"Once {capability} is complete, the learner can use it in "
                f"{reel.project_contribution or 'the module project'}"
            )
        )
    module_reels = list(module.reels)
    index = next(
        (i for i, candidate in enumerate(module_reels) if candidate.reel_id == reel.reel_id),
        0,
    )
    if index == 0:
        escalation = (
            f"يثبت أساس قرار الموديول من خلال {capability}"
            if direct_arabic
            else f"establish the module decision foundation through {capability}"
        )
    elif index == len(module_reels) - 1:
        escalation = (
            f"يدمج {capability} في تسليم الموديول"
            if direct_arabic
            else f"integrate {capability} into the module deliverable"
        )
    else:
        escalation = (
            f"يزود استقلال المتعلم بتطبيق {capability} تحت شرط جديد"
            if direct_arabic
            else f"increase independence by applying {capability} under a new condition"
        )
    prerequisite = list(reel.prerequisite_lesson_ids)
    if prerequisite:
        dependency = (
            f"يحتاج نتيجة {', '.join(prerequisite)} قبل {capability}"
            if direct_arabic
            else f"Requires the result of {', '.join(prerequisite)} before {capability}"
        )
    elif previous_reel is not None:
        dependency = (
            f"يستخدم ناتج {previous_reel.reel_id} كحالة سابقة قبل {capability}"
            if direct_arabic
            else f"Uses {previous_reel.reel_id} as the prior state for {capability}"
        )
    else:
        dependency = (
            f"يبدأ من {prior_after} ويدخل {capability}"
            if direct_arabic
            else f"Starts from {prior_after} and introduces {capability}"
        )

    if direct_arabic:
        return LessonSemanticContract(
            learner_before=prior_after,
            learner_after=learner_after,
            exact_capability_change=(
                f"ينقل المتعلم من {prior_after} لتنفيذ {capability} لوحده"
            ),
            strongest_non_obvious_meaning=(
                f"قيمة {core} بتبان لما تغيّر {support} جوه {capability}"
            ),
            misconception_or_failure=failure,
            causal_explanation=(
                f"{core} بتغيّر النتيجة لأنها بتتحكم في {support} أثناء {capability}"
            ),
            proof_example_or_demonstration=proof,
            learner_test_or_action=(
                f"نفّذ {capability} وراجع {core} واشرح الفرق اللي ظهر"
            ),
            boundary_or_exception=(
                f"متعممش {capability} في الحالة دي {failure}"
            ),
            real_tension=(
                f"تحافظ على {core} وانت بتنفذ {capability}"
            ),
            complete_payoff=(
                f"المتعلم يكمّل {capability} ويطلع "
                f"{reel.project_contribution or learner_after}"
            ),
            earned_next_need=earned_next,
            escalation_role=escalation,
            sequence_dependency=dependency,
        )

    return LessonSemanticContract(
        learner_before=prior_after,
        learner_after=learner_after,
        exact_capability_change=(
            f"Change from {prior_after} to independently performing {capability}"
        ),
        strongest_non_obvious_meaning=(
            f"{core} only creates value when it changes {support} inside {capability}"
        ),
        misconception_or_failure=failure,
        causal_explanation=(
            f"{core} changes the outcome because it controls {support} in {capability}"
        ),
        proof_example_or_demonstration=proof,
        learner_test_or_action=(
            f"Perform {capability}, verify {core}, and explain the observed difference"
        ),
        boundary_or_exception=(
            f"Do not generalize {capability} when {failure} applies"
        ),
        real_tension=(
            f"The learner must preserve {core} without causing {failure}"
        ),
        complete_payoff=(
            f"The learner completes {capability} and produces "
            f"{reel.project_contribution or learner_after}"
        ),
        earned_next_need=earned_next,
        escalation_role=escalation,
        sequence_dependency=dependency,
    )


def validate_lesson_semantic_contract(
    contract: LessonSemanticContract,
    reel: ReelPlan,
    *,
    peer_contracts: list[LessonSemanticContract] | None = None,
) -> SemanticContractValidation:
    errors: list[str] = []
    values = contract.model_dump()
    for name, value in values.items():
        if not _specific(
            str(value),
            allow_state_label=name in {"learner_before", "learner_after"},
        ):
            errors.append(f"{reel.reel_id}: {name} is generic or empty")

    anchor_tokens = _tokens(
        " ".join(
            [
                reel.title,
                reel.purpose,
                reel.distinct_teaching_outcome,
                reel.new_skill_or_decision,
                *reel.must_cover,
            ]
        )
    )
    for name in (
        "exact_capability_change",
        "strongest_non_obvious_meaning",
        "causal_explanation",
        "proof_example_or_demonstration",
        "learner_test_or_action",
        "complete_payoff",
    ):
        if anchor_tokens and not (_tokens(str(values[name])) & anchor_tokens):
            errors.append(f"{reel.reel_id}: {name} is interchangeable with another lesson")

    normalized_capability = " ".join(contract.exact_capability_change.casefold().split())
    for peer in peer_contracts or []:
        if " ".join(peer.exact_capability_change.casefold().split()) == normalized_capability:
            errors.append(
                f"{reel.reel_id}: exact_capability_change duplicates another lesson"
            )
            break
    return SemanticContractValidation(ok=not errors, errors=errors)


def attach_lesson_semantic_contracts(
    course_map: CourseMap,
    *,
    force_rebuild: bool = False,
) -> CourseMap:
    """Attach and validate every contract before the first lesson write."""
    flat = [reel for module in course_map.modules for reel in module.reels]
    contracts: list[LessonSemanticContract] = []
    modules: list[ModulePlan] = []
    flat_index = {reel.reel_id: index for index, reel in enumerate(flat)}
    for module in course_map.modules:
        reels: list[ReelPlan] = []
        for reel in module.reels:
            index = flat_index[reel.reel_id]
            contract_reel = (
                reel.model_copy(update={"lesson_semantic_contract": None})
                if force_rebuild
                else reel
            )
            contract = build_lesson_semantic_contract(
                course_map,
                module,
                contract_reel,
                previous_reel=flat[index - 1] if index > 0 else None,
                next_reel=flat[index + 1] if index + 1 < len(flat) else None,
            )
            validation = validate_lesson_semantic_contract(
                contract,
                reel,
                peer_contracts=contracts,
            )
            validation.raise_if_invalid()
            contracts.append(contract)
            reels.append(reel.model_copy(update={"lesson_semantic_contract": contract}))
        modules.append(module.model_copy(update={"reels": reels}))
    return course_map.model_copy(update={"modules": modules})


def inspect_script_against_semantic_contract(
    script_text: str,
    contract: LessonSemanticContract,
) -> SemanticScriptReport:
    script_tokens = _tokens(script_text)
    field_tokens = {
        name: _tokens(str(getattr(contract, name)))
        for name in _SPOKEN_REQUIRED_FIELDS
    }
    token_frequency = Counter(
        token
        for anchors in field_tokens.values()
        for token in anchors
    )
    missing: list[str] = []
    for name in _SPOKEN_REQUIRED_FIELDS:
        anchors = field_tokens[name]
        distinctive = {
            token for token in anchors if token_frequency[token] <= 2
        }
        evidence = distinctive or anchors
        if evidence and len(evidence & script_tokens) < min(2, len(evidence)):
            missing.append(name)

    filler: list[str] = []
    semantic_tokens = set().union(
        *(_tokens(str(value)) for value in contract.model_dump().values())
    )
    seen_lines: set[str] = set()
    for raw in (script_text or "").splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        normalized = line.casefold()
        duplicate = normalized in seen_lines
        seen_lines.add(normalized)
        safe_pattern = any(pattern.match(line) for pattern in _SAFE_FILLER_PATTERNS)
        if duplicate or (safe_pattern and not (_tokens(line) & semantic_tokens)):
            filler.append(line)
    return SemanticScriptReport(
        ok=not missing and not filler,
        missing_fields=missing,
        filler_lines=filler,
    )


def remove_safe_semantic_filler(
    script_text: str,
    contract: LessonSemanticContract,
) -> tuple[str, list[str]]:
    """Delete only provably redundant/template lines; never compress meaning."""
    before = inspect_script_against_semantic_contract(script_text, contract)
    if not before.filler_lines:
        return script_text, []
    semantic_tokens = set().union(
        *(_tokens(str(value)) for value in contract.model_dump().values())
    )
    seen: set[str] = set()
    kept: list[str] = []
    removed: list[str] = []
    for raw in script_text.splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        normalized = line.casefold()
        duplicate = normalized in seen
        safe_pattern = any(pattern.match(line) for pattern in _SAFE_FILLER_PATTERNS)
        if duplicate or (safe_pattern and not (_tokens(line) & semantic_tokens)):
            removed.append(line)
            continue
        seen.add(normalized)
        kept.append(raw)
    candidate = "\n".join(kept).strip()
    after = inspect_script_against_semantic_contract(candidate, contract)
    if set(after.missing_fields) - set(before.missing_fields):
        return script_text, []
    return candidate, removed


__all__ = [
    "SemanticContractValidation",
    "SemanticScriptReport",
    "attach_lesson_semantic_contracts",
    "build_lesson_semantic_contract",
    "inspect_script_against_semantic_contract",
    "remove_safe_semantic_filler",
    "validate_lesson_semantic_contract",
]
