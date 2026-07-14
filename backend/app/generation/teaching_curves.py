"""Dynamic Teaching Curve planning (internal only).

Before each module and each lesson/reel, plan a compact `module_curve` /
`lesson_curve` so writing follows a human teacher's rise-and-fall rather than
one fixed depth/voice/length/energy for the whole course.

These artifacts guide prompts and local variation checks. They must never
appear in the final teleprompter DOCX.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.generation import ModulePlan, ReelPlan

# --- Allowed planning labels (decisions, not section templates) ------------

MODULE_ROLES: tuple[str, ...] = (
    "foundation",
    "correction",
    "practical_build",
    "deepening",
    "synthesis",
    "transition",
    "mastery",
)

MODULE_ENERGY_CURVES: tuple[str, ...] = (
    "calm_start",
    "rising",
    "alternating",
    "intense_middle",
    "quiet_precision",
    "practical_momentum",
    "reflective_close",
)

MODULE_DEPTH_PATTERNS: tuple[str, ...] = (
    "light_to_deep",
    "deep_to_practical",
    "alternating",
    "mostly_practical",
    "mostly_corrective",
)

NATURAL_LENGTHS: tuple[str, ...] = ("short", "medium", "long", "extended")
NATURAL_DEPTHS: tuple[str, ...] = ("light", "standard", "deep", "very_deep")
TEACHING_ENERGIES: tuple[str, ...] = (
    "calm",
    "precise",
    "practical",
    "analytical",
    "sharp",
    "warm",
    "excited",
    "restrained",
)
TENSION_CURVES: tuple[str, ...] = (
    "flat_clear",
    "soft_rise",
    "strong_rise",
    "shock_then_explain",
    "confusion_to_clarity",
    "pressure_then_relief",
)
SPEECH_DENSITIES: tuple[str, ...] = ("low", "medium", "high")
EXPLANATION_MODES: tuple[str, ...] = (
    "direct_explanation",
    "example_first",
    "mistake_correction",
    "demonstration",
    "comparison",
    "mental_model",
    "case_breakdown",
)
HOOK_STRENGTHS: tuple[str, ...] = ("quiet", "medium", "strong")
ENDING_MOTIONS: tuple[str, ...] = (
    "clean_close",
    "soft_next_need",
    "unresolved_practical_need",
    "natural_transition",
    "no_loop_needed",
)


class ModuleCurve(BaseModel):
    """Compact module-level teaching/performance curve (internal)."""

    module_role: str
    module_energy_curve: str
    module_depth_pattern: str
    module_variation_goal: str
    module_risk: str
    rationale: str = ""


class LessonCurve(BaseModel):
    """Compact lesson/reel teaching curve (internal)."""

    natural_length: str
    natural_depth: str
    teaching_energy: str
    tension_curve: str
    speech_density: str
    explanation_mode: str
    hook_strength: str
    hook_reason: str
    ending_motion: str
    compression_decision: str
    expansion_decision: str
    rationale: str = ""


class CurveNeighbor(BaseModel):
    """Minimal prev/next context for curve planning (avoid full script dump)."""

    reel_id: str
    title: str
    purpose: str = ""


def _pick(options: tuple[str, ...], index: int) -> str:
    return options[index % len(options)]


def _topic_signals(text: str) -> dict[str, bool]:
    lowered = (text or "").lower()
    return {
        "hard": any(
            k in lowered
            for k in (
                "difficult",
                "complex",
                "advanced",
                "صعب",
                "معقد",
                "عميق",
                "advanced",
                "mistake",
                "غلط",
                "error",
            )
        ),
        "practical": any(
            k in lowered
            for k in (
                "practical",
                "apply",
                "build",
                "demo",
                "تطبيق",
                "عملي",
                "ابني",
                "خطوات",
            )
        ),
        "intro": any(
            k in lowered
            for k in ("intro", "overview", "foundation", "أساسي", "مقدمة", "بداية")
        ),
        "correction": any(
            k in lowered for k in ("mistake", "myth", "wrong", "غلط", "شائع", "تصحيح")
        ),
        "emotional": any(
            k in lowered for k in ("fear", "anxiety", "shame", "خوف", "قلق", "احباط")
        ),
    }


def plan_module_curve(
    *,
    module: ModulePlan,
    module_index: int,
    total_modules: int,
    previous_curve: ModuleCurve | None = None,
) -> ModuleCurve:
    """Decide this module's role/energy/depth relative to course position."""
    signals = _topic_signals(f"{module.title} {module.purpose}")
    role = _pick(MODULE_ROLES, module_index)
    if module_index == 0:
        role = "foundation"
    elif module_index == total_modules - 1 and total_modules > 1:
        role = "mastery" if not signals["practical"] else "synthesis"
    elif signals["correction"]:
        role = "correction"
    elif signals["practical"] and role in ("foundation", "transition"):
        role = "practical_build"

    energy = _pick(MODULE_ENERGY_CURVES, module_index + (1 if signals["hard"] else 0))
    if role == "foundation":
        energy = "calm_start"
    elif role == "correction":
        energy = "intense_middle"
    elif role in ("synthesis", "mastery"):
        energy = "reflective_close"
    elif signals["practical"]:
        energy = "practical_momentum"

    depth = _pick(MODULE_DEPTH_PATTERNS, module_index)
    if signals["hard"]:
        depth = "light_to_deep"
    elif signals["practical"]:
        depth = "mostly_practical"
    elif role == "correction":
        depth = "mostly_corrective"

    prev_role = previous_curve.module_role if previous_curve else "none"
    variation = (
        f"Shift away from previous module role '{prev_role}' toward '{role}' "
        f"with {energy.replace('_', ' ')} pacing."
    )
    risk = (
        "Repetition and flat energy if every lesson uses the same length and hook; "
        "overhype if ordinary points get viral treatment; shallow explain if speed "
        "overrides misunderstanding risk."
    )
    rationale = (
        f"Module {module_index + 1}/{total_modules} ({module.title}): "
        f"role={role} based on topic signals and course position."
    )
    return ModuleCurve(
        module_role=role,
        module_energy_curve=energy,
        module_depth_pattern=depth,
        module_variation_goal=variation,
        module_risk=risk,
        rationale=rationale,
    )


