"""Stage 5b: VERIFY -- the checker disposes.

The second branch in the system, and the one the v2 invariant turns on. The
proposal made at SELECT is checked against the compiled rule, and the result
routes: a confirmed selection goes on to be written up, anything else becomes a
structured escalation.

    model said | checker says          | result
    -----------|-----------------------|----------------------------------------
    passage P  | P admissible          | FUSE
    passage P  | P inadmissible        | REFUSE, naming the unmet clause
    none       | something admissible  | REFUSE, logging the disagreement
    none       | nothing admissible    | REFUSE, no governing procedure

Both disagreement directions fail closed, and a passage the model did not
select is never promoted -- a checker that could hand back a rule nobody read
would be the same system with the tiers swapped, not a safer one.

This node replaces v1's GATE, which compared a TF-IDF-derived similarity float
against a configured threshold and called the comparison a decision. Whether a
rule applies is not a question about similarity.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState


def verify_node(state: SituationState) -> dict[str, Any]:
    # The provider was unreachable at SELECT and the outcome is already settled.
    # Nothing to verify, and nothing here may replace a settled outcome.
    if state.get("outcome") is not None:
        return {}
    verdict = state["flow"].verify(state["admissibility"], state["selection"])
    return {"verdict": verdict}


def route_after_verify(state: SituationState) -> str:
    """Pick the next node from the verdict already computed and already logged.

    Deterministic by construction: one boolean, read straight out of the state.
    A missing verdict means the outcome was settled before verification could
    run, which is a refusal by every path that can produce it.
    """
    verdict = state.get("verdict")
    return "FUSE" if verdict is not None and verdict.verified else "REFUSE"
