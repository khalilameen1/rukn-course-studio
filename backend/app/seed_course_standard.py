"""CLI entrypoint for installing the canonical RUKN v1.3 standard.

Run from ``backend/``:

    python -m app.seed_course_standard
    python -m app.seed_course_standard --reset --confirm
"""

from app.data.admin_knowledge.seed_loader import main


if __name__ == "__main__":
    raise SystemExit(main())
