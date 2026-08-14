"""Stage 5: REASON.

Runs the orchestrated reasoning flow bound by RETRIEVE. The flow writes its own
steps -- RETRIEVE, SELECT, GATE, and then either FUSE + GENERATE or REFUSE -- to
the same hash-chained trail this Situation opened at the confidence gate, so the
record stays one continuous chain regardless of which branch it took.

A provider outage does not raise out of here: the flow degrades to a structured
escalation and reports it, and the flag is carried back up so the whole
evaluation can say so in its tier status rather than failing quietly.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState


def reason_node(state: SituationState) -> dict[str, Any]:
    outcome = state["flow"].run(state["facts"])
    return {
        "outcome": outcome,
        "degraded": outcome.degraded,
        "degraded_reason": outcome.degraded_reason,
    }
