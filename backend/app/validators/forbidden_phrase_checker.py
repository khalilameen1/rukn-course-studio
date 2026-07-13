"""Checks generated text against Rukn's forbidden-phrases admin knowledge
item (see app/seed_admin_knowledge.py `rukn-forbidden-phrases`). Plain
substring matching - no AI, no embeddings.
"""

import json
from dataclasses import dataclass

FORBIDDEN_PHRASES_KEY = "rukn-forbidden-phrases"


@dataclass
class ForbiddenPhraseMatch:
    phrase: str
    severity: str
    replacement_hint: str | None


def load_forbidden_phrases(rules_context: dict[str, str]) -> list[dict]:
    """Parse the active `rukn-forbidden-phrases` admin knowledge item.

    Never raises: a missing item or malformed JSON just means no phrases
    are checked, rather than breaking the whole pipeline over formatting.
    """
    raw = rules_context.get(FORBIDDEN_PHRASES_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    phrases = data.get("phrases") if isinstance(data, dict) else None
    return phrases if isinstance(phrases, list) else []


def check_forbidden_phrases(
    text: str, rules_context: dict[str, str]
) -> list[ForbiddenPhraseMatch]:
    """Every forbidden phrase found verbatim in `text`."""
    phrases = load_forbidden_phrases(rules_context)
    if not text or not phrases:
        return []

    matches: list[ForbiddenPhraseMatch] = []
    for entry in phrases:
        if not isinstance(entry, dict):
            continue
        phrase = entry.get("phrase")
        if phrase and phrase in text:
            matches.append(
                ForbiddenPhraseMatch(
                    phrase=phrase,
                    severity=entry.get("severity", "medium"),
                    replacement_hint=entry.get("replacement_hint"),
                )
            )
    return matches
