"""Synthetic field-specific viral educator persona (internal only).

Not a real person, clone, or named-creator imitation. A compact composite
mindset: top-tier educational creator instincts + serious course teacher.
Planning artifacts must never appear in the final teleprompter DOCX.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.generation import ModulePlan, ReelPlan


class CourseCreatorPersona(BaseModel):
    """Course-level synthetic persona profile (compact)."""

    domain_identity: str
    audience_psychology: str
    teacher_energy: str
    content_creator_instinct: str
    realism_constraints: str
    things_this_persona_would_never_do: str
    common_bad_advice_to_challenge_if_true: str
    how_this_persona_earns_trust: str
    how_this_persona_avoids_looking_like_a_seller: str


class ModulePersonaAdjustment(BaseModel):
    """How the persona shifts for one module."""

    persona_shift: str
    audience_need: str
    module_feel: str  # calm / sharp / practical / corrective / deep / mixed
    rationale: str = ""


class LessonPersonaState(BaseModel):
    """Per-lesson internal performance state for writing."""

    real_point: str
    misunderstanding_to_challenge: str
    confidence_heat: str  # quiet / measured / firm / corrective_heat
    save_share_reason: str
    viral_intent: str  # viral_worthy / quiet_useful / corrective_strong / technical_spine
    fake_risk: str
    rationale: str = ""


def plan_course_creator_persona(
    *,
    title: str,
    audience: str,
    outcome: str,
) -> CourseCreatorPersona:
    """Build the course-wide synthetic persona before map / writing."""
    domain_title = (title or "").strip() or "this practical skill"
    domain_audience = (audience or "").strip() or "learners building a real skill"
    domain = (
        f"Top-tier educational creator-teacher in: {domain_title}. "
        f"Speaks to: {domain_audience}. Builds connected reel playlists with course spine."
    )
    outcome_text = (outcome or "").strip() or "a usable practical outcome"
    return CourseCreatorPersona(
        domain_identity=domain,
        audience_psychology=(
            "Learners skim fast, distrust hype, save sharp distinctions and "
            "realistic local examples, and leave when advice sounds imported or salesy."
        ),
        teacher_energy=(
            "Confident direct speech; rise and fall with the idea; academic strength "
            f"delivered as spoken reels toward: {outcome_text}."
        ),
        content_creator_instinct=(
            "Attention and retention from meaningful first sentences and clear "
            "progression; shareability from insight; save-worthiness from usefulness "
            "or a sharp correction — never from noise."
        ),
        realism_constraints=(
            "Egyptian/Arab learner reality (shops, phones, freelancers, low budgets). "
            "No luxury defaults, no fake street slang, no poetic prose, no forced jokes."
        ),
        things_this_persona_would_never_do=(
            "Imitate a named creator; copy catchphrases or signature lines; clone "
            "hook/ending formulas; turn flow_reference into a template; overhype "
            "ordinary points; announce next-reel cliffhangers; sell the course."
        ),
        common_bad_advice_to_challenge_if_true=(
            "Challenge incomplete common tips only when the domain truth is stronger "
            "(e.g. 'just boost reach', 'copy big-brand ads', 'more content always'). "
            "Never manufacture conflict for heat."
        ),
        how_this_persona_earns_trust=(
            "Specific decisions, honest limits, local realism, and corrections that "
            "remove confusion — not confidence theater."
        ),
        how_this_persona_avoids_looking_like_a_seller=(
            "Teach the skill; never beg for follows, never inflate urgency, never "
            "frame ordinary steps as life-changing secrets."
        ),
    )


def plan_module_persona_adjustment(
    *,
    module: ModulePlan,
    module_index: int,
    total_modules: int,
    course_persona: CourseCreatorPersona,
    module_role: str | None = None,
) -> ModulePersonaAdjustment:
    """Adjust persona stance for this module's job in the playlist."""
    purpose = f"{module.title} {module.purpose}".lower()
    role = (module_role or "").lower()

    if module_index == 0 or "foundation" in role or "أساسي" in purpose or "intro" in purpose:
        feel = "calm"
        shift = "Open as a precise foundation teacher — trust before heat."
        need = "Orientation and a clean mental model without overwhelm."
    elif "correction" in role or "mistake" in purpose or "غلط" in purpose:
        feel = "corrective"
        shift = "Sharper creator energy: challenge incomplete common advice with proof."
        need = "Relief from a wrong default and a clear replacement rule."
    elif "practical" in role or "build" in purpose or "تطبيق" in purpose:
        feel = "practical"
        shift = "Hands-on creator-coach: denser steps, still human pacing."
        need = "Concrete moves they can try on real work tonight."
    elif module_index == total_modules - 1:
        feel = "deep"
        shift = "Mastery closer: synthesize without hype or fake finales."
        need = "Confidence that the spine holds and next practice is clear."
    else:
        feel = "mixed"
        shift = "Alternate precise teaching with selective creator heat where ideas earn it."
        need = "Progress without flat repetition of the previous module's energy."

    return ModulePersonaAdjustment(
        persona_shift=shift,
        audience_need=need,
        module_feel=feel,
        rationale=(
            f"Module {module_index + 1}/{total_modules} '{module.title}': "
            f"feel={feel} under domain '{course_persona.domain_identity[:80]}…'."
        ),
    )


