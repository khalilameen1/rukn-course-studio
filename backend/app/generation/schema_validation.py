"""Strict AI output schema validation helpers.

Anthropic path already validates via tool schemas + MAX_ATTEMPTS=2.
This module centralizes validate/repair messaging for Fake/tests/orchestrator.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

MAX_SCHEMA_REPAIR_ATTEMPTS = 2


class SchemaValidationFailed(ValueError):
    """Exhausted schema repair attempts — run/lesson should stop cleanly."""

    def __init__(self, schema_name: str, error: str) -> None:
        self.schema_name = schema_name
        self.error = error
        super().__init__(f"{schema_name} schema invalid after retries: {error}")


def validate_model(schema: type[T], data: dict | BaseModel) -> T:
    if isinstance(data, schema):
        return data
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationFailed(schema.__name__, str(exc)) from exc


def repair_instruction(error: str) -> str:
    return (
        "Your previous structured output failed validation: "
        f"{error[:500]}. Return ONLY valid structured data matching the schema."
    )
