"""Content Atom Ledger — prevent knowledge loss during compression/rewrite."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContentAtom(BaseModel):
    atom_id: str
    label: str
    source_id: str | None = None
    importance: str = "core"  # core | supporting | optional
    included_lesson_id: str | None = None
    status: str = "planned"  # planned | included | merged | excluded
    exclusion_reason: str = ""
    merged_from: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class ContentAtomLedger(BaseModel):
    atoms: list[ContentAtom] = Field(default_factory=list)

    def by_id(self) -> dict[str, ContentAtom]:
        return {a.atom_id: a for a in self.atoms}

    def core_atoms(self) -> list[ContentAtom]:
        return [a for a in self.atoms if a.importance == "core"]

    def missing_core(self) -> list[ContentAtom]:
        return [
            a
            for a in self.core_atoms()
            if a.status not in {"included", "merged"} or not a.included_lesson_id
        ]

    def record_merge(
        self, keeper_lesson_id: str, donor_lesson_id: str, donor_atom_ids: list[str]
    ) -> None:
        index = self.by_id()
        for atom_id in donor_atom_ids:
            atom = index.get(atom_id)
            if atom is None:
                continue
            atom.status = "merged"
            atom.included_lesson_id = keeper_lesson_id
            if donor_lesson_id not in atom.merged_from:
                atom.merged_from.append(donor_lesson_id)

    def assign(self, atom_id: str, lesson_id: str) -> None:
        atom = self.by_id().get(atom_id)
        if atom is None:
            return
        atom.included_lesson_id = lesson_id
        atom.status = "included"

    def coverage_delta(
        self, before_ids: set[str], after_ids: set[str]
    ) -> list[str]:
        return sorted(before_ids - after_ids)


def atoms_from_reel_plan(reel_id: str, must_cover: list[str], *, importance: str = "core") -> list[ContentAtom]:
    out: list[ContentAtom] = []
    for i, item in enumerate(must_cover or []):
        label = (item or "").strip()
        if not label:
            continue
        out.append(
            ContentAtom(
                atom_id=f"{reel_id}:a{i+1}",
                label=label,
                importance=importance,
                included_lesson_id=reel_id,
                status="included",
            )
        )
    if not out:
        out.append(
            ContentAtom(
                atom_id=f"{reel_id}:outcome",
                label=f"outcome:{reel_id}",
                importance="core",
                included_lesson_id=reel_id,
                status="included",
            )
        )
    return out


def build_ledger_from_course_map(course_map) -> ContentAtomLedger:
    atoms: list[ContentAtom] = []
    for module in course_map.modules:
        for reel in module.reels:
            atoms.extend(atoms_from_reel_plan(reel.reel_id, list(reel.must_cover or [])))
    return ContentAtomLedger(atoms=atoms)


def assert_no_core_atom_loss(
    before: ContentAtomLedger, after: ContentAtomLedger
) -> list[str]:
    """Return error strings if core atoms disappeared without merge/include."""
    before_core = {a.atom_id: a for a in before.core_atoms()}
    after_ids = {a.atom_id for a in after.atoms}
    errors: list[str] = []
    for atom_id, atom in before_core.items():
        if atom_id not in after_ids:
            # Allow if label preserved under merged atom with same label.
            if not any(a.label == atom.label and a.status in {"included", "merged"} for a in after.atoms):
                errors.append(f"CONTENT_ATOM_MISSING:{atom_id}:{atom.label}")
            continue
        after_atom = after.by_id()[atom_id]
        if after_atom.status == "excluded" and after_atom.importance == "core":
            errors.append(
                f"CONTENT_ATOM_MISSING:{atom_id}:excluded:{after_atom.exclusion_reason or 'no reason'}"
            )
        elif after_atom.status in {"included", "merged"} and not after_atom.included_lesson_id:
            errors.append(f"CONTENT_ATOM_MISSING:{atom_id}:no_lesson")
    return errors
