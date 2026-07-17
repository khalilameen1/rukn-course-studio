"""Coarse agent roster for Generate UI — never exposes agent text."""

from __future__ import annotations

from typing import Literal

AgentId = Literal["research", "map", "lessons", "quality", "export"]
AgentState = Literal["idle", "running", "done"]

ROSTER_ORDER: tuple[AgentId, ...] = (
    "research",
    "map",
    "lessons",
    "quality",
    "export",
)

ROSTER_LABELS: dict[AgentId, str] = {
    "research": "Research",
    "map": "Map",
    "lessons": "Lessons",
    "quality": "Quality",
    "export": "Export",
}

# Stages that mark each agent as currently running.
_RUNNING: dict[str, AgentId] = {
    "queued": "research",
    "reading_sources": "research",
    "filling_gaps": "research",
    "synthesizing": "research",
    "building_map": "map",
    "generating": "lessons",
    "reviewing_repetition": "quality",
    "reviewing": "quality",
    "exporting": "export",
}

# Stages at/after which prior agents are done.
_DONE_THROUGH: dict[str, int] = {
    "queued": -1,
    "reading_sources": -1,
    "filling_gaps": -1,
    "synthesizing": -1,
    "building_map": 0,  # research done
    "generating": 1,
    "reviewing_repetition": 2,
    "reviewing": 2,
    "exporting": 3,
    "done": 4,
    "completed": 4,
    "failed": -2,
    "partial": -2,
    "canceled": -2,
    "paused": -2,
}


def build_agent_roster(
    *,
    current_stage: str | None,
    status: str | None = None,
) -> list[dict[str, str]]:
    """Return [{id, label, state}] for the five coarse agents."""
    stage = (current_stage or "").strip().lower() or "queued"
    status_s = (status or "").strip().lower()

    if status_s in {"completed"} or stage == "done":
        return [
            {"id": a, "label": ROSTER_LABELS[a], "state": "done"}
            for a in ROSTER_ORDER
        ]

    if status_s in {"failed", "partial", "canceled"} or stage in {
        "failed",
        "partial",
        "canceled",
    }:
        # Mark completed prefix if we can infer; otherwise all idle except none running.
        done_idx = _DONE_THROUGH.get(stage, -1)
        running = _RUNNING.get(stage)
        out: list[dict[str, str]] = []
        for i, agent in enumerate(ROSTER_ORDER):
            if done_idx >= i:
                state: AgentState = "done"
            elif running == agent:
                state = "running"
            else:
                state = "idle"
            out.append({"id": agent, "label": ROSTER_LABELS[agent], "state": state})
        return out

    running = _RUNNING.get(stage, "research")
    done_idx = _DONE_THROUGH.get(stage, -1)
    out = []
    for i, agent in enumerate(ROSTER_ORDER):
        if agent == running:
            state = "running"
        elif done_idx >= i:
            state = "done"
        else:
            state = "idle"
        out.append({"id": agent, "label": ROSTER_LABELS[agent], "state": state})
    return out
