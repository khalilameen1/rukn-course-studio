"""Tolerant enum storage + GenerationJobRead null/NAME coercion for Generate 500s."""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db_enums import sa_str_enum
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode
from app.models.generation_job import GenerationJob
from app.schemas.generation_job import GenerationJobRead


def test_sa_str_enum_loads_name_and_value(tmp_path):
    from sqlalchemy import Column
    from sqlmodel import Field

    class Probe(SQLModel, table=True):
        __tablename__ = "enum_probe"
        id: int | None = Field(default=None, primary_key=True)
        status: JobStatus = Field(sa_column=Column(sa_str_enum(JobStatus), nullable=False))

    engine = create_engine(f"sqlite:///{tmp_path / 'enum_probe.db'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO enum_probe (id, status) VALUES (1, 'RUNNING')"))
        conn.execute(text("INSERT INTO enum_probe (id, status) VALUES (2, 'running')"))

    with Session(engine) as session:
        rows = list(session.exec(select(Probe).order_by(Probe.id)))
    assert rows[0].status == JobStatus.RUNNING
    assert rows[1].status == JobStatus.RUNNING

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE enum_probe SET status = :v WHERE id = 1"),
            {"v": JobStatus.COMPLETED},
        )
    # bind param should store value
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT status FROM enum_probe WHERE id = 1")).scalar()
    assert stored == "completed"


def test_generation_job_read_coerces_nulls_and_names():
    now = datetime.now(timezone.utc)
    job = GenerationJob(
        id=1,
        course_id=1,
        status="RUNNING",  # type: ignore[arg-type]
        cancel_requested=None,  # type: ignore[arg-type]
        current_stage="generating",
        progress_percent=None,  # type: ignore[arg-type]
        completed_modules_count=None,  # type: ignore[arg-type]
        waste_warnings_json=None,  # type: ignore[arg-type]
        generation_quality_mode="PREMIUM",  # type: ignore[arg-type]
        web_research_mode="AUTONOMOUS_GAP_FILL",  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )
    read = GenerationJobRead.model_validate(job)
    assert read.status == JobStatus.RUNNING
    assert read.cancel_requested is False
    assert read.progress_percent == 0
    assert read.completed_modules_count == 0
    assert read.waste_warnings_json == []
    assert read.generation_quality_mode == GenerationQualityMode.PREMIUM
    assert read.web_research_mode == WebResearchMode.AUTONOMOUS_GAP_FILL
