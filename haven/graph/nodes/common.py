"""The closing sequence shared by both terminal nodes of the situation graph.

WITHHOLD and SCREEN reach the same end: seal the audit trail into the store,
then project the accumulated state onto the ``Situation`` the contract exposes.
Written once rather than twice so the two exits cannot drift apart -- the fields
below are the operator-facing record of a safety decision, and a field that is
right on one path and stale on the other is exactly the kind of divergence
nobody notices until it matters.

Not a node. It has no entry in either graph; both nodes call it as their last
statement.
"""

from __future__ import annotations

from haven.contracts import Recommendation, Refusal, Situation
from haven.graph.state import SituationState
from haven.reasoning.audit import AUDIT


def record_situation(
    state: SituationState,
    recommendation: Recommendation | None,
    refusal: Refusal | None,
) -> Situation:
    """Commit the trail and build the Situation. Exactly one outcome is populated."""
    member, task = state["member"], state["task"]
    sample, workload, trigger = state["sample"], state["workload"], state["trigger"]

    AUDIT.put(state["trail"])
    return Situation(
        situation_id=state["situation_id"],
        crew_member=member.id,
        crew_member_name=member.name or member.id,
        crew_role=member.role,
        task=task.id,
        task_type=task.type,
        task_label=task.label,
        task_scheduled=task.scheduled,
        task_criticality=task.criticality,
        alertness_score=round(sample.score, 3),
        workload_score=round(workload.score, 1),
        circadian_flag=sample.in_circadian_low,
        risk_level=trigger.risk_level,
        confidence=state["confidence"].level,
        outcome="refusal" if refusal else "recommendation",
        recommendation=recommendation,
        refusal=refusal,
        evidence=state["evidence"],
        audit_ref=state["audit_ref"],
        corpus_manifest=state["corpus_manifest"],
    )