def plan_lesson_curve(
    *,
    reel: ReelPlan,
    reel_index: int,
    reels_in_module: int,
    module_curve: ModuleCurve,
    previous: CurveNeighbor | None = None,
    next_reel: CurveNeighbor | None = None,
) -> LessonCurve:
    """Decide this lesson's natural movement from topic + neighbors + module curve.

    Labels are planning decisions: the idea controls the curve, not the reverse.
    Inside one module, lengths/energies/hooks/endings are rotated so the module
    cannot collapse into one machine rhythm.
    """
    blob = " ".join(
        [
            reel.title,
            reel.purpose,
            " ".join(reel.must_cover),
            previous.purpose if previous else "",
            next_reel.purpose if next_reel else "",
        ]
    )
    signals = _topic_signals(blob)
    # Length/depth/energy rotate by index first (human variation inside module).
    # Topic signals may bias — they must not flatten every lesson to one energy.
    length = _pick(NATURAL_LENGTHS, reel_index)
    depth = _pick(NATURAL_DEPTHS, reel_index + (1 if signals["hard"] else 0))
    energy = _pick(TEACHING_ENERGIES, reel_index + (hash(reel.reel_id) % 5))
    tension = _pick(TENSION_CURVES, reel_index)
    density = _pick(SPEECH_DENSITIES, reel_index)
    mode = _pick(EXPLANATION_MODES, reel_index + (2 if signals["correction"] else 0))
    hook = _pick(HOOK_STRENGTHS, reel_index)
    ending = _pick(ENDING_MOTIONS, reel_index)

    if signals["intro"] and not signals["hard"] and reel_index == 0:
        length = "short" if length == "extended" else length
        depth = "light"
        energy = "calm"
        hook = "quiet"
        tension = "flat_clear"
        ending = "natural_transition"
    if signals["hard"]:
        length = "long" if length == "short" else length
        if length == "medium":
            length = "long"
        depth = "deep" if depth == "light" else depth
        if energy in ("excited", "warm"):
            energy = "analytical"
        tension = "confusion_to_clarity"
        hook = "quiet" if hook == "strong" else hook
    if signals["practical"] and reel_index % 2 == 0:
        # Bias some (not all) practical lessons toward application energy.
        energy = "practical"
        mode = "demonstration" if mode == "direct_explanation" else mode
        ending = "unresolved_practical_need" if ending == "clean_close" else ending
    if signals["correction"]:
        energy = "sharp"
        mode = "mistake_correction"
        tension = "pressure_then_relief"
        hook = "medium" if hook == "quiet" else hook
    if signals["emotional"]:
        energy = "warm"
        density = "low"
        hook = "quiet"

    # Module role soft constraints (never force viral).
    if module_curve.module_energy_curve == "quiet_precision":
        energy = "precise" if energy == "excited" else energy
        hook = "quiet" if hook == "strong" else hook
    if module_curve.module_role == "foundation" and reel_index == 0:
        hook = "quiet"
        ending = "soft_next_need"

    # Last lesson in module: prefer clean close / no forced loop.
    if reel_index == reels_in_module - 1 and ending not in (
        "clean_close",
        "no_loop_needed",
        "natural_transition",
    ):
        ending = "no_loop_needed"

    hook_reason = (
        "Open on the exact decision the learner gets wrong, without bait."
        if signals["correction"]
        else (
            "Quiet entry: the first concrete fact is enough to stop the right viewer."
            if hook == "quiet"
            else (
                "Strong stop only because the idea itself is high-stakes, not for heat."
                if hook == "strong"
                else "Medium hook: name the useful problem in the first breath."
            )
        )
    )

    compress = (
        "Say the decision rule and one realistic check; skip biography, "
        "throat-clearing, and equal-length padding."
    )
    expand = (
        "Expand where misunderstanding risk is high: contrast the wrong default "
        "with the correct mental model and one local example."
        if signals["hard"] or signals["correction"]
        else (
            "Keep depth light; expand only if a concrete application step is missing."
        )
    )

    prev_label = previous.title if previous else "start"
    next_label = next_reel.title if next_reel else "module end"
    rationale = (
        f"Between '{prev_label}' and '{next_label}': length={length}, "
        f"energy={energy}, hook={hook} because topic signals and module "
        f"role '{module_curve.module_role}' demand human variation, not a flat line."
    )

    return LessonCurve(
        natural_length=length,
        natural_depth=depth,
        teaching_energy=energy,
        tension_curve=tension,
        speech_density=density,
        explanation_mode=mode,
        hook_strength=hook,
        hook_reason=hook_reason,
        ending_motion=ending,
        compression_decision=compress,
        expansion_decision=expand,
        rationale=rationale,
    )


