"""Hardcoded, approximate Anthropic pricing table (AI Usage Center, §5).

*** These are placeholder/approximate values, not fetched from any live
pricing API. Check them against Anthropic's current published pricing
(https://www.anthropic.com/pricing) before trusting any cost figure this
module computes for real budgeting decisions. Every cost figure this app
shows is explicitly labeled "estimated app usage" - never a real account
balance - see app/routers/ai_usage.py. ***

Keyed by a case-insensitive substring match against the configured model
name (e.g. "claude-sonnet-5" matches the "sonnet" entry) so this table
never needs to track Anthropic's exact model-slug naming.
"""

from __future__ import annotations

# USD per 1,000,000 tokens. Approximate as of this pass's authoring -
# update against Anthropic's current pricing page before relying on this
# for anything beyond a rough estimate.
PRICING_USD_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "opus": {"input": 15.0, "output": 75.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 0.80, "output": 4.0},
}

# Used when no substring above matches the configured model name - a
# Sonnet-like middle-of-the-road estimate rather than refusing to compute
# anything at all.
DEFAULT_PRICING_USD_PER_MILLION_TOKENS: dict[str, float] = {"input": 3.0, "output": 15.0}


def _pricing_for_model(model_name: str) -> dict[str, float]:
    lowered = (model_name or "").lower()
    for key, pricing in PRICING_USD_PER_MILLION_TOKENS.items():
        if key in lowered:
            return pricing
    return DEFAULT_PRICING_USD_PER_MILLION_TOKENS


def estimate_cost_usd(
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float:
    """Rough estimated cost in USD for one call - see module docstring.

    Never raises: missing token counts are treated as 0 rather than
    failing the caller (app/generation/orchestrator.py records a usage
    event either way).
    """
    pricing = _pricing_for_model(model_name)
    input_cost = (input_tokens or 0) / 1_000_000 * pricing["input"]
    output_cost = (output_tokens or 0) / 1_000_000 * pricing["output"]
    return round(input_cost + output_cost, 6)
