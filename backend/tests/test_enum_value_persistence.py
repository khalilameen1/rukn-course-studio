"""Enum value persistence — mixed NAME/VALUE rows must not 500 course reads."""

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import _normalize_str_enum_storage
from app.models.course import Course
from app.models.enums import (
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    StructureMode,
    TargetMarket,
    WebResearchMode,
)


def test_course_orm_reads_value_stored_enums(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'enum_values.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO courses ("
                "title, audience, outcome, structure_mode, explanation_level, "
                "generation_preset, generation_quality_mode, web_research_mode, "
                "target_market, status, course_type, created_at, updated_at"
                ") VALUES ("
                "'Mixed Enum Course', 'a', 'o', 'CONNECTED_NO_MODULES', 'FINAL_ONLY', "
                "'BALANCED', 'premium', 'autonomous_gap_fill', 'egypt', 'draft', "
                "'practical_skill', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                ")"
            )
        )

    # Before normalize: NAME-style structure_mode would fail under values_callable.
    _normalize_str_enum_storage()

    with Session(engine) as session:
        course = session.exec(select(Course)).one()
        assert course.structure_mode == StructureMode.CONNECTED_NO_MODULES
        assert course.explanation_level == ExplanationLevel.FINAL_ONLY
        assert course.generation_preset == GenerationPreset.BALANCED
        assert course.generation_quality_mode == GenerationQualityMode.PREMIUM
        assert course.web_research_mode == WebResearchMode.AUTONOMOUS_GAP_FILL
        assert course.target_market == TargetMarket.EGYPT


def test_course_create_persists_enum_values(tmp_path, monkeypatch):
    import app.db as db_module
    from app.crud import courses

    engine = create_engine(f"sqlite:///{tmp_path / 'enum_create.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        created = courses.create(
            session,
            title="Value Persist",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
            generation_preset=GenerationPreset.BALANCED,
            generation_quality_mode=GenerationQualityMode.PREMIUM,
            target_market=TargetMarket.EGYPT,
            web_research_mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        )
        cid = created.id

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT structure_mode, generation_quality_mode, target_market "
                "FROM courses WHERE id = :id"
            ),
            {"id": cid},
        ).one()
    assert row == ("connected_no_modules", "premium", "egypt")

    with Session(engine) as session:
        loaded = session.get(Course, cid)
        assert loaded is not None
        assert loaded.generation_quality_mode == GenerationQualityMode.PREMIUM


def test_legacy_source_category_aliases_normalize(tmp_path, monkeypatch):
    import app.db as db_module
    from app.models.course_source import CourseSource
    from app.models.enums import SourceCategory

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_src.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO courses ("
                "title, audience, outcome, structure_mode, explanation_level, "
                "generation_preset, generation_quality_mode, web_research_mode, "
                "target_market, status, course_type, created_at, updated_at"
                ") VALUES ("
                "'Legacy Src', 'a', 'o', 'connected_no_modules', 'final_only', "
                "'balanced', 'premium', 'autonomous_gap_fill', 'egypt', 'draft', "
                "'practical_skill', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                ")"
            )
        )
        cid = conn.execute(text("SELECT id FROM courses")).scalar()
        conn.execute(
            text(
                "INSERT INTO course_sources ("
                "course_id, source_category, priority, status, include_in_generation, created_at"
                ") VALUES (:cid, 'NOTES', 'medium', 'ready', 1, CURRENT_TIMESTAMP)"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO course_sources ("
                "course_id, source_category, priority, status, include_in_generation, created_at"
                ") VALUES (:cid, 'MAIN_CONTENT', 'HIGH', 'ready', 1, CURRENT_TIMESTAMP)"
            ),
            {"cid": cid},
        )

    _normalize_str_enum_storage()

    with Session(engine) as session:
        rows = list(session.exec(select(CourseSource)))
    assert {r.source_category for r in rows} == {
        SourceCategory.USER_NOTES,
        SourceCategory.SCIENTIFIC_REFERENCE,
    }
    assert all(r.priority.value == "medium" or r.priority.value == "high" for r in rows)
