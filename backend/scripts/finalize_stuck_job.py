#!/usr/bin/env python3
"""Finalize a stuck generation job from saved lessons (no AI).

Usage (Render Shell or any host with DATABASE_URL + STORAGE_DIR):

  export DATABASE_URL='postgresql://...'
  export STORAGE_DIR=/opt/render/project/src/backend/storage
  cd backend
  python scripts/finalize_stuck_job.py 51

Inspect only (no writes):

  python scripts/finalize_stuck_job.py 51 --inspect
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/...` from backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlmodel import Session  # noqa: E402

from app.crud import generation_jobs  # noqa: E402
from app.db import engine  # noqa: E402
from app.services.finalize_saved_job import (  # noqa: E402
    finalize_job_from_saved_lessons,
    inspect_saved_lessons,
    job_eligible_for_saved_finalize,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id", type=int)
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print lesson integrity report and exit without writing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Finalize even if stage/status checks would normally skip.",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        job = generation_jobs.get(session, args.job_id)
        if job is None:
            print(f"Job {args.job_id} not found", file=sys.stderr)
            return 1

        inspection = inspect_saved_lessons(job)
        report = {
            "job_id": job.id,
            "course_id": job.course_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "current_stage": job.current_stage,
            "progress_percent": job.progress_percent,
            "completed_reels_count": job.completed_reels_count,
            "total_lessons_count": job.total_lessons_count,
            "output_docx_path": job.output_docx_path,
            "eligible": job_eligible_for_saved_finalize(job),
            "inspection": {
                "ok": inspection.ok,
                "reason": inspection.reason,
                "planned_count": inspection.planned_count,
                "saved_count": inspection.saved_count,
                "unique_saved_count": inspection.unique_saved_count,
                "missing_reel_ids": list(inspection.missing_reel_ids),
                "duplicate_reel_ids": list(inspection.duplicate_reel_ids),
                "empty_script_reel_ids": list(inspection.empty_script_reel_ids),
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

        if args.inspect:
            return 0 if inspection.ok else 2

        if not inspection.ok and not args.force:
            print("Refusing to finalize: lesson integrity check failed.", file=sys.stderr)
            return 2

        updated = finalize_job_from_saved_lessons(session, job, force=True)
        if updated is None:
            print("Finalize returned None (export failed or ineligible).", file=sys.stderr)
            return 3

        print(
            json.dumps(
                {
                    "result": "completed",
                    "job_id": updated.id,
                    "status": updated.status.value,
                    "current_stage": updated.current_stage,
                    "output_docx_path": updated.output_docx_path,
                    "ai_calls": 0,
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
