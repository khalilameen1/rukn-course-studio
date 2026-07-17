"""JSON Admin Knowledge seed blobs."""

from __future__ import annotations

import json

from app.generation.presets import DEFAULT_GENERATION_PRESET, PRESET_DESCRIPTIONS

FORBIDDEN_PHRASES = {
    "description": "Phrases that must never appear in generated lecturer scripts.",
    "phrases": [
        {
            "phrase": "في الريل ده",
            "severity": "high",
            "replacement_hint": (
                "Cut the meta-reference to the reel; start the sentence "
                "directly with the actual content."
            ),
        },
        {
            "phrase": "خلينا نتكلم عن",
            "severity": "high",
            "replacement_hint": (
                "Drop the throat-clearing opener and state the point directly."
            ),
        },
        {
            "phrase": "مرحباً بكم في هذا الفيديو",
            "severity": "high",
            "replacement_hint": (
                "Remove generic welcome intros entirely; open with the first "
                "real idea instead."
            ),
        },
        {
            "phrase": "وفي النهاية حابب أقولكم",
            "severity": "medium",
            "replacement_hint": (
                "Replace cliché sign-offs with a concrete recap or a clear "
                "next action."
            ),
        },
        {
            "phrase": "متنسوش تتابعونا وتشتركوا في القناة",
            "severity": "high",
            "replacement_hint": (
                "Remove entirely - this is a lecturer script, not a social "
                "media video."
            ),
        },
        {
            "phrase": "بجد يا شباب الموضوع ده هيغير حياتكم",
            "severity": "medium",
            "replacement_hint": (
                "Cut the motivational hype; state why it matters in one "
                "plain, concrete sentence instead."
            ),
        },
        {
            "phrase": "السر اللي محدش يعرفه",
            "severity": "high",
            "replacement_hint": (
                "Drop attention bait. Open with the real distinction or "
                "correction the learner needs."
            ),
        },
        {
            "phrase": "ده هيغير حياتك",
            "severity": "high",
            "replacement_hint": (
                "Remove overhyped payoff claims. State one concrete benefit."
            ),
        },
        {
            "phrase": "أخطر حاجة",
            "severity": "medium",
            "replacement_hint": (
                "Use calm precision unless the risk is genuinely severe; "
                "name the actual failure mode instead of ranking 'worst'."
            ),
        },
        {
            "phrase": "أكبر غلط",
            "severity": "medium",
            "replacement_hint": (
                "Prefer a precise mistake name over superlative bait."
            ),
        },
        {
            "phrase": "في الريل الجاي",
            "severity": "high",
            "replacement_hint": (
                "Never announce the next reel. End on a natural cut at an "
                "important unfinished point."
            ),
        },
        {
            "phrase": "في الجزء الجاي",
            "severity": "high",
            "replacement_hint": (
                "No forced cliffhanger announcement. End where the idea "
                "opens a real next need."
            ),
        },
        {
            "phrase": "استنوا الجزء اللي بعده",
            "severity": "high",
            "replacement_hint": (
                "Remove seller-style continues. Cut organically."
            ),
        },
        {
            "phrase": "this will destroy",
            "severity": "high",
            "replacement_hint": "Remove English clickbait; speak plainly.",
        },
        {
            "phrase": "secret no one knows",
            "severity": "high",
            "replacement_hint": "Remove bait; teach the actual point.",
        },
    ],
}

