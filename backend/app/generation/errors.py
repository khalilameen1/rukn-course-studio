"""Provider-error classification and clean, user-facing error copy.

`classify_provider_error` is a pure function: it only inspects the failing
exception's type name and message text, never a concrete provider's
exception classes, so it works unchanged for a test's injected failure
today and for a real provider's own exception types later without this
module needing to know anything about either.

Nothing here ever returns raw exception internals (docs/PRD.md FR-10,
"clear, actionable error state, not a raw stack trace") - callers
(app/generation/orchestrator.py) should always show one of the fixed
sentences below, never `str(exc)` itself. The raw text may still go into
the short, truncated, internal-only `log_json` entry, since that's never
returned to the end user.
"""

ErrorCategory = str

_CATEGORIES: tuple[str, ...] = (
    "rate_limit",
    "insufficient_quota",
    "timeout",
    "provider_unavailable",
    "malformed_response",
    "context_too_long",
    "runaway_guard",
    "unknown",
)


def classify_provider_error(exc: Exception) -> str:
    """One of `_CATEGORIES` above, defaulting to `"unknown"`."""
    haystack = f"{type(exc).__name__} {exc}".lower()

    if "emergencyrunawayguard" in haystack or "runaway guard" in haystack:
        return "runaway_guard"
    if "rate limit" in haystack or "ratelimit" in haystack or "429" in haystack:
        return "rate_limit"
    if (
        "quota" in haystack
        or "insufficient" in haystack
        or "credit" in haystack
        or "credit balance" in haystack
        or "billing" in haystack
    ):
        return "insufficient_quota"
    if "timeout" in haystack or "timed out" in haystack:
        return "timeout"
    if "connection" in haystack or "unavailable" in haystack or "503" in haystack:
        return "provider_unavailable"
    if "invalid" in haystack or "malformed" in haystack:
        return "malformed_response"
    if (
        "context length" in haystack
        or "context_length" in haystack
        or "too long" in haystack
        or "token limit" in haystack
        or "context limit" in haystack
        or "maximum context" in haystack
    ):
        return "context_too_long"
    return "unknown"


# Shown when the run has already saved usable work (job ends PARTIAL) -
# always the required "...after saving completed sections." clause plus
# one short, jargon-free, category-specific reason.
ERROR_CATEGORY_MESSAGES: dict[str, str] = {
    "rate_limit": (
        "Generation stopped after saving completed sections — "
        "the AI provider is rate-limiting requests."
    ),
    "insufficient_quota": (
        "Generation stopped after saving completed sections — "
        "the AI provider account is out of credits."
    ),
    "timeout": (
        "Generation stopped after saving completed sections — "
        "the AI provider took too long to respond."
    ),
    "provider_unavailable": (
        "Generation stopped after saving completed sections — "
        "the AI provider is temporarily unavailable."
    ),
    "malformed_response": (
        "Generation stopped after saving completed sections — "
        "the AI provider returned a response we couldn't use."
    ),
    "context_too_long": (
        "Generation stopped after saving completed sections — "
        "the course content became too long for the AI provider to process."
    ),
    "runaway_guard": (
        "Stopped by emergency runaway guard after saving completed sections."
    ),
    "unknown": (
        "Generation stopped after saving completed sections — "
        "an unexpected error occurred."
    ),
}

# Shown when nothing usable was saved yet (job ends FAILED) - no
# "completed sections" claim, since there aren't any.
ERROR_CATEGORY_MESSAGES_NOTHING_SAVED: dict[str, str] = {
    "rate_limit": "Generation failed before anything could be saved — the AI provider is rate-limiting requests.",
    "insufficient_quota": (
        "Generation failed before anything could be saved — "
        "the AI provider account is out of credits."
    ),
    "timeout": (
        "Generation failed before anything could be saved — "
        "the AI provider took too long to respond."
    ),
    "provider_unavailable": (
        "Generation failed before anything could be saved — "
        "the AI provider is temporarily unavailable."
    ),
    "malformed_response": (
        "Generation failed before anything could be saved — "
        "the AI provider returned a response we couldn't use."
    ),
    "context_too_long": (
        "Generation failed before anything could be saved — "
        "the course content became too long for the AI provider to process."
    ),
    "runaway_guard": "Stopped by emergency runaway guard.",
    "unknown": "Generation failed before anything could be saved — an unexpected error occurred.",
}


def error_message_for(category: str, *, has_saved_work: bool) -> str:
    """The clean, user-facing sentence for a category - never raw
    exception text. Falls back to the category's `"unknown"` copy for an
    unrecognized category rather than raising: this sits in an error path
    that must never itself crash."""
    messages = ERROR_CATEGORY_MESSAGES if has_saved_work else ERROR_CATEGORY_MESSAGES_NOTHING_SAVED
    return messages.get(category, messages["unknown"])
