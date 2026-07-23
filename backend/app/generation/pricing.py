"""Approximate OpenAI API pricing used only for the internal usage estimate.

Values are standard GPT-5.6 list pricing at the migration date. The UI must
continue to label these as estimates, never an invoice or account balance.
"""
from __future__ import annotations

PRICING_USD_PER_MILLION_TOKENS: tuple[tuple[str, dict[str, float]], ...] = (
    ("gpt-5.6-sol", {"input": 5.0, "output": 30.0}),
    ("gpt-5.6-pro", {"input": 5.0, "output": 30.0}),
    ("gpt-5.6", {"input": 5.0, "output": 30.0}),
    ("gpt-5.6-terra", {"input": 2.5, "output": 15.0}),
    ("gpt-5.6-luna", {"input": 1.0, "output": 6.0}),
)
DEFAULT_PRICING_USD_PER_MILLION_TOKENS = {"input": 5.0, "output": 30.0}

def _pricing_for_model(model_name: str) -> dict[str, float]:
    lowered = (model_name or "").lower()
    for key, pricing in PRICING_USD_PER_MILLION_TOKENS:
        if key in lowered:
            return pricing
    return DEFAULT_PRICING_USD_PER_MILLION_TOKENS

def estimate_cost_usd(model_name: str, input_tokens: int | None, output_tokens: int | None,
                      cache_read_tokens: int | None = None, cache_write_tokens: int | None = None) -> float:
    pricing = _pricing_for_model(model_name)
    input_cost = (input_tokens or 0) / 1_000_000 * pricing["input"]
    output_cost = (output_tokens or 0) / 1_000_000 * pricing["output"]
    cache_read_cost = (cache_read_tokens or 0) / 1_000_000 * pricing["input"] * 0.1
    cache_write_cost = (cache_write_tokens or 0) / 1_000_000 * pricing["input"] * 1.25
    return round(input_cost + output_cost + cache_read_cost + cache_write_cost, 6)