QUALITY_RUBRIC = {
    "description": "Checks applied when reviewing practical skill courses during generation.",
    "checks": [
        {
            "id": "clear_outcome",
            "label": "Clear outcome",
            "description": (
                "Every module and the course as a whole states a concrete, "
                "checkable outcome the learner can achieve."
            ),
        },
        {
            "id": "module_progression",
            "label": "Module progression",
            "description": (
                "Each module builds on the skills taught in previous "
                "modules; nothing is taught out of order or in isolation."
            ),
        },
        {
            "id": "no_repetition",
            "label": "No repetition",
            "description": (
                "No reel or module repeats explanations, examples, or "
                "phrasing already used earlier in the course."
            ),
        },
        {
            "id": "real_application",
            "label": "Real application",
            "description": (
                "Examples and exercises reflect realistic, real-world use "
                "of the skill - not invented toy scenarios."
            ),
        },
        {
            "id": "bridge_project_quality",
            "label": "Bridge project quality",
            "description": (
                "Bridge projects genuinely connect the modules on either "
                "side and are not fake or disconnected from the material."
            ),
        },
        {
            "id": "natural_lecturer_text",
            "label": "Natural lecturer text",
            "description": (
                "The script reads like a real lecturer speaking naturally - "
                "short sentences, direct entry, no filler or forbidden "
                "phrases."
            ),
        },
        {
            "id": "shareability",
            "label": "Shareability",
            "description": (
                "Contains a non-obvious distinction, correction, or mental "
                "model worth sharing - not generic advice everyone already knows."
            ),
        },
        {
            "id": "save_worthiness",
            "label": "Save-worthiness",
            "description": (
                "Gives something the student would honestly bookmark: a "
                "usable shortcut, checklist distinction, or realistic fix."
            ),
        },
        {
            "id": "non_obvious_value",
            "label": "Non-obvious value",
            "description": (
                "High-signal content: corrects a likely student mistake or "
                "clarifies something previously confusing."
            ),
        },
        {
            "id": "realism",
            "label": "Realism / locality",
            "description": (
                "Examples fit Egyptian/Arab learner reality (small shops, "
                "phones, low budgets) - not imported luxury or default "
                "huge-company contexts."
            ),
        },
        {
            "id": "human_speech_naturalness",
            "label": "Human speech naturalness",
            "description": (
                "Sounds like a human teacher in the domain - not AI "
                "colloquial Arabic, poetic fluff, or fake street slang."
            ),
        },
        {
            "id": "anti_cliche",
            "label": "Anti-cliché",
            "description": "No overhyped hooks, motivational fluff, or bait language.",
        },
        {
            "id": "anti_template",
            "label": "Anti-template",
            "description": (
                "Does not repeat a recent reel's structure, hook family, "
                "loop move, or mechanical device pattern."
            ),
        },
        {
            "id": "loop_organicness",
            "label": "Loop organicness",
            "description": (
                "Any series cut feels like drama/platform cut at a real "
                "need - never 'in the next reel' announcement."
            ),
        },
        {
            "id": "hook_meaningfulness",
            "label": "Hook meaningfulness",
            "description": (
                "First sentence stops because of the idea, not exaggerated "
                "wording. Quiet topics stay calm."
            ),
        },
        {
            "id": "sentence_necessity",
            "label": "Sentence necessity",
            "description": (
                "Fail if multiple sentences can be removed without loss. "
                "No padding to hit a length."
            ),
        },
        {
            "id": "domain_fit",
            "label": "Domain fit",
            "description": (
                "Teaching energy fits the skill domain; not one robotic "
                "voice for every craft."
            ),
        },
        {
            "id": "course_continuity",
            "label": "Course continuity",
            "description": (
                "Standalone for a stranger on social, but no disguised "
                "recap of the previous reel; series feels connected not chopped."
            ),
        },
        {
            "id": "no_forced_selling",
            "label": "Teacher dignity / no forced selling",
            "description": (
                "May show course value honestly; must not sound like a "
                "desperate seller."
            ),
        },
        {
            "id": "variable_length",
            "label": "Variable length by idea",
            "description": (
                "Length follows the idea (short/medium/long). Not forced "
                "equal word counts; not padded or cut until shallow."
            ),
        },
    ],
}

# Kept in sync with app/generation/presets.py - the seeded JSON below is the
# same data the real provider will eventually read, just also visible to
# admins via the Admin Knowledge Center.
GENERATION_PRESETS = {
    "description": (
        "Named generation presets for future AI-provider use. FakeProvider "
        "does not read this yet (see app/generation/presets.py)."
    ),
    "default": DEFAULT_GENERATION_PRESET.value,
    "presets": [
        {"id": preset.value, "label": preset.value.capitalize(), "description": description}
        for preset, description in PRESET_DESCRIPTIONS.items()
    ],
}

