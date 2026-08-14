"""Stage 7: PRESENT.

Assembles the payload the console renders. Nothing is computed here that has not
already been computed and, where it mattered, logged; this node only names which
tier produced what, so an operator can tell a live tier from a mocked one and a
healthy run from a degraded one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from haven.config import BUILD_MODE
from haven.contracts import EvaluationResponse, TierStatus
from haven.graph.state import HavenState


def _now() -> datetime:
    return datetime.now(timezone.utc)


def present_node(state: HavenState) -> dict[str, Any]:
    request = state["request"]
    llm = state["llm"]
    retriever = state["retriever"]

    return {
        "response": EvaluationResponse(
            evaluation_id=f"EVAL-{state['window_start'].strftime('%Y%m%d')}-{_now().strftime('%H%M%S')}",
            generated_at=_now(),
            scenario_id=request.scenario_id,
            window=request.evaluation_window,
            readiness=state["readiness"],
            timeline=state["timeline"],
            situations=state["situations"],
            archived_low_risk=state["archived"],
            tier_status=TierStatus(
                deterministic="Three-Process Model + NASA-TLX (live)",
                retrieval=retriever.backend_name,
                reasoning=f"{llm.provider} / {llm.model_id}",
                orchestration=f"Bob reasoning flow, hash-chained audit ({BUILD_MODE})",
                degraded=state["degraded"],
                degraded_reason=state["degraded_reason"],
            ),
        )
    }