def compact_module_curve_for_prompt(curve: ModuleCurve) -> dict[str, str]:
    """Token-cheap labels + one-line rationale for writing prompts."""
    return {
        "module_role": curve.module_role,
        "module_energy_curve": curve.module_energy_curve,
        "module_depth_pattern": curve.module_depth_pattern,
        "module_variation_goal": curve.module_variation_goal,
        "module_risk": curve.module_risk,
        "rationale": curve.rationale,
    }


def compact_lesson_curve_for_prompt(curve: LessonCurve) -> dict[str, str]:
    """Token-cheap labels + short reasons for writing prompts."""
    return {
        "natural_length": curve.natural_length,
        "natural_depth": curve.natural_depth,
        "teaching_energy": curve.teaching_energy,
        "tension_curve": curve.tension_curve,
        "speech_density": curve.speech_density,
        "explanation_mode": curve.explanation_mode,
        "hook_strength": curve.hook_strength,
        "hook_reason": curve.hook_reason,
        "ending_motion": curve.ending_motion,
        "compression_decision": curve.compression_decision,
        "expansion_decision": curve.expansion_decision,
        "rationale": curve.rationale,
    }


def format_curves_for_prompt(
    module_curve: ModuleCurve,
    lesson_curve: LessonCurve,
) -> dict[str, dict[str, str]]:
    """Shape both curves the way WriteSingleReelInput / Anthropic context expect."""
    return {
        "module_curve": compact_module_curve_for_prompt(module_curve),
        "lesson_curve": compact_lesson_curve_for_prompt(lesson_curve),
    }
