"""Seed the fixed set of core Rukn admin knowledge items.

Run with:
    python -m app.seed_admin_knowledge

Safe to re-run: any `key` that already has at least one row (any version)
is left untouched, so re-running never creates duplicate versions. To
reseed a specific item from scratch, delete its row(s) via the admin API
or /admin page first.
"""

import json

from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.db import engine, init_db
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
    ],
}

SEED_ITEMS: list[dict] = [
    {
        "key": "rukn-core",
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
        "key": "rukn-practical-course",
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
        "key": "rukn-writing-style",
        "title": "Rukn Writing Style Rules",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Writing Style Rules

- Sentences must be short and natural, in a lecturer's spoken voice.
- Enter each topic directly - no long wind-up before getting to the point.
- Never use "في الريل ده" (filler referencing "in this reel").
- Never use "خلينا نتكلم عن" ("let's talk about") or similar throat-clearing openers.
- No cliché endings (e.g. generic "and that's it, see you next time" wrap-ups).
- No motivational fluff - stay practical and to the point, not inspirational.
""",
    },
    {
        "key": "rukn-forbidden-phrases",
        "title": "Rukn Forbidden Phrases",
        "item_type": ItemType.JSON,
        "content_text": json.dumps(FORBIDDEN_PHRASES, ensure_ascii=False, indent=2),
    },
    {
        "key": "rukn-quality-rubric",
        "title": "Rukn Quality Rubric",
        "item_type": ItemType.JSON,
        "content_text": json.dumps(QUALITY_RUBRIC, ensure_ascii=False, indent=2),
    },
    {
        "key": "rukn-spoken-style-bank",
        "title": "Rukn Spoken Style Reference Bank",
        "item_type": ItemType.MARKDOWN,
        "content_text": """# Rukn Spoken Style Reference Bank

> **Style reference only - not a factual source.** These snippets exist purely to demonstrate Rukn's natural spoken tone. Never treat their content as facts, data, or course material to reuse - only imitate the *rhythm and phrasing* of the sentences.

Example spoken-style lines (placeholders):

- "لو جربت كذا قبل كده هتلاقي الفرق واضح من الجملة الأولى."
- "الحركة دي ممكن تبان بسيطة، بس هي اللي بتفرق فعلياً في النتيجة."
- "خد بالك من الخطوة دي كويس، عشان اللي جاي بعدها مبني عليها."

Add more real examples here as they're collected. Keep every entry short, natural, and in the direct-entry lecturer voice described in rukn-writing-style.
""",
    },
]


def seed(session: Session) -> None:
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


def main() -> None:
    init_db()
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
