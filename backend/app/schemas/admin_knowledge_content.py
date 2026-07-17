"""Typed content for JSON Admin Knowledge items."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator


class ForbiddenPhraseEntry(BaseModel):
    phrase: str = Field(min_length=1)
    severity: Literal["high", "medium", "low"]
    replacement_hint: str = Field(min_length=1)


class ForbiddenPhrasesContent(BaseModel):
    description: str = Field(min_length=1)
    phrases: list[ForbiddenPhraseEntry] = Field(min_length=1)


class QualityRubricCheck(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class QualityRubricContent(BaseModel):
    description: str = Field(min_length=1)
    checks: list[QualityRubricCheck] = Field(min_length=1)


class GenerationPresetEntry(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GenerationPresetsContent(BaseModel):
    description: str = Field(min_length=1)
    default: str = Field(min_length=1)
    presets: list[GenerationPresetEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def default_must_exist(self) -> GenerationPresetsContent:
        ids = {p.id for p in self.presets}
        if self.default not in ids:
            raise ValueError(
                f"default {self.default!r} is not among preset ids {sorted(ids)}"
            )
        return self


_JSON_SCHEMAS: dict[str, type[BaseModel]] = {
    "rukn_forbidden_phrases": ForbiddenPhrasesContent,
    "rukn_quality_rubric": QualityRubricContent,
    "rukn_generation_presets": GenerationPresetsContent,
}


def validate_admin_knowledge_content(
    *,
    key: str,
    item_type: str,
    content_text: str | None,
) -> None:
    """Raise ValueError with a clear message when JSON system content is invalid."""
    type_value = getattr(item_type, "value", item_type)
    if str(type_value).lower() != "json":
        return
    schema = _JSON_SCHEMAS.get(key)
    if schema is None:
        # Custom JSON keys: must at least be parseable JSON object/array.
        if content_text is None or not str(content_text).strip():
            raise ValueError("JSON knowledge items require non-empty content_text.")
        try:
            json.loads(content_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"content_text is not valid JSON: {exc}") from exc
        return

    if content_text is None or not str(content_text).strip():
        raise ValueError(f"{key} requires JSON content_text.")
    try:
        payload = json.loads(content_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{key} content_text is not valid JSON: {exc}") from exc
    try:
        schema.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{key} failed schema validation: {exc}") from exc
