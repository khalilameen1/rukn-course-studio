"""Public import surface for the one unified v2 run snapshot contract."""

from app.generation.quality.context_snapshot import (
    REQUIRED_STATE_KEYS,
    SNAPSHOT_VERSION,
    GenerationContextSnapshot,
    SnapshotMismatchError,
    assert_snapshot_compatible,
    build_config_inputs,
    build_generation_context_snapshot,
    fingerprint_value,
)

__all__ = [
    "REQUIRED_STATE_KEYS",
    "SNAPSHOT_VERSION",
    "GenerationContextSnapshot",
    "SnapshotMismatchError",
    "assert_snapshot_compatible",
    "build_config_inputs",
    "build_generation_context_snapshot",
    "fingerprint_value",
]
