"""Terminology + Claim ledgers (internal, never DOCX)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TermEntry(BaseModel):
    original_term: str
    intended_meaning: str = ""
    approved_localized_term: str = ""
    approved_original_form: str = ""
    forbidden_literal_forms: list[str] = Field(default_factory=list)
    domain_context: str = ""
    source_id: str | None = None


class TerminologyLedger(BaseModel):
    terms: list[TermEntry] = Field(default_factory=list)

    def find_forbidden_literals(self, text: str) -> list[str]:
        low = (text or "").lower()
        hits: list[str] = []
        for term in self.terms:
            for bad in term.forbidden_literal_forms:
                if bad and bad.lower() in low:
                    hits.append(bad)
        return hits


class ClaimEntry(BaseModel):
    claim_id: str
    claim: str
    source_id: str | None = None
    authority: str = "unknown"
    source_date: str = ""
    freshness_required: bool = False
    verified: bool = False
    editorial_inference: bool = False
    risk: str = "low"


class ClaimLedger(BaseModel):
    claims: list[ClaimEntry] = Field(default_factory=list)

    def unverified_high_risk(self) -> list[ClaimEntry]:
        return [
            c
            for c in self.claims
            if not c.verified
            and (c.freshness_required or c.risk in {"high", "critical"} or not c.source_id)
        ]


# Domain-scoped literal bans — NOT injected into unrelated course prompts.
DOMAIN_LITERAL_FIXTURES: dict[str, list[str]] = {
    "professional_or_income_skill": ["عميل بارد", "الجمهور البارد"],
    "language_learning": [],
}
