"""English Spoken Delivery QA — used when presenter_language is English."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class EnglishGateIssue:
    code: str
    detail: str
    severity: str


@dataclass
class EnglishGateReport:
    issues: list[EnglishGateIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity in ("fatal", "serious") for i in self.issues)


_STIFF = re.compile(
    r"\b(furthermore|moreover|thus|hence|in conclusion|it is important to note)\b",
    re.I,
)
_MARKETING = re.compile(
    r"\b(guaranteed income|get rich quick|100% results|secret formula)\b",
    re.I,
)


def run_english_spoken_gate(script_text: str) -> EnglishGateReport:
    report = EnglishGateReport()
    text = script_text or ""
    if not text.strip():
        report.issues.append(EnglishGateIssue("empty_script", "Empty script", "fatal"))
        return report
    if _STIFF.search(text):
        report.issues.append(
            EnglishGateIssue(
                "LANGUAGE_REGISTER_MIX",
                "Stiff essay register unfit for spoken English delivery",
                "serious",
            )
        )
    if _MARKETING.search(text):
        report.issues.append(
            EnglishGateIssue(
                "UNSUPPORTED_CLAIM",
                "Marketing/guarantee phrasing blocked",
                "fatal",
            )
        )
    for line in text.splitlines():
        if len(line.split()) > 42:
            report.issues.append(
                EnglishGateIssue(
                    "READ_ALOUD_FAILURE",
                    "Line too long to speak comfortably",
                    "serious",
                )
            )
            break
    return report
