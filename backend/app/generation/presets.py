"""Generation presets: named intents for how an AI provider should approach
a generation task.

Not wired into any provider call yet - `FakeProvider` remains the only
active provider (see app/ai/factory.py) and ignores this entirely. This
module exists purely to prepare a clean, typed configuration surface
*before* a real provider is connected, so wiring it in later is a small
change instead of a design decision made under pressure.

`GenerationPreset` itself lives in app/models/enums.py (so it can be a
proper SQLModel column type on `Course`) and is re-exported here so
existing `from app.generation.presets import GenerationPreset` imports
keep working unchanged.

Do NOT build the full "Fusion" merge-two-attempts feature yet - only the
name and description are reserved for now.
"""

from app.models.enums import GenerationPreset

__all__ = [
    "GenerationPreset",
    "DEFAULT_GENERATION_PRESET",
    "PRESET_DESCRIPTIONS",
    "PRESET_TEMPERATURES",
    "resolve_generation_settings",
]


# Normal lesson/script generation is the common case - every other preset
# is for a specific future situation (reviewing, brainstorming variety,
# merging attempts, strict final cleanup), not the default path.
DEFAULT_GENERATION_PRESET = GenerationPreset.BALANCED

PRESET_DESCRIPTIONS: dict[GenerationPreset, str] = {
    GenerationPreset.CONSERVATIVE: (
        "Review, correction, and low-hallucination passes - favors accuracy "
        "and caution over variety. Intended future use: reviewing or "
        "correcting already-generated content, not first-draft writing."
    ),
    GenerationPreset.BALANCED: (
        "Normal lesson/script generation - the default for everyday reel "
        "and module writing. Used unless a task specifically calls for one "
        "of the other presets."
    ),
    GenerationPreset.CREATIVE: (
        "Openings, examples, and angles - favors variety and a stronger "
        "hook over strict conservatism. Intended future use: generating "
        "multiple candidate openings/examples to choose from."
    ),
    GenerationPreset.FUSION: (
        "Combining two attempts into one. Intended future use: merging a "
        "Conservative attempt and a Creative attempt into a single best "
        "version. Not implemented yet - only the preset name is reserved."
    ),
    GenerationPreset.STRICT_TELEPROMPTER: (
        "Final export/cleanup pass enforcing the teleprompter DOCX "
        "contract strictly - lowest tolerance for anything that isn't "
        "spoken script."
    ),
}

# Prep for a future real provider only - nothing calls this yet. Kept here
# as a typed, reviewable table instead of inventing numbers ad hoc once a
# real provider is finally wired in.
PRESET_TEMPERATURES: dict[GenerationPreset, float] = {
    GenerationPreset.CONSERVATIVE: 0.2,
    GenerationPreset.BALANCED: 0.45,
    GenerationPreset.CREATIVE: 0.75,
    GenerationPreset.FUSION: 0.35,
    GenerationPreset.STRICT_TELEPROMPTER: 0.25,
}


def resolve_generation_settings(preset: GenerationPreset) -> dict:
    """Plain-dict settings for `preset` - for future real-provider use only.

    Nothing calls this yet; it exists so wiring in a real provider later is
    a matter of reading this dict, not inventing the mapping under
    pressure.
    """
    return {"preset": preset.value, "temperature": PRESET_TEMPERATURES[preset]}
