"""Install and reset the immutable RUKN v1.3 standard.

There is no archive, custom-key, inactive-version, or restore path.  A reset
permanently replaces the retired rules store with the 14 shipped Markdown files.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.config import settings
from app.data.course_standard import (
    STANDARD_FILE_NAMES,
    STANDARD_VERSION,
    standard_fingerprint,
    standard_seed_items,
)
import app.db as db_pkg
from app.db import init_db
from app.models.admin_knowledge import AdminKnowledgeItem
from app.models.course import Course
from app.models.generation_job import GenerationJob

SEED_ITEMS = standard_seed_items()
_SEED_BY_KEY = {str(item["key"]): item for item in SEED_ITEMS}


def _row_matches(row: AdminKnowledgeItem, expected: dict[str, object]) -> bool:
    return (
        row.key == expected["key"]
        and row.title == expected["title"]
        and row.item_type == expected["item_type"]
        and row.content_text == expected["content_text"]
        and row.file_path == expected["file_path"]
        and row.version == 1
        and row.is_active is True
    )


def canonical_items(session: Session) -> list[AdminKnowledgeItem]:
    rows = list(session.exec(select(AdminKnowledgeItem)))
    by_key = {row.key: row for row in rows if row.key in _SEED_BY_KEY}
    return [by_key[key] for key in STANDARD_FILE_NAMES if key in by_key]


def _purge_legacy_backup_files() -> int:
    storage_root = Path(settings.storage_dir).resolve()
    target = (storage_root / "backups" / "admin_knowledge").resolve()
    target.relative_to(storage_root)
    if not target.exists():
        return 0
    removed = sum(1 for path in target.rglob("*") if path.is_file())
    shutil.rmtree(target)
    return removed


def _purge_retired_snapshots(session: Session) -> tuple[int, int]:
    def uses_retired_contract(snapshot: object) -> bool:
        if not isinstance(snapshot, dict) or snapshot.get("version") != "2.0":
            return True
        rule_pack = snapshot.get("ACTIVE_RULE_PACK")
        return not isinstance(rule_pack, dict) or (
            rule_pack.get("standard_version") != STANDARD_VERSION
            or rule_pack.get("fingerprint") != standard_fingerprint()
        )

    cleared_courses = 0
    for course in session.exec(select(Course)):
        changed = False
        if course.active_rules_snapshot_json is not None:
            course.active_rules_snapshot_json = None
            changed = True
        if course.generation_context_snapshot_json is not None and uses_retired_contract(
            course.generation_context_snapshot_json
        ):
            course.generation_context_snapshot_json = None
            changed = True
        if changed:
            session.add(course)
            cleared_courses += 1

    cleared_jobs = 0
    for job in session.exec(select(GenerationJob)):
        if job.run_snapshot_json is not None and uses_retired_contract(job.run_snapshot_json):
            job.run_snapshot_json = None
            session.add(job)
            cleared_jobs += 1
    return cleared_courses, cleared_jobs


def _replace_all(session: Session) -> dict[str, Any]:
    existing = list(session.exec(select(AdminKnowledgeItem)))
    for row in existing:
        session.delete(row)

    cleared_courses, cleared_jobs = _purge_retired_snapshots(session)
    inserted: list[AdminKnowledgeItem] = []
    for item in SEED_ITEMS:
        row = AdminKnowledgeItem(**item)
        session.add(row)
        inserted.append(row)
    session.commit()
    return {
        "removed_rows": len(existing),
        "inserted_rows": len(inserted),
        "cleared_course_snapshots": cleared_courses,
        "cleared_job_snapshots": cleared_jobs,
        "deleted_backup_files": _purge_legacy_backup_files(),
    }


def seed(session: Session) -> dict[str, Any]:
    """Synchronize once; any non-canonical state triggers a hard replacement."""
    rows = list(session.exec(select(AdminKnowledgeItem)))
    grouped: dict[str, list[AdminKnowledgeItem]] = {}
    for row in rows:
        grouped.setdefault(row.key, []).append(row)
    healthy = len(rows) == len(STANDARD_FILE_NAMES) and all(
        len(grouped.get(key, [])) == 1
        and _row_matches(grouped[key][0], _SEED_BY_KEY[key])
        for key in STANDARD_FILE_NAMES
    )
    if healthy:
        return {
            "changed": False,
            "removed_rows": 0,
            "inserted_rows": 0,
            "cleared_course_snapshots": 0,
            "cleared_job_snapshots": 0,
            "deleted_backup_files": 0,
        }
    return {"changed": True, **_replace_all(session)}


def reset_standard(session: Session) -> dict[str, Any]:
    return {"changed": True, **_replace_all(session)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the canonical RUKN v1.3 standard")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if args.reset and not args.confirm:
        print("Refusing destructive reset without --confirm")
        return 2
    init_db()
    with Session(db_pkg.engine) as session:
        report = reset_standard(session) if args.reset else seed(session)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
