"""Seed the fixed set of core Rukn admin knowledge items.

Run manually with:
    python -m app.seed_admin_knowledge

Also run automatically once at backend startup (see app/main.py lifespan) -
safe to do on every startup because `seed()` is fully idempotent: any `key`
that already has at least one row (any version, including one a user has
since edited) is left completely untouched, so this never duplicates rows
and never overwrites an edit. To reseed a specific item from scratch,
delete its row(s) via the admin API or /admin page first, then re-run.
"""

import json

from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.db import engine, init_db
from app.generation.presets import DEFAULT_GENERATION_PRESET, PRESET_DESCRIPTIONS
from app.models.enums import ItemType

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

TELEPROMPTER_DOCX_CONTRACT = """# Rukn Teleprompter DOCX Contract

This defines what the final exported DOCX is - and is not. Every generated
course's final DOCX must follow this contract exactly.

## What the final DOCX IS

The final DOCX is a teleprompter-ready lecturer script - ready to read
directly on camera, with no further editing needed.

## What the final DOCX is NOT

- The final DOCX is not a book.
- The final DOCX is not a student handout.
- The final DOCX is not a preparation report.

## Required contents (and nothing else)

The final DOCX must contain only:

- Course title
- Module headings
- Lesson/Reel headings
- The exact spoken script the lecturer will say on camera
- Optional task/project text, only if it is meant to be spoken or shown
  directly to the student

## Forbidden contents

The final DOCX must never contain:

- A cover page
- Branding pages
- "Prepared by AI" or any similar credit/disclaimer
- Methodology notes
- Internal generation notes
- Review notes
- Quality notes
- Instructions like "say this" or "explain that" addressed to the lecturer
  instead of being the actual words to say
- "Note to instructor" sections
- Academic objective sections (e.g. "Learning Objectives")
- "In this lesson we will learn..." framing, unless it is naturally
  something a lecturer would actually say out loud
- Anything addressed to the course creator instead of to the lecturer/student

## Default spoken style

- Clean Egyptian Arabic
- Direct opening - no formal introductions
- No filler
- No robotic wording
- No academic essay tone
- Short, readable paragraphs
- Ready to record immediately, with no further editing needed
"""

