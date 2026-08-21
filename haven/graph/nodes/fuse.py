"""Stage 5c: FUSE -- one justification from three facts and a verified rule.

Reached only from a verdict that confirmed the model's selection, so by the time
this node runs the citation is already lawful and the passage may be handed over
in full. What the model does here is write, not choose.

Numbers remain the deterministic tier's: ``assert_no_novel_numbers`` rejects any
numeral the fact set did not supply. The provider gets one chance to correct it,
with the offending figure named; a second violation withholds the recommendation
and escalates, because a figure nobody computed must never reach an operator.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState
from haven.rag.corpus import BY_ID
from haven.reasoning.llm import LLMUnavailable, NumericIntegrityError


def fuse_node(state: SituationState) -> dict[str, Any]:
    flow, facts = state["flow"], state["facts"]
    passage = BY_ID[state["verdict"].passage_id]
    try:
        return {"justification": flow.fuse(facts, passage)}
    except LLMUnavailable as exc:
        return {
            "outcome": flow.degrade(facts, str(exc)),
            "degraded": True,
            "degraded_reason": str(exc),
        }
    except NumericIntegrityError as exc:
        # The guard fired twice. Caught rather than raised: an invented figure
        # is an operational condition with a correct response -- withhold and
        # escalate -- not a program error deserving a 500.
        return {"outcome": flow.refuse_numeric_integrity(facts, state["candidates"], "FUSE", exc)}
