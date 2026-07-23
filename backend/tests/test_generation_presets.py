"""Tests for app/generation/presets.py - config only, no provider wiring yet."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.generation.presets import (
    DEFAULT_GENERATION_PRESET,
    PRESET_DESCRIPTIONS,
    PRESET_TEMPERATURES,
    GenerationPreset,
    resolve_generation_settings,
)
from app.models.course import Course
from app.models.enums import StructureMode


def test_default_preset_is_balanced():
    assert DEFAULT_GENERATION_PRESET == GenerationPreset.BALANCED


def test_all_five_required_presets_exist():
    assert {preset.value for preset in GenerationPreset} == {
        "conservative",
        "balanced",
        "creative",
        "fusion",
        "strict_teleprompter",
    }


def test_every_preset_has_a_non_empty_description():
    for preset in GenerationPreset:
        assert PRESET_DESCRIPTIONS[preset]


def test_every_preset_has_a_temperature():
    for preset in GenerationPreset:
        assert isinstance(PRESET_TEMPERATURES[preset], float)


def test_resolve_generation_settings_returns_preset_and_temperature():
    settings_ = resolve_generation_settings(GenerationPreset.CREATIVE)
    assert settings_ == {
        "preset": "creative",
        "effective_preset": "creative",
        "temperature": PRESET_TEMPERATURES[GenerationPreset.CREATIVE],
    }


def test_fusion_aliases_to_balanced_settings():
    settings_ = resolve_generation_settings(GenerationPreset.FUSION)
    assert settings_["preset"] == "fusion"
    assert settings_["effective_preset"] == "balanced"
    assert settings_["temperature"] == PRESET_TEMPERATURES[GenerationPreset.BALANCED]


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_course_defaults_to_balanced_preset(session):
    course = Course(
        title="Test course",
        audience="testers",
        outcome="test things",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
    )
    session.add(course)
    session.commit()
    session.refresh(course)

    assert course.generation_preset == GenerationPreset.BALANCED


def test_invalid_generation_preset_on_create_course_returns_422():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/courses",
        json={
            "title": "Bad preset course",
            "audience": "testers",
            "outcome": "test things",
            "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
            "generation_preset": "not_a_real_preset",
        },
    )
    assert response.status_code == 422
