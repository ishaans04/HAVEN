"""Stage 6b: SCREEN -- the schedule-impact veto, and the situation graph's exit.

The reasoning tier proposes; this screen disposes. It confirms that the proposed
action leaves every safety-critical role staffed by someone qualified, rested
and uncommitted. It can downgrade a recommendation to the fallback the *same
cited passage* prescribes, or block it outright into an escalation. It can never
create a recommendation of its own.

When the flow already refused, there is nothing to screen and the refusal passes
straight through.
"""

from __future__ import annotations

from typing import Any

from haven.config import THRESHOLDS
from haven.contracts import Citation, Recommendation, Refusal, ScheduleImpact
from haven.data.crew import SAFETY_CRITICAL_ROLES
from haven.deterministic.screens import CrewSnapshot, screen_schedule_impact
from haven.graph.nodes.common import record_situation
from haven.graph.state import SituationState
from haven.rag.corpus import BY_ID

ACTION_LABELS = {
    "second_operator_verify": "Second-operator verification",
    "short_rest_then_proceed": "Protected rest, then re-evaluate",
    "duty_rotation": "Duty rotation",
    "task_deferral": "Defer to next execution window",
    "no_action_required": "Proceed as scheduled",
}

RESOURCE_COST = {
    "second_operator_verify": "One additional crew-hour. No schedule slip.",
    "short_rest_then_proceed": "Protected rest before execution. Task slips inside the current window.",
    "duty_rotation": "Assignment moves to another qualified operator; originating operator released to rest.",
    "task_deferral": "Task slips to the next execution window. No crew-hours consumed now.",
    "no_action_required": "None.",
}


def screen_node(state: SituationState) -> dict[str, Any]:
    member, task = state["member"], state["task"]
    models, tasks = state["models"], state["tasks"]
    trail, flow, facts = state["trail"], state["flow"], state["facts"]
    outcome = state["outcome"]

    recommendation: Recommendation | None = None
    refusal_obj: Refusal | None = None

    if outcome.outcome == "refusal":
        refusal_obj = Refusal(
            reason=outcome.refusal["reason"],
            reason_label=outcome.refusal["reason_label"],
            searched=outcome.refusal["searched"],
            best_candidate=outcome.refusal["best_candidate"],
            gate=outcome.refusal["gate"],
            explanation=outcome.refusal["explanation"],
            escalate_to=outcome.refusal["escalate_to"],
            failed_clauses=outcome.refusal["failed_clauses"],
            model_selected=outcome.refusal["model_selected"],
            checker_disagreed=outcome.refusal["checker_disagreed"],
        )
    else:
        snapshots = [
            CrewSnapshot(
                crew_id=other.id,
                name=other.name or other.id,
                role=other.role,
                qualified_for=other.qualified_for,
                alertness_at_task=models[other.id].sample(task.scheduled).score,
                assigned_tasks=[
                    (t.id, t.criticality, t.scheduled, t.duration_min) for t in tasks if t.assigned_to == other.id
                ],
            )
            for other in state["request"].crew
        ]
        action = outcome.action
        impact = screen_schedule_impact(
            action=action,
            task_type=task.type,
            task_time=task.scheduled,
            task_duration_min=task.duration_min,
            assigned_crew_id=member.id,
            crew=snapshots,
            safety_critical_roles=SAFETY_CRITICAL_ROLES,
        )

        passage = BY_ID[outcome.citation["passage_id"]]
        downgrade_note = ""
        rationale = outcome.rationale
        if not impact.roster_ok and passage.fallback_action:
            downgrade_note = (
                f" Primary action ({ACTION_LABELS[action]}) was blocked by the schedule-impact screen; "
                f"{passage.doc} section {passage.section} prescribes this fallback where the primary "
                f"cannot be staffed."
            )
            action = passage.fallback_action
            rationale = flow.regenerate(facts, passage, action, outcome.justification)

        trail.append(
            step="SCHEDULE_IMPACT",
            tier="deterministic",
            detail=(impact.note + downgrade_note if impact.roster_ok or passage.fallback_action else impact.note),
            inputs={
                "proposed_action": outcome.action,
                "safety_critical_roles": list(SAFETY_CRITICAL_ROLES),
                "alternate_min_alertness": THRESHOLDS.alternate_min_alertness,
            },
            outputs={
                "roster_ok": impact.roster_ok,
                "alternate": impact.alternate,
                "blocked_reason": impact.blocked_reason,
                "final_action": action,
            },
        )

        if not impact.roster_ok and not passage.fallback_action:
            refusal_obj = Refusal(
                reason="roster_conflict",
                reason_label="No workable staffing",
                searched=[c["doc"] for c in (outcome.candidates or [])],
                best_candidate=None,
                gate=THRESHOLDS.relevance_gate,
                explanation=(
                    f"{passage.doc} section {passage.section} governs and prescribes "
                    f"{ACTION_LABELS[outcome.action].lower()}, but the schedule-impact screen "
                    f"cannot staff it: {impact.note} The procedure states no alternative for this "
                    f"case, so the decision is escalated rather than downgraded."
                ),
                escalate_to="flight_director",
                # The passage verified cleanly; what failed was the roster, not
                # the rule. Recording the selection keeps the refusal traceable
                # back to the same passage the audit trail names.
                model_selected=outcome.model_selected,
            )
        else:
            recommendation = Recommendation(
                action=action,
                action_label=ACTION_LABELS[action],
                citation=Citation(**outcome.citation),
                rationale=rationale + downgrade_note,
                resource_cost=RESOURCE_COST[action],
                # The checker's verdict on the cited passage, carried out to the
                # operator. A downgrade changes the action, never the citation,
                # so these clauses describe the passage still being cited.
                verified_clauses=outcome.verified_clauses,
                schedule_impact=ScheduleImpact(
                    roster_ok=impact.roster_ok,
                    checked_roles=sorted(set(impact.checked_roles)),
                    alternate=impact.alternate,
                    alternate_name=impact.alternate_name,
                    note=impact.note,
                    blocked_reason=impact.blocked_reason,
                ),
            )

    return {
        "recommendation": recommendation,
        "refusal": refusal_obj,
        "situation": record_situation(state, recommendation, refusal_obj),
    }
