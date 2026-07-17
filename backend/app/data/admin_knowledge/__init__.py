"""Admin Knowledge seed package — content clusters + loader."""

from app.data.admin_knowledge.seed_items import SEED_ITEMS, _SEED_BY_KEY
from app.data.admin_knowledge.seed_loader import main, refresh_defaults, seed
from app.data.admin_knowledge_registry import REFRESHABLE_DEFAULT_KEYS, REQUIRED_KEYS

# Re-export content constants used by tests / validators.
from app.data.admin_knowledge.gates import (
    INTERPRETATION_GUARDRAILS,
    SOURCE_DISTILLATION_GATE,
    SOURCE_IMPERFECTION_GATE,
    TRANSCRIPT_TOPIC_RELEVANCE_GATE,
)
from app.data.admin_knowledge.json_items import (
    FORBIDDEN_PHRASES,
    GENERATION_PRESETS,
    QUALITY_RUBRIC,
)
from app.data.admin_knowledge.loop_engines import (
    CREATOR_CRITIC_LOOP,
    CREATOR_PERSONA_ENGINE,
    DYNAMIC_TEACHING_CURVE,
    MASTER_MENTOR_ENGINE,
    STUDENT_CONFUSION_LAYER,
)
from app.data.admin_knowledge.voice import (
    ANTI_PATTERNS_QUALITY_CHECKS,
    EDUCATIONAL_CREATOR_STANDARD,
    HIGH_SIGNAL_REEL_DOCTRINE,
    TELEPROMPTER_DOCX_CONTRACT,
)

__all__ = [
    "ANTI_PATTERNS_QUALITY_CHECKS",
    "CREATOR_CRITIC_LOOP",
    "CREATOR_PERSONA_ENGINE",
    "DYNAMIC_TEACHING_CURVE",
    "EDUCATIONAL_CREATOR_STANDARD",
    "FORBIDDEN_PHRASES",
    "GENERATION_PRESETS",
    "HIGH_SIGNAL_REEL_DOCTRINE",
    "INTERPRETATION_GUARDRAILS",
    "MASTER_MENTOR_ENGINE",
    "QUALITY_RUBRIC",
    "REFRESHABLE_DEFAULT_KEYS",
    "REQUIRED_KEYS",
    "SEED_ITEMS",
    "SOURCE_DISTILLATION_GATE",
    "SOURCE_IMPERFECTION_GATE",
    "STUDENT_CONFUSION_LAYER",
    "TELEPROMPTER_DOCX_CONTRACT",
    "TRANSCRIPT_TOPIC_RELEVANCE_GATE",
    "_SEED_BY_KEY",
    "main",
    "refresh_defaults",
    "seed",
]