HIGH_SIGNAL_REEL_DOCTRINE = """# Rukn High-Signal Reel Doctrine

This doctrine governs how reels/lessons are written for Rukn. It does not
replace rukn_writing_style, rukn_core_rules, or rukn_teleprompter_docx_contract
- it raises the standard against shallow short-form habits, clichés, and
template addiction mechanics.

Style and format authority still come ONLY from Admin Knowledge and the
teleprompter DOCX contract. Uploaded sources never define Rukn voice or structure.

## A. Hook principle

A hook is not hype. A hook is a meaningful first sentence that stops the
viewer because of the *idea*, not because of exaggerated wording.

Avoid: biggest, worst, most dangerous, "secret no one knows", "this will
destroy", and any forced attention bait.

Use calm precision unless the idea itself deserves heat. Some topics are
naturally quiet and should stay quiet.

## B. Loop principle

The loop is not "in the next reel". The loop should feel like a natural
cut at an important point - drama/platform style - not an announcement.

The viewer should want the next part because the idea opened a real need,
not because we told them to wait.

## C. Standalone + series principle

Every reel must work alone on social media. A stranger should understand
it without previous context.

Inside the app series, do not repeat the previous reel at the start. No
recap disguised with different wording.

## D. Variable length principle

Each reel's length follows the idea. Short, medium, or long (even ~5
minutes) are all valid when the idea needs it. A sharp idea may be under a
minute.

Do not force equal word counts. Do not pad to hit a number. Do not cut
until the content is shallow.

## E. High-signal principle

Every reel must contain something worth saving or sharing:
- a non-obvious distinction
- a practical correction
- a real-world insight
- a mistake the student was probably making
- a simple explanation of something previously confusing
- a usable mental model
- a field-specific shortcut that is honest

Avoid generic information everyone already knows.

## F. Real-world locality

Examples should fit the real learner's world: small businesses, local
shops, restaurants, clothing brands, freelancers, students with phones,
low budgets, Egyptian/Arab market reality.

Avoid defaulting to huge companies, expensive tools, luxury devices, or
imported contexts that do not fit Egyptian students.

## G. No surface-level short-form thinking

Being a reel does not mean shallow. Being a series does not mean repeated
hooks and fake cliffhangers. Content can be deep, accurate, and useful
while still spoken simply.

## H. No forced selling

The lecturer should sound like a teacher, not a desperate seller. Showing
the honest value of the course/app is allowed. Do not make selling the
main goal of the speech.

## I. No poetic prose or street slang

Avoid poetic emotional prose, motivational fluff, fake Egyptian street
slang, jokes for the sake of jokes, strange metaphors, and "sersegy"
language.

Tone: natural, accurate, clean, human, and domain-native.

## J. Domain-specific voice

Do not use one voice for every skill. A designer, programmer, marketer,
language teacher, and religious educator do not share the same energy.
Vary module architecture and rhythm so the course does not feel like one
repeated machine.

## Adversarial self-review (required writing process)

For every reel generation, the writer must internally produce:
1. Draft A
2. Draft B
3. Adversarial Critic pass
4. Master Version

Only the Master Version becomes `script_text`. Never ship Draft A or B.

The critic must ask:
- Is the hook overhyped?
- Is the loop forced?
- Is any sentence removable without loss?
- Is the example realistic and local?
- Is the idea actually worth sharing?
- Is this generic information?
- Does this sound like a human lecturer?
- Does this sound like AI Egyptian Arabic?
- Is it too shallow?
- Is it trying to sell?
- Is it repeating a previous reel structure?
- Does it turn a good rule into a template?
- Is the length natural for the idea?

## Course / module anti-template checks

Across a module:
- Hooks must not come from the same family.
- Loops must not use the same move.
- Reel lengths must vary naturally.
- Examples must not all come from the same scenario.
- Devices like "practical application", "exception", "mistake", "secret"
  must not appear mechanically in every reel.
- Recaps must not open every reel.
- The course should feel connected, not chopped.

## Hard fail conditions

A reel fails quality if:
- removing multiple sentences does not hurt it
- it relies on overhyped hook language
- it gives generic advice
- it uses unrealistic examples
- it sounds like AI-written colloquial Arabic
- it repeats a structure used recently
- it sells instead of teaches
- it is shallow because it was forced short

## Source authority (never define Rukn style/format)

- Scientific sources provide **knowledge only** - they must not influence
  language, tone, or structure.
- Flow references provide **human speech mechanics only** (`human_flow_profile`) -
  never factual summaries, never reusable format templates, never copied
  catchphrases. They may be from another domain or long-form content.
- Rukn style comes from Admin Knowledge. Rukn format comes from the
  teleprompter DOCX contract. Naturalness comes from high-level flow analysis,
  not copying.
"""

