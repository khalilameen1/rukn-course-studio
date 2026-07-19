"""Shared Pydantic / Form before-validators for API boundary mistakes."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BeforeValidator

from app.models.enums import (
    AddressForm,
    CourseFamily,
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    ItemType,
    JobStatus,
    Priority,
    SourceCategory,
    SourceOrigin,
    StructureMode,
    TargetMarket,
    WebResearchMode,
)
from app.services.enum_coerce import (
    coerce_priority,
    coerce_source_category,
    coerce_source_origin,
    coerce_str_enum,
)
from app.services.json_coerce import coerce_json_dict, coerce_json_list


def _enum(enum_cls):  # type: ignore[no-untyped-def]
    def _inner(value: Any) -> Any:
        return coerce_str_enum(enum_cls, value)

    return _inner


# Annotated types — use on schema fields and FastAPI Form()/Query() params.
SourceCategoryLoose = Annotated[SourceCategory, BeforeValidator(coerce_source_category)]
PriorityLoose = Annotated[Priority, BeforeValidator(coerce_priority)]
SourceOriginLoose = Annotated[
    SourceOrigin | None, BeforeValidator(coerce_source_origin)
]
JobStatusLoose = Annotated[JobStatus, BeforeValidator(_enum(JobStatus))]
StructureModeLoose = Annotated[StructureMode, BeforeValidator(_enum(StructureMode))]
ExplanationLevelLoose = Annotated[
    ExplanationLevel, BeforeValidator(_enum(ExplanationLevel))
]
GenerationPresetLoose = Annotated[
    GenerationPreset, BeforeValidator(_enum(GenerationPreset))
]
GenerationQualityModeLoose = Annotated[
    GenerationQualityMode, BeforeValidator(_enum(GenerationQualityMode))
]
WebResearchModeLoose = Annotated[
    WebResearchMode, BeforeValidator(_enum(WebResearchMode))
]
TargetMarketLoose = Annotated[TargetMarket, BeforeValidator(_enum(TargetMarket))]
CourseFamilyLoose = Annotated[CourseFamily, BeforeValidator(_enum(CourseFamily))]
AddressFormLoose = Annotated[AddressForm, BeforeValidator(_enum(AddressForm))]
ItemTypeLoose = Annotated[ItemType, BeforeValidator(_enum(ItemType))]

JsonObjectLoose = Annotated[dict[str, Any] | None, BeforeValidator(coerce_json_dict)]
JsonArrayLoose = Annotated[list[Any], BeforeValidator(coerce_json_list)]
