"""WITHHOLD -- the terminal node for a Situation whose input is too thin.

Reached only from the confidence gate, and only when the gate says the record
cannot support a conclusion. No retrieval runs, no model is consulted, and no
recommendation is issued: the missing record is reported as the finding and the
decision escalates to the flight surgeon.
"""

from __future__ import annotations

from typing import Any

from haven.config import THRESHOLDS
from haven.contracts import Refusal
from haven.graph.nodes.common import record_situation
from haven.graph.state import SituationState


def withhold_node(state: SituationState) -> dict[str, Any]:
    confidence = state["confidence"]
    trail = state["trail"]

    refusal = Refusal(
        reason="insufficient_input",
        reason_label="Input insufficient",
        searched=[],
        best_candidate=None,
        gate=THRESHOLDS.relevance_gate,
        explanation=(
            "The sleep and duty record for this operator does not cover enough of the trailing "
            "window to model alertness. "
            + " ".join(n.capitalize() + "." for n in confidence.notes)
            + " No recommendation is issued; the gap itself is the finding."
        ),
        escalate_to="flight_surgeon",
    )
    trail.append(
        step="WITHHOLD",
        tier="deterministic",
        detail="Confidence gate withheld the recommendation before the reasoning tier was invoked.",
        outputs=refusal.model_dump(),
    )

    return {"refusal": refusal, "situation": record_situation(state, None, refusal)}
