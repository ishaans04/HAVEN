"""Stage 5: SELECT -- the model proposes.

The one node in the graph where a provider is asked for a judgement, and it is
given nothing but prose: passage id, document, section, title, text. The
compiled preconditions that decide the matter are withheld (S4), and the answer
it returns is a *proposal* -- VERIFY disposes of it.

A provider outage is caught here rather than raised, because an unreachable
model is an operational condition, not a program error: the flow degrades to a
structured escalation with the deterministic evidence attached, and every
reasoning node after this one goes inert. That is the invariant the guards in
VERIFY, REFUSE and GENERATE encode -- **once an outcome exists, nothing may
replace it.**
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState
from haven.reasoning.llm import LLMUnavailable

NOTHING_SELECTED: dict[str, Any] = {"governing_passage_id": None, "rejected": []}


def select_node(state: SituationState) -> dict[str, Any]:
    flow, facts = state["flow"], state["facts"]
    candidates = state["candidates"]

    # Retrieval found nothing to read. Consulting a provider about an empty
    # candidate set would be a call whose only possible honest answer is the one
    # already known, so the flow proceeds straight to VERIFY, which will find
    # nothing admissible and refuse.
    if not candidates:
        return {"selection": NOTHING_SELECTED}

    try:
        return {"selection": flow.select(facts, candidates)}
    except LLMUnavailable as exc:
        return {
            "outcome": flow.degrade(facts, str(exc)),
            "degraded": True,
            "degraded_reason": str(exc),
        }
