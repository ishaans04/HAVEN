"""Stage 5d: GENERATE -- the operator-facing recommendation.

States the action the verified passage prescribes, cites it, and carries the
checker's clause-by-clause verdict out with it so the console can show the
operator the test the citation passed rather than asking them to trust it.

Inert if the provider died at FUSE: once an outcome exists, nothing may replace
it.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState
from haven.rag.corpus import BY_ID
from haven.reasoning.llm import LLMUnavailable


def generate_node(state: SituationState) -> dict[str, Any]:
    if state.get("outcome") is not None:
        return {}

    flow, facts, verdict = state["flow"], state["facts"], state["verdict"]
    passage = BY_ID[verdict.passage_id]
    try:
        outcome = flow.generate(
            facts,
            passage,
            state["justification"],
            verdict,
            state["candidates"],
            state["selection"]["rejected"],
        )
    except LLMUnavailable as exc:
        return {
            "outcome": flow.degrade(facts, str(exc)),
            "degraded": True,
            "degraded_reason": str(exc),
        }
    return {"outcome": outcome}
