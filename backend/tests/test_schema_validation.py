"""Schema validation and repair behavior for model outputs."""

import pytest
from pydantic import BaseModel

from app.generation.schema_validation import (
    MAX_SCHEMA_REPAIR_ATTEMPTS,
    SchemaValidationFailed,
    repair_instruction,
    validate_model,
)


class SampleOut(BaseModel):
    title: str
    count: int


def test_validate_model_accepts_valid_dict():
    out = validate_model(SampleOut, {"title": "Ads", "count": 2})
    assert out.title == "Ads"


def test_validate_model_raises_cleanly_on_malformed():
    with pytest.raises(SchemaValidationFailed) as exc:
        validate_model(SampleOut, {"title": "Ads"})
    assert "SampleOut" in str(exc.value)


def test_repair_instruction_is_bounded():
    err = "x" * 2000
    msg = repair_instruction(err)
    assert len(msg) < 700
    assert "validation" in msg.lower()


def test_max_repair_attempts_constant_is_small():
    assert MAX_SCHEMA_REPAIR_ATTEMPTS == 2