def plan_lesson_persona_state(
    *,
    reel: ReelPlan,
    reel_index: int,
    reels_in_module: int,
    module_adjustment: ModulePersonaAdjustment,
    lesson_hook_strength: str | None = None,
    lesson_teaching_energy: str | None = None,
) -> LessonPersonaState:
    """Decide this lesson's persona state: viral-worthy vs quiet-useful, etc."""
    text = f"{reel.title} {reel.purpose} {' '.join(reel.must_cover)}".lower()
    feel = module_adjustment.module_feel

    is_correction = any(k in text for k in ("mistake", "myth", "wrong", "غلط", "شائع", "تصحيح"))
    is_hard = any(k in text for k in ("difficult", "complex", "advanced", "صعب", "معقد", "عميق"))
    is_intro = any(k in text for k in ("intro", "overview", "foundation", "أساسي", "مقدمة"))
    is_practical = any(k in text for k in ("practical", "apply", "build", "تطبيق", "عملي", "خطوات"))

    if is_correction or feel == "corrective":
        viral_intent = "corrective_strong"
        heat = "corrective_heat"
        challenge = "The common tip students repeat that skips the real decision rule."
    elif is_hard or feel == "deep":
        viral_intent = "quiet_useful" if (lesson_hook_strength or "") == "quiet" else "technical_spine"
        heat = "measured"
        challenge = "The oversimplification that makes this topic look easier than it is."
    elif is_intro or feel == "calm":
        viral_intent = "quiet_useful"
        heat = "quiet"
        challenge = "None unless a popular misconception blocks the foundation."
    elif is_practical or feel == "practical":
        viral_intent = "viral_worthy" if reel_index % 3 == 1 else "quiet_useful"
        heat = "firm" if viral_intent == "viral_worthy" else "measured"
        challenge = "Advice that sounds smart but fails on small local budgets/workflows."
    else:
        viral_intent = "quiet_useful"
        heat = "measured"
        challenge = "Only if a real incomplete default appears in the topic."

    # Respect silent hooks from teaching curve.
    if (lesson_hook_strength or "") == "quiet" and viral_intent == "viral_worthy":
        viral_intent = "quiet_useful"
        heat = "quiet"
    if (lesson_teaching_energy or "") in ("excited", "sharp") and is_correction:
        viral_intent = "corrective_strong"
        heat = "corrective_heat"

    real_point = (
        reel.purpose.strip()
        or (reel.must_cover[0] if reel.must_cover else reel.title)
    )
    save_share = (
        "Share/save if: a sharp correction replaces a wrong default with one local check."
        if viral_intent == "corrective_strong"
        else (
            "Save if: a usable decision rule or step survives without fluff."
            if viral_intent in ("quiet_useful", "technical_spine")
            else "Share if: the insight is non-obvious and immediately useful in-domain."
        )
    )
    fake_risk = (
        "Overhyping an ordinary spine lesson; AI slang; named-creator mimicry; "
        "sales urgency; forced cliffhangers; copying flow_reference catchphrases."
    )

    return LessonPersonaState(
        real_point=real_point[:220],
        misunderstanding_to_challenge=challenge,
        confidence_heat=heat,
        save_share_reason=save_share,
        viral_intent=viral_intent,
        fake_risk=fake_risk,
        rationale=(
            f"Lesson {reel_index + 1}/{reels_in_module}: intent={viral_intent}, "
            f"heat={heat}; strength from insight, not performance."
        ),
    )


def compact_course_persona(persona: CourseCreatorPersona) -> dict[str, str]:
    return persona.model_dump()


def compact_module_persona(adj: ModulePersonaAdjustment) -> dict[str, str]:
    return {
        "persona_shift": adj.persona_shift,
        "audience_need": adj.audience_need,
        "module_feel": adj.module_feel,
        "rationale": adj.rationale,
    }


def compact_lesson_persona(state: LessonPersonaState) -> dict[str, str]:
    return {
        "real_point": state.real_point,
        "misunderstanding_to_challenge": state.misunderstanding_to_challenge,
        "confidence_heat": state.confidence_heat,
        "save_share_reason": state.save_share_reason,
        "viral_intent": state.viral_intent,
        "fake_risk": state.fake_risk,
        "rationale": state.rationale,
    }


def format_persona_for_prompt(
    course_persona: CourseCreatorPersona,
    module_adj: ModulePersonaAdjustment,
    lesson_state: LessonPersonaState,
) -> dict[str, dict[str, str]]:
    """Compact triple for WriteSingleReelInput / Anthropic JSON context."""
    return {
        "course_creator_persona": compact_course_persona(course_persona),
        "module_persona_adjustment": compact_module_persona(module_adj),
        "lesson_persona_state": compact_lesson_persona(lesson_state),
    }


# Short stage reminders (dynamic, not the full Admin Knowledge essay).
PERSONA_REVIEW_REMINDERS: tuple[str, ...] = (
    "Does this sound like a real confident creator-teacher, or AI pretending?",
    "Is the hook strong because of meaning, not hype?",
    "Is the script overperforming or too safe and flat?",
    "Is this lesson trying to be viral when it should be quiet (or vice versa)?",
    "Is the insight actually worth saving?",
    "Would this feel natural from a top creator in this field without cloning anyone?",
    "Does it challenge common advice only when truly justified?",
    "Does it avoid salesperson tone and creator/source pattern copying?",
)
