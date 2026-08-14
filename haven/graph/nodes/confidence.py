"""Stage 6a: CONFIDENCE -- the input-sufficiency gate.

The first node of the situation graph, and the reason the situation graph has a
branch at all. It opens the audit trail for this Situation, writes the TRIGGER
and CONFIDENCE entries, and decides whether there is enough record to reason
about. When there is not, the graph routes straight to WITHHOLD and the
reasoning tier is never reached -- asserting anything from a record this thin
would be false certainty, and the gap itself is the finding.
"""

from __future__ import annotations

from typing import Any

from haven.config import THRESHOLDS
from haven.contracts import Evidence
from haven.deterministic.screens import assess_confidence
from haven.graph.state import SituationState
from haven.reasoning.audit import AuditTrail


def confidence_node(state: SituationState) -> dict[str, Any]:
    member, task = state["member"], state["task"]
    model, sample, workload = state["model"], state["sample"], state["workload"]
    trigger = state["trigger"]
    situation_id = state["situation_id"]

    confidence = assess_confidence(
        sleep_episodes=[(e.sleep, e.wake) for e in member.sleep_log],
        duty_entries=[(d.start, d.end) for d in member.duty_log],
        window_start=state["window_start"],
    )

    last_sleep = max(
        (e for e in member.sleep_log if e.wake <= task.scheduled),
        key=lambda e: e.wake,
        default=None,
    )
    evidence = Evidence(
        hours_awake=round(sample.hours_awake, 1),
        sleep_debt_h=round(model.sleep_debt_h(task.scheduled), 1),
        last_sleep_duration_h=round((last_sleep.wake - last_sleep.sleep).total_seconds() / 3600.0, 1)
        if last_sleep
        else 0.0,
        kss=round(sample.kss, 1),
        homeostatic=round(sample.homeostatic, 2),
        circadian=round(sample.circadian, 2),
        inertia=round(sample.inertia, 2),
        workload_subscales={k: round(v, 1) for k, v in workload.subscales.items()},
        workload_band=workload.band,
        data_coverage=confidence.coverage,
    )

    audit_ref = f"LOG-{situation_id}"
    trail = AuditTrail(audit_ref=audit_ref, situation_id=situation_id)
    trail.append(
        step="TRIGGER",
        tier="deterministic",
        detail=(
            f"Three-Process Model and NASA-TLX evaluated for {member.name} against {task.id}. "
            + "; ".join(trigger.reasons)
            + "."
        ),
        inputs={
            "alertness_threshold": trigger.alertness_threshold,
            "workload_trigger": THRESHOLDS.workload_trigger,
            "criticality": task.criticality,
        },
        outputs={
            "alertness_score": round(sample.score, 3),
            "workload_score": round(workload.score, 1),
            "circadian_flag": sample.in_circadian_low,
            "risk_score": trigger.risk_score,
            "risk_level": trigger.risk_level,
        },
    )
    trail.append(
        step="CONFIDENCE",
        tier="deterministic",
        detail=(
            f"Input sufficiency assessed as {confidence.level}"
            + (f": {'; '.join(confidence.notes)}." if confidence.notes else ".")
        ),
        inputs={"lookback_days": 3, "full_coverage_threshold": THRESHOLDS.confidence_full_coverage},
        outputs={"level": confidence.level, "coverage": confidence.coverage, "withhold": confidence.withhold},
    )

    return {"audit_ref": audit_ref, "trail": trail, "confidence": confidence, "evidence": evidence}


def route_after_confidence(state: SituationState) -> str:
    """Pick the next node from the gate's own verdict, and nothing else.

    Deterministic by construction: one boolean, already computed and already
    logged, read straight out of the state. A router that consulted a model
    would put an unaudited decision on the control flow itself.
    """
    return "WITHHOLD" if state["confidence"].withhold else "RETRIEVE"
