"""Run snapshot metadata (§2 & §3): a small, secret-free, immutable record
of exactly which admin-knowledge content, prompt-compiler version, preset,
and provider/model produced one `GenerationJob` run.

Design note - why `GenerationJob`, not `Course`: `Course.active_rules_
snapshot_json` already existed on the model before this pass, but a grep
of the codebase confirms it was never populated anywhere. It's also the
wrong model for this: `Course` is one mutable row reused across every run
for that course, so writing a snapshot there on each run would silently
overwrite the previous run's snapshot the next time generation runs -
exactly what "old generation runs should still show which snapshot they
used" rules out. This module instead builds the dict that
`app/generation/orchestrator.py` stores on `GenerationJob.run_snapshot_json`
- one immutable row per run, written once near the start of that run and
never mutated again. `Course.active_rules_snapshot_json` is left in place,
unused, with an updated comment on the model pointing here - see
`app/models/course.py`.

Only short content hashes are stored, never raw admin-knowledge or source
text - see `_short_hash` below. Every field here is deliberately
non-secret and safe to eventually return to the frontend (see
`GenerationJobRead.run_snapshot`): no API key, no `AUTH_SECRET_KEY`, no
`DATABASE_URL`, ever.

The three specifically-called-out hashes (teleprompter contract, forbidden
phrases, quality rubric) are not duplicated as separate fields - they are
simply whichever entries of `admin_knowledge_snapshot` happen to be keyed
`rukn_teleprompter_docx_contract` / `rukn_forbidden_phrases` /
`rukn_quality_rubric` (only present if that admin-knowledge item was
active for this run). Documented here, and in README.md "Prompt/rules
snapshotting", so this mapping is easy to find.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.config import Settings
from app.config import settings as default_settings
from app.generation.prompt_compiler import PROMPT_COMPILER_VERSION
from app.version import get_app_commit

# Short enough to keep run_snapshot_json small (per the request: "if full
# snapshot storage is too heavy, store compact content hashes plus enough
# metadata"), long enough that an accidental collision between two
# genuinely different admin-knowledge texts is not a practical concern for
# this traceability use case.
HASH_LENGTH = 16


def _short_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:HASH_LENGTH]


def build_run_snapshot(
    *,
    rules_context: dict[str, str],
    generation_preset: str,
    source_ids_used: list[int],
    generation_quality_mode: str = "premium",
    web_research_mode: str = "autonomous_gap_fill",
    config: Settings = default_settings,
) -> dict:
    """Build the dict to store verbatim on `GenerationJob.run_snapshot_json`.

    `rules_context` should be the *full* active-rules dict as loaded by
    `app/generation/orchestrator.py` `_load_active_rules` (not one already
    narrowed to a single stage via `select_rules_for_stage`) - the snapshot
    is meant to capture everything that was active for the run, not just
    one stage's slice of it.
    """
    provider = (config.ai_provider or "fake").strip().lower()
    model = config.ai_model_name if provider == "anthropic" else "fake"

    admin_knowledge_snapshot = {key: _short_hash(text) for key, text in rules_context.items()}

    return {
        "admin_knowledge_snapshot": admin_knowledge_snapshot,
        "prompt_compiler_version": PROMPT_COMPILER_VERSION,
        "generation_preset": generation_preset,
        "generation_quality_mode": generation_quality_mode,
        "web_research_mode": web_research_mode,
        "provider": provider,
        "model": model,
        "source_ids_used": list(source_ids_used),
        "app_commit": get_app_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
