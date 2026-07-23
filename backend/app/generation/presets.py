"""Generation presets: named intents for how an AI provider should approach
a generation task.

OpenAI Responses (`gpt-5.6-sol`) ignores sampling temperature — stage routing
uses reasoning effort instead (`app/generation/model_routing.py`). Preset
values remain on the course for intent labeling and any legacy Anthropic
rollback path.

`GenerationPreset` itself lives in app/models/enums.py (so it can be a
proper SQLModel column type on `Course`) and is re-exported here so
existing `from app.generation.presets import GenerationPreset` imports
keep working unchanged.

Fusion is an alias of Balanced until a true dual-attempt merge ships.
"""

from app.models.enums import GenerationPreset

__all__ = [
    "GenerationPreset",
    "DEFAULT_GENERATION_PRESET",
    "PRESET_DESCRIPTIONS",
    "PRESET_TEMPERATURES",
    "resolve_generation_settings",
    "normalize_generation_preset",
]


# Normal lesson/script generation is the common case - every other preset
# is for a specific situation (reviewing, brainstorming variety, strict
# final cleanup), not the default path.
DEFAULT_GENERATION_PRESET = GenerationPreset.BALANCED

PRESET_DESCRIPTIONS: dict[GenerationPreset, str] = {
    GenerationPreset.CONSERVATIVE: (
        "Review, correction, and low-hallucination passes - favors accuracy "
        "and caution over variety. Best for reviewing or correcting already-"
        "generated content, not first-draft writing."
    ),
    GenerationPreset.BALANCED: (
        "Normal lesson/script generation - the default for everyday reel "
        "and module writing. Used unless a task specifically calls for one "
        "of the other presets."
    ),
    GenerationPreset.CREATIVE: (
        "Openings, examples, and angles - favors variety and a stronger "
        "hook over strict conservatism."
    ),
    GenerationPreset.FUSION: (
        "Reserved label. Currently uses the same settings as Balanced. "
        "A future dual-attempt merge (Conservative + Creative) is not shipped."
    ),
    GenerationPreset.STRICT_TELEPROMPTER: (
        "Final export/cleanup pass enforcing the teleprompter DOCX "
        "contract strictly - lowest tolerance for anything that isn't "
        "spoken script."
    ),
}

# Legacy Anthropic temperature map. OpenAI production ignores these.
PRESET_TEMPERATURES: dict[GenerationPreset, float] = {
    GenerationPreset.CONSERVATIVE: 0.2,
    GenerationPreset.BALANCED: 0.45,
    GenerationPreset.CREATIVE: 0.75,
    GenerationPreset.FUSION: 0.45,  # alias of Balanced
    GenerationPreset.STRICT_TELEPROMPTER: 0.25,
}


def normalize_generation_preset(preset: GenerationPreset) -> GenerationPreset:
    """Map unimplemented Fusion onto Balanced for provider settings."""
    if preset == GenerationPreset.FUSION:
        return GenerationPreset.BALANCED
    return preset


def resolve_generation_settings(preset: GenerationPreset) -> dict:
    """Plain-dict settings for `preset` (legacy temperature + resolved intent)."""
    effective = normalize_generation_preset(preset)
    return {
        "preset": preset.value,
        "effective_preset": effective.value,
        "temperature": PRESET_TEMPERATURES[effective],
    }