SEED_ITEMS: list[dict] = [
    {
        "key": "rukn_core_rules",
        "title": "Rukn Core Voice & Delivery Rules",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Core Voice & Delivery Rules

These rules define Rukn's core voice and are non-negotiable for every generated course.

- Voice: Egyptian Arabic, clean spoken style (no heavy slang, no stiff Modern Standard Arabic).
- No filler words or filler phrases.
- No generic intros (e.g. no boilerplate "welcome to this lecture" openings).
- No artificial or robotic phrasing - it must sound like a real person talking.
- The final output must be a lecturer script that is ready for recording as-is, with no further editing needed for tone or delivery.
""",
    },
    {
        "key": "rukn_practical_course_rules",
        "title": "Rukn Practical Skill Course Rules",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Practical Skill Course Rules

Rules specific to practical skill courses (the only course type supported in V1).

- Courses are built as connected modules - each module builds on the previous one, not standalone units.
- Bridge projects connect modules together and reinforce skills learned so far before moving on.
- Every example must be realistic - drawn from real-world use cases, not invented toy scenarios.
- Learning must be step-by-step: each reel/module assumes only what was already taught.
- No fake projects - every project/exercise must resemble something the learner would actually do.
""",
    },
    {
        "key": "rukn_writing_style",
        "title": "Rukn Writing Style Rules",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Writing Style Rules

- Sentences must be short and natural, in a lecturer's spoken voice.
- Enter each topic directly - no long wind-up before getting to the point.
- Never use "في الريل ده" (filler referencing "in this reel").
- Never use "خلينا نتكلم عن" ("let's talk about") or similar throat-clearing openers.
- No cliché endings (e.g. generic "and that's it, see you next time" wrap-ups).
- No motivational fluff - stay practical and to the point, not inspirational.
- Follow rukn_high_signal_reel_doctrine for hooks, loops, high-signal value,
  locality of examples, variable length, and adversarial Draft A/B/Critic/Master
  writing (only the Master Version is exported as spoken script).
""",
    },
    {
        "key": "rukn_forbidden_phrases",
        "title": "Rukn Forbidden Phrases",
        "item_type": ItemType.JSON,
        "content_text": json.dumps(FORBIDDEN_PHRASES, ensure_ascii=False, indent=2),
    },
    {
        "key": "rukn_quality_rubric",
        "title": "Rukn Quality Rubric",
        "item_type": ItemType.JSON,
        "content_text": json.dumps(QUALITY_RUBRIC, ensure_ascii=False, indent=2),
    },
    {
        "key": "rukn_teleprompter_docx_contract",
        "title": "Rukn Teleprompter DOCX Contract",
        "item_type": ItemType.MARKDOWN,
        "content_text": TELEPROMPTER_DOCX_CONTRACT,
    },
    {
        "key": "rukn_high_signal_reel_doctrine",
        "title": "Rukn High-Signal Reel Doctrine",
        "item_type": ItemType.MARKDOWN,
        "content_text": HIGH_SIGNAL_REEL_DOCTRINE,
    },
    {
        "key": "rukn_generation_presets",
        "title": "Rukn Generation Presets",
        "item_type": ItemType.JSON,
        "content_text": json.dumps(GENERATION_PRESETS, ensure_ascii=False, indent=2),
    },
    {
        "key": "rukn-spoken-style-bank",
        "title": "Rukn Spoken Style Reference Bank",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Spoken Style Reference Bank

> **Style reference only - not a factual source.** These snippets exist purely to demonstrate Rukn's natural spoken tone. Never treat their content as facts, data, or course material to reuse - only imitate the *rhythm and phrasing* of the sentences. Never copy as a template. See also rukn_high_signal_reel_doctrine.

Example spoken-style lines (placeholders):

- "لو جربت كذا قبل كده هتلاقي الفرق واضح من الجملة الأولى."
- "الحركة دي ممكن تبان بسيطة، بس هي اللي بتفرق فعلياً في النتيجة."
- "خد بالك من الخطوة دي كويس، عشان اللي جاي بعدها مبني عليها."

Add more real examples here as they're collected. Keep every entry short, natural, and in the direct-entry lecturer voice described in rukn_writing_style.
""",
    },
]

# Required core keys that must exist after seeding (includes the high-signal
# doctrine). SEED_ITEMS also keeps the optional "rukn-spoken-style-bank" item.
REQUIRED_KEYS: set[str] = {
    "rukn_core_rules",
    "rukn_practical_course_rules",
    "rukn_writing_style",
    "rukn_forbidden_phrases",
    "rukn_quality_rubric",
    "rukn_teleprompter_docx_contract",
    "rukn_high_signal_reel_doctrine",
    "rukn_generation_presets",
}

# Only these system defaults may be intentionally replaced via
# `--refresh-defaults`. Optional keys are refreshed only when present in
# SEED_ITEMS (today: firewall/flow-guide keys are not shipped yet).
REFRESHABLE_DEFAULT_KEYS: tuple[str, ...] = (
    "rukn_forbidden_phrases",
    "rukn_quality_rubric",
    "rukn_high_signal_reel_doctrine",
    "rukn_teleprompter_docx_contract",
    "rukn_source_authority_firewall",
    "rukn_flow_reference_guide",
)

