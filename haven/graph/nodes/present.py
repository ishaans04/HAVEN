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
    # Only a ProviderChain reports a chain; a single adapter reports itself.
    chain_status = llm.status() if hasattr(llm, "status") else {}

    return {
        "response": EvaluationResponse(
            evaluation_id=state["evaluation_id"],
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
                # A fallback inside the chain degrades the evaluation just as a
                # total outage does. The operator asked for interpretation from
                # a particular model; being handed another is worth saying.
                degraded=state["degraded"] or bool(chain_status.get("degraded")),
                degraded_reason=state["degraded_reason"] or chain_status.get("degraded_reason"),
                corpus_manifest=state["corpus_manifest"],
                provider_chain=list(chain_status.get("chain", [])),
                served_by=str(chain_status.get("served_by", "") or llm.provider),
            ),
        )
    }
