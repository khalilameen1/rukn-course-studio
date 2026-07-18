"""Teleprompter blocks — meaning-based lines and pauses (internal only)."""

from __future__ import annotations

import re
from pydantic import BaseModel, Field

from app.generation.quality.contract import DeliveryContract
from app.generation.quality.issue_codes import IssueCode


class TeleprompterLine(BaseModel):
    text: str
    pause_after: bool = False


class TeleprompterBlock(BaseModel):
    lines: list[TeleprompterLine] = Field(default_factory=list)
    pause_after: bool = True


class TeleprompterDoc(BaseModel):
    blocks: list[TeleprompterBlock] = Field(default_factory=list)

    def plain_text(self) -> str:
        """DOCX-facing text: line breaks inside blocks, blank line between blocks."""
        parts: list[str] = []
        for i, block in enumerate(self.blocks):
            lines = [ln.text.strip() for ln in block.lines if ln.text.strip()]
            if not lines:
                continue
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    def word_count(self) -> int:
        return len(self.plain_text().split())


_SPLIT_HINTS = re.compile(
    r"(?<=\s)(عشان|لأن|لكن|لو|بعدين|يعني|مثلاً|مثلا|والنتيجة|الاستثناء)\s+"
)


def build_teleprompter_doc(
    script_text: str,
    *,
    contract: DeliveryContract | None = None,
) -> TeleprompterDoc:
    contract = contract or DeliveryContract()
    # Prefer existing paragraphs as blocks.
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", script_text or "") if b.strip()]
    if not raw_blocks:
        raw_blocks = [script_text.strip()] if (script_text or "").strip() else []
    blocks: list[TeleprompterBlock] = []
    for raw in raw_blocks:
        lines_src = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines_src) == 1:
            lines_src = _split_into_lines(lines_src[0], contract)
        # Merge ultra-short consecutive shreds.
        lines_src = _merge_short_runs(lines_src, contract)
        t_lines = [TeleprompterLine(text=ln) for ln in lines_src if ln]
        if t_lines:
            blocks.append(TeleprompterBlock(lines=t_lines, pause_after=True))
    return TeleprompterDoc(blocks=blocks)


def _split_into_lines(text: str, contract: DeliveryContract) -> list[str]:
    words = text.split()
    if len(words) <= contract.teleprompter_line_hard_max:
        return [text]
    lines: list[str] = []
    buf: list[str] = []
    for w in words:
        buf.append(w)
        if len(buf) >= contract.teleprompter_line_target_max:
            lines.append(" ".join(buf))
            buf = []
    if buf:
        if lines and len(buf) < 3:
            lines[-1] = lines[-1] + " " + " ".join(buf)
        else:
            lines.append(" ".join(buf))
    return lines


def _merge_short_runs(lines: list[str], contract: DeliveryContract) -> list[str]:
    out: list[str] = []
    for ln in lines:
        words = ln.split()
        if out and len(words) <= 2 and len(out[-1].split()) < contract.teleprompter_line_target_min:
            out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)
    # Collapse 3+ ultra-short consecutive lines.
    fixed: list[str] = []
    i = 0
    while i < len(out):
        if len(out[i].split()) <= 2:
            run = [out[i]]
            j = i + 1
            while j < len(out) and len(out[j].split()) <= 2:
                run.append(out[j])
                j += 1
            if len(run) >= 3:
                fixed.append(" ".join(run))
                i = j
                continue
        fixed.append(out[i])
        i += 1
    return fixed


def detect_bad_source_line_breaks(script_text: str) -> list[tuple[str, str]]:
    """Flag shredded teleprompter input (word-per-line) before layout merge."""
    issues: list[tuple[str, str]] = []
    lines = [ln.strip() for ln in (script_text or "").splitlines() if ln.strip()]
    short_run = 0
    for ln in lines:
        if len(ln.split()) <= 2:
            short_run += 1
            if short_run >= 4:
                issues.append(
                    (IssueCode.BAD_LINE_BREAK.value, "four+ ultra-short consecutive lines")
                )
                break
        else:
            short_run = 0
    return issues


def evaluate_teleprompter_layout(
    doc: TeleprompterDoc,
    *,
    contract: DeliveryContract | None = None,
    source_text: str | None = None,
) -> list[tuple[str, str]]:
    contract = contract or DeliveryContract()
    issues: list[tuple[str, str]] = []
    if source_text:
        issues.extend(detect_bad_source_line_breaks(source_text))
    all_lines = [ln.text for b in doc.blocks for ln in b.lines if ln.text.strip()]
    if not all_lines:
        issues.append((IssueCode.TELEPROMPTER_LAYOUT_FAIL.value, "empty teleprompter"))
        return issues
    lengths = [len(ln.split()) for ln in all_lines]
    avg = sum(lengths) / len(lengths)
    if avg > contract.teleprompter_line_hard_max + 2:
        issues.append(
            (
                IssueCode.READ_ALOUD_FAILURE.value,
                f"average line words {avg:.1f} too high for breath",
            )
        )
    if max(lengths) > contract.teleprompter_line_hard_max + 6:
        issues.append(
            (
                IssueCode.READ_ALOUD_FAILURE.value,
                f"longest line has {max(lengths)} words",
            )
        )
    # Too many consecutive 1-2 word lines.
    short_run = 0
    for n in lengths:
        if n <= 2:
            short_run += 1
            if short_run >= 4:
                issues.append(
                    (IssueCode.BAD_LINE_BREAK.value, "four+ ultra-short consecutive lines")
                )
                break
        else:
            short_run = 0
    for block in doc.blocks:
        bw = sum(len(ln.text.split()) for ln in block.lines)
        if bw and (bw < contract.block_word_min or bw > contract.block_word_max + 20):
            # Soft: only flag extreme empties / monsters.
            if bw < 3 or bw > contract.block_word_max + 40:
                issues.append(
                    (
                        IssueCode.TELEPROMPTER_LAYOUT_FAIL.value,
                        f"block words={bw} outside flexible range",
                    )
                )
    return issues