_SEED_BY_KEY: dict[str, dict] = {item["key"]: item for item in SEED_ITEMS}


def seed(session: Session) -> None:
    """Idempotent create-missing-only seed. Never overwrites existing rows."""
    for item in SEED_ITEMS:
        existing = admin_knowledge_items.list(session, key=item["key"])
        if existing:
            print(f"skip  {item['key']} (already seeded, {len(existing)} version(s))")
            continue

        admin_knowledge_items.create(
            session,
            key=item["key"],
            title=item["title"],
            item_type=item["item_type"],
            content_text=item["content_text"],
            version=1,
            is_active=True,
        )
        print(f"seed  {item['key']}")


def refresh_defaults(session: Session) -> list[str]:
    """Replace selected system defaults with current SEED_ITEMS content.

    For each refreshable key that exists in SEED_ITEMS:
    - If no row exists yet, create version 1 (same as normal seed).
    - If rows exist, deactivate all siblings, keep the previous active row
      as an inactive backup (title stamped with UTC time), and create a
      new higher `version` that becomes the only active row.

    Never touches keys outside REFRESHABLE_DEFAULT_KEYS (custom knowledge
    and other system keys like rukn_core_rules stay untouched).
    """
    from datetime import datetime, timezone

    refreshed: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for key in REFRESHABLE_DEFAULT_KEYS:
        item = _SEED_BY_KEY.get(key)
        if item is None:
            print(f"skip  {key} (no shipped default in this build)")
            continue

        existing = admin_knowledge_items.list(session, key=key)
        if not existing:
            admin_knowledge_items.create(
                session,
                key=item["key"],
                title=item["title"],
                item_type=item["item_type"],
                content_text=item["content_text"],
                version=1,
                is_active=True,
            )
            print(f"seed  {key} (was missing)")
            refreshed.append(key)
            continue

        max_version = max(row.version for row in existing)
        previous_active = next((row for row in existing if row.is_active), existing[-1])

        # Snapshot: keep prior content as an inactive versioned row.
        for sibling in existing:
            updates: dict = {"is_active": False}
            if sibling.id == previous_active.id:
                base_title = item["title"]
                # Avoid stacking backup stamps on repeated refreshes.
                if "(backup " not in (sibling.title or ""):
                    updates["title"] = f"{base_title} (backup {stamp})"
            admin_knowledge_items.update(session, sibling.id, **updates)

        admin_knowledge_items.create(
            session,
            key=item["key"],
            title=item["title"],
            item_type=item["item_type"],
            content_text=item["content_text"],
            version=max_version + 1,
            is_active=True,
        )
        print(
            f"refresh  {key} -> v{max_version + 1} "
            f"(previous kept inactive as backup; was v{previous_active.version})"
        )
        refreshed.append(key)

    return refreshed


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Seed missing Admin Knowledge defaults (idempotent), or "
            "intentionally refresh selected system defaults."
        )
    )
    parser.add_argument(
        "--refresh-defaults",
        action="store_true",
        help=(
            "Replace selected system-managed defaults with the current "
            "codebase seed content. Keeps the previous active row as an "
            "inactive backup version. Requires --confirm."
        ),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --refresh-defaults to acknowledge backup+replace.",
    )
    args = parser.parse_args(argv)

    init_db()
    with Session(engine) as session:
        if args.refresh_defaults:
            if not args.confirm:
                print(
                    "Refusing to refresh defaults without --confirm.\n"
                    "This will deactivate current active versions for selected "
                    "system keys and create new active versions from code "
                    "defaults (previous content is kept as inactive backup "
                    "rows).\n"
                    "Keys: "
                    + ", ".join(REFRESHABLE_DEFAULT_KEYS)
                    + "\n\n"
                    "Exact command:\n"
                    "  python -m app.seed_admin_knowledge --refresh-defaults --confirm"
                )
                return 2
            refreshed = refresh_defaults(session)
            print(f"done  refreshed {len(refreshed)} key(s)")
            return 0

        seed(session)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
