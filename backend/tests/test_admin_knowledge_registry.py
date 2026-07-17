"""Admin Knowledge registry consistency — single source of truth checks."""

from __future__ import annotations

from app.data.admin_knowledge_registry import (
    EXCLUDED_FROM_STAGE_PACKS,
    KEY_CATALOG,
    OPTIONAL_SEED_KEYS,
    REFRESHABLE_DEFAULT_KEYS,
    REQUIRED_KEYS,
    STABLE_RULE_KEYS,
    STAGE_RULE_KEYS,
    key_info_public,
)
from app.data.admin_knowledge_seed import SEED_ITEMS
from app.generation.prompt_compiler import STABLE_RULE_KEYS as COMPILER_STABLE
from app.generation.prompt_compiler import _STAGE_RULE_KEYS as COMPILER_STAGE
from app.prompts.prompt_registry import PipelineStage


def test_required_keys_have_seed_content():
    seed_keys = {item["key"] for item in SEED_ITEMS}
    missing = REQUIRED_KEYS - seed_keys
    assert not missing, f"REQUIRED_KEYS missing from SEED_ITEMS: {sorted(missing)}"


def test_refreshable_subset_of_required_and_catalog():
    for key in REFRESHABLE_DEFAULT_KEYS:
        assert key in REQUIRED_KEYS
        assert KEY_CATALOG[key].refreshable is True
    for key, info in KEY_CATALOG.items():
        if info.refreshable:
            assert key in REFRESHABLE_DEFAULT_KEYS


def test_stage_keys_are_required_and_not_excluded():
    for stage, keys in STAGE_RULE_KEYS.items():
        assert isinstance(stage, PipelineStage)
        for key in keys:
            assert key in REQUIRED_KEYS, f"{key} in {stage} but not REQUIRED"
            assert key not in EXCLUDED_FROM_STAGE_PACKS


def test_stable_equals_union_of_stage_keys():
    union: set[str] = set()
    for keys in STAGE_RULE_KEYS.values():
        union.update(keys)
    assert set(STABLE_RULE_KEYS) == union
    assert "rukn_cost_hygiene_trusted_knowledge" in STABLE_RULE_KEYS
    assert "rukn_generation_presets" not in STABLE_RULE_KEYS


def test_compiler_aliases_match_registry():
    assert COMPILER_STAGE is STAGE_RULE_KEYS
    assert set(COMPILER_STABLE) == set(STABLE_RULE_KEYS)


def test_every_pipeline_stage_has_rule_map():
    assert set(STAGE_RULE_KEYS) == set(PipelineStage)


def test_catalog_public_shape():
    rows = key_info_public()
    assert len(rows) == len(KEY_CATALOG)
    by_key = {r["key"]: r for r in rows}
    assert by_key["rukn_cost_hygiene_trusted_knowledge"]["stable"] is True
    assert by_key["rukn_generation_presets"]["in_stage_packs"] is False
    assert by_key["rukn_core_rules"]["refreshable"] is False


def test_optional_seed_keys_not_required():
    assert OPTIONAL_SEED_KEYS.isdisjoint(REQUIRED_KEYS)
