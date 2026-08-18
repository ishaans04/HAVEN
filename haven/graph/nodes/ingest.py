"""Stage 1: INGEST.

Turns the request into the structures every later stage reads: one
Three-Process Model per crew member, a lookup from crew id to crew member, and
the task list in execution order. Nothing here decides anything.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from haven.contracts import CrewMember
from haven.deterministic.three_process_model import SleepEpisode, ThreeProcessModel
from haven.graph.state import HavenState
from haven.rag.corpus import CORPUS_MANIFEST


def model_for(member: CrewMember) -> ThreeProcessModel:
    episodes = [SleepEpisode(sleep=e.sleep, wake=e.wake) for e in member.sleep_log]
    return ThreeProcessModel(episodes, acrophase_offset_h=member.circadian_offset_h)


def new_evaluation_id(window_start: datetime) -> str:
    """A label unique to this run of the engine.

    The date is the window's; the time and the random suffix are this run's. The
    suffix is what makes it unique: two evaluations of the same window in the
    same second are ordinary -- a demo clicking between scenarios does it
    constantly -- and until now they produced identical Situation identifiers,
    so their audit trails overwrote one another in the store.

    Deriving the identifier from a digest of the request instead would be
    reproducible, which is appealing, but re-running one scenario would then
    reuse its audit_ref and append a second set of steps to the trail already
    on disk. Uniqueness is what the durable ledger needs.
    """
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    return f"EVAL-{window_start.strftime('%Y%m%d')}-{stamp}-{uuid.uuid4().hex[:6]}"


def ingest_node(state: HavenState) -> dict[str, Any]:
    request = state["request"]
    return {
        "evaluation_id": new_evaluation_id(request.evaluation_window.start),
        "corpus_manifest": CORPUS_MANIFEST,
        "window_start": request.evaluation_window.start,
        "window_end": request.evaluation_window.end,
        "models": {m.id: model_for(m) for m in request.crew},
        "by_id": {m.id: m for m in request.crew},
        # Sorted here, once. The Situation identifier is derived from a task's
        # position in this list, so the ordering is load-bearing, not cosmetic.
        "tasks": sorted(request.tasks, key=lambda t: t.scheduled),
    }
