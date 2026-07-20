"""Canonical RUKN v1.3 standard loader (legacy import path)."""

from app.data.admin_knowledge.seed_loader import (
    SEED_ITEMS,
    _SEED_BY_KEY,
    canonical_items,
    main,
    reset_standard,
    seed,
)
from app.data.course_standard import (
    STANDARD_FILE_NAMES,
    STANDARD_KEYS,
    STANDARD_VERSION,
    load_standard_files,
    standard_fingerprint,
    standard_manifest,
)

__all__ = [
    "SEED_ITEMS",
    "STANDARD_FILE_NAMES",
    "STANDARD_KEYS",
    "STANDARD_VERSION",
    "_SEED_BY_KEY",
    "canonical_items",
    "load_standard_files",
    "main",
    "reset_standard",
    "seed",
    "standard_fingerprint",
    "standard_manifest",
]
