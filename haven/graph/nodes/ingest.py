"""Stage 1: INGEST.

Turns the request into the structures every later stage reads: one
Three-Process Model per crew member, a lookup from crew id to crew member, and
the task list in execution order. Nothing here decides anything.
"""

from __future__ import annotations

from typing import Any

from haven.contracts import CrewMember
from haven.deterministic.three_process_model import SleepEpisode, ThreeProcessModel
from haven.graph.state import HavenState


def model_for(member: CrewMember) -> ThreeProcessModel:
    episodes = [SleepEpisode(sleep=e.sleep, wake=e.wake) for e in member.sleep_log]
    return ThreeProcessModel(episodes, acrophase_offset_h=member.circadian_offset_h)


def ingest_node(state: HavenState) -> dict[str, Any]:
    request = state["request"]
    return {
        "window_start": request.evaluation_window.start,
        "window_end": request.evaluation_window.end,
        "models": {m.id: model_for(m) for m in request.crew},
        "by_id": {m.id: m for m in request.crew},
        # Sorted here, once. The Situation identifier is derived from a task's
        # position in this list, so the ordering is load-bearing, not cosmetic.
        "tasks": sorted(request.tasks, key=lambda t: t.scheduled),
    }
