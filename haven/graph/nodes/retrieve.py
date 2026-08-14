"""Stage 4: RETRIEVE.

Assembles the deterministic fact set the reasoning tier is allowed to see -- it
is also the allow-list the numeric-integrity guard checks generated text
against -- binds the retrieval and reasoning adapters into the flow that will
run them, and performs the retrieval itself.

Since Phase 1B this node really does retrieve. In Phase 1A it only bound the
flow, because ``ReasoningFlow.run`` was one indivisible call covering retrieval,
selection, the gate, fusion and generation; that call is gone, and each of its
steps is now a node of this graph. What comes back is the *full* candidate
payload: compiled preconditions included, because ADMISSIBILITY, the audit trail
and the console all need them. The redaction that keeps them away from the
reasoning tier happens at SELECT, in one place (safety requirement S4).
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState
from haven.reasoning.orchestrator import ReasoningFlow


def retrieve_node(state: SituationState) -> dict[str, Any]:
    member, task = state["member"], state["task"]
    model, sample, workload = state["model"], state["sample"], state["workload"]
    trigger = state["trigger"]

    facts = {
        "crew_name": member.name or member.id,
        "crew_role": member.role,
        "task_id": task.id,
        "task_type": task.type,
        "criticality": task.criticality,
        "phase": "execution",
        "alertness_score": round(sample.score, 2),
        "alertness_threshold": trigger.alertness_threshold,
        "workload_score": round(workload.score, 1),
        "circadian_flag": sample.in_circadian_low,
        "hours_awake": round(sample.hours_awake, 1),
        "sleep_debt_h": round(model.sleep_debt_h(task.scheduled), 1),
        "kss": round(sample.kss, 1),
    }
    flow = ReasoningFlow(state["retriever"], state["llm"], state["trail"])
    return {"facts": facts, "flow": flow, "candidates": flow.retrieve(facts)}
