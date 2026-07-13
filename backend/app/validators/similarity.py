"""Shared string-similarity helper for the local validators - plain
difflib, no embeddings.
"""

import difflib


def text_similarity(a: str, b: str) -> float:
    """0.0-1.0 similarity ratio between two strings, case/whitespace-insensitive."""
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def opening_words(script_text: str, word_count: int) -> str:
    words = (script_text or "").strip().split()
    return " ".join(words[:word_count])
