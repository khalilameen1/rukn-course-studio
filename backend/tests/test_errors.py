"""Tests for app/generation/errors.py - provider error classification and
the clean, user-facing error copy shown instead of raw exception text."""

import pytest

from app.generation.errors import (
    ERROR_CATEGORY_MESSAGES,
    ERROR_CATEGORY_MESSAGES_NOTHING_SAVED,
    classify_provider_error,
    error_message_for,
)


@pytest.mark.parametrize(
    "message,expected_category",
    [
        ("Rate limit exceeded, please retry", "rate_limit"),
        ("HTTP 429 Too Many Requests", "rate_limit"),
        ("insufficient_quota: you have run out of credits", "insufficient_quota"),
        ("Request timed out after 30s", "timeout"),
        ("Connection timeout while calling the provider", "timeout"),
        ("Service unavailable (503)", "provider_unavailable"),
        ("Could not establish a connection to the API", "provider_unavailable"),
        ("Received an invalid/malformed response from the model", "malformed_response"),
        ("Context length exceeded: too long for this model", "context_too_long"),
        ("token limit exceeded for this request", "context_too_long"),
        ("Your credit balance is too low to access the Anthropic API", "insufficient_quota"),
        ("Please add more credits to your account", "insufficient_quota"),
        ("Billing issue: please update your payment method", "insufficient_quota"),
        ("Prompt exceeds the context limit for this model", "context_too_long"),
        ("Input length exceeds the maximum context length allowed", "context_too_long"),
        ("Something completely unexpected happened", "unknown"),
    ],
)
def test_classify_provider_error_categories(message, expected_category):
    assert classify_provider_error(RuntimeError(message)) == expected_category


def test_classify_provider_error_uses_exception_type_name_too():
    """Classification also looks at the exception's class name, not just
    its message - useful for a real provider's own typed exceptions
    (e.g. `RateLimitError`) later."""

    class RateLimitError(Exception):
        pass

    assert classify_provider_error(RateLimitError("try again later")) == "rate_limit"


def test_error_message_for_has_saved_work_mentions_saved_sections():
    for category, message in ERROR_CATEGORY_MESSAGES.items():
        assert error_message_for(category, has_saved_work=True) == message
        assert "saving completed sections" in message


def test_error_message_for_no_saved_work_does_not_claim_anything_was_saved():
    for category, message in ERROR_CATEGORY_MESSAGES_NOTHING_SAVED.items():
        assert error_message_for(category, has_saved_work=False) == message
        assert "saving completed sections" not in message


def test_error_message_for_unknown_category_falls_back_safely():
    assert (
        error_message_for("something-made-up", has_saved_work=True)
        == ERROR_CATEGORY_MESSAGES["unknown"]
    )
    assert (
        error_message_for("something-made-up", has_saved_work=False)
        == ERROR_CATEGORY_MESSAGES_NOTHING_SAVED["unknown"]
    )
