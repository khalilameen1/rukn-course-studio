"""Generation consumes only the complete canonical standard."""

from sqlmodel import Session, SQLModel, create_engine

from app.data.admin_knowledge.seed_loader import seed
from app.data.course_standard import STANDARD_FILE_NAMES, load_standard_files
from app.generation.orchestrator import _load_active_rules


def test_load_active_rules_is_exact_canonical_package(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rules.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
        rules = _load_active_rules(session)
        assert tuple(rules) == STANDARD_FILE_NAMES
        assert rules == load_standard_files()


def test_source_authority_firewall_is_in_canonical_package():
    body = "\n".join(load_standard_files().values()).lower()
    assert "authority" in body
    assert "source" in body
    assert "style" in body or "voice" in body
