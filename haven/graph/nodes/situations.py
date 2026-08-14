"""SITUATIONS -- runs the situation graph once per raised Situation.

Sequential by design. Concurrency is a later phase's problem, and until then the
iteration order is the sorted task order, which is the order the audit trail,
the Situation list and the console all read in.

Each pass is a fresh invocation of the compiled situation graph with its own
audit trail. What comes back up is the ``Situation`` payload and, if the
reasoning provider was unreachable for that pass, the degraded flag -- sticky
once set, with the most recent reason carried into the tier status.
"""

from __future__ import annotations

from typing import Any

from haven.contracts import Situation
from haven.graph.situation_graph import SITUATION_GRAPH
from haven.graph.state import HavenState


def situations_node(state: HavenState) -> dict[str, Any]:
    situations: list[Situation] = []
    degraded = False
    degraded_reason: str | None = None

    for entry in state["raised"]:
        scored = entry.scored
        result = SITUATION_GRAPH.invoke(
            {
                "window_start": state["window_start"],
                "request": state["request"],
                "models": state["models"],
                "tasks": state["tasks"],
                "retriever": state["retriever"],
                "llm": state["llm"],
                "member": scored.member,
                "model": scored.model,
                "task": scored.task,
                "sample": scored.sample,
                "workload": scored.workload,
                "trigger": entry.trigger,
                "situation_id": entry.situation_id,
            }
        )
        if result.get("degraded"):
            degraded = True
            degraded_reason = result.get("degraded_reason")
        situations.append(result["situation"])

    return {"situations": situations, "degraded": degraded, "degraded_reason": degraded_reason}
