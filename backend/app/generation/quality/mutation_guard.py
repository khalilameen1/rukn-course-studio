"""Post-pass invariant — any word-changing edit re-opens all quality gates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def script_fingerprint(text: str) -> str:
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class PassedScriptLock:
    reel_id: str
    fingerprint: str
    script_text: str
    unlocked_for_format_only: bool = False


@dataclass
class MutationGuard:
    locks: dict[str, PassedScriptLock] = field(default_factory=dict)

    def mark_passed(self, reel_id: str, script_text: str) -> None:
        self.locks[reel_id] = PassedScriptLock(
            reel_id=reel_id,
            fingerprint=script_fingerprint(script_text),
            script_text=script_text,
        )

    def assert_unchanged_or_requalify(self, reel_id: str, script_text: str) -> list[str]:
        lock = self.locks.get(reel_id)
        if lock is None:
            return []
        if script_fingerprint(script_text) != lock.fingerprint:
            # Invalidate pass — caller must re-run gates.
            del self.locks[reel_id]
            return [
                f"content_mutated_after_pass:{reel_id}:re-run all content/language gates"
            ]
        return []

    def format_only_allowed(self, reel_id: str, before: str, after: str) -> bool:
        """True when only whitespace/newlines changed (no word tokens)."""
        return " ".join(before.split()) == " ".join(after.split())
