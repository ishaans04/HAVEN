"""REFUSE -- the escalation VERIFY's disposition implies.

A refusal is a first-class output here, not an error path: it records what was
searched, what the model proposed, which compiled clause the checker found
unsatisfied, and who the decision escalates to. That record is the product.

Inert when the provider outage path already produced an outcome at SELECT --
that refusal is written and hashed, and this node does not get to write a second
one over it.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState


def refuse_node(state: SituationState) -> dict[str, Any]:
    if state.get("outcome") is not None:
        return {}
    outcome = state["flow"].refuse_verdict(
        state["facts"],
        state["candidates"],
        state["verdict"],
        state["selection"]["rejected"],
    )
    return {"outcome": outcome}
